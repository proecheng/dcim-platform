"""统一数据入库管道 — Task 2.1

所有数据源（MQTT、DemoEngine、DataSourceBridge）统一通过此管道入库。
单一入口 process_payload() 执行完整链路:
  PointDataLatest + PointRealtime + PointHistory → commit → alarm → WS → Redis → linkage
"""

import json as _json
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional, Sequence

from sqlalchemy import select, update, text, bindparam
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.database import async_session
from ..core.redis import redis_service
from ..engines.alarm_engine import alarm_engine
from ..models import Point, PointRealtime, PointHistory, Alarm
from ..models.device import Device
from ..models.spatial import Site
from ..models.gateway import PointDataLatest
from ..services.websocket import ws_manager

logger = logging.getLogger(__name__)


ALLOWED_STATUS = {"normal", "offline", "alarm", "unknown", "fault", "maintenance"}


# ── 标准载荷 DTO ──────────────────────────────────────────────


@dataclass
class IngestPoint:
    """标准化的单点数据载荷"""

    point_id: int  # Point 表主键 (int)
    value: float  # 数值
    quality: int = 0  # 数据质量 (0=好, 1=不确定, 2=坏)
    timestamp: Optional[datetime] = None  # 采集时间
    status: str = "normal"  # 状态
    gateway_id: Optional[str] = None  # 网关 ID (MQTT 来源)
    point_key: Optional[str] = None  # 原始点位标识 (PointDataLatest 用)
    source: str = "unknown"  # 来源标识: mqtt / demo / bridge


@dataclass
class IngestResult:
    """入库结果"""

    total: int = 0
    written: int = 0
    alarms_created: int = 0
    alarms_resolved: int = 0
    errors: List[str] = field(default_factory=list)


# ── 点位元数据缓存 ──────────────────────────────────────────────

# 内存缓存: point_id → Point 基本属性 (避免每次查库)
_point_meta_cache: dict[int, dict] = {}
_cache_loaded = False

# 降采样缓存: point_id → 最后一次存储时间
_last_store_time: dict[int, datetime] = {}


async def _ensure_point_cache(session: AsyncSession) -> None:
    """加载点位元数据缓存（首次调用时加载，后续跳过）"""
    global _cache_loaded
    if _cache_loaded:
        return
    result = await session.execute(
        select(
            Point.id,
            Point.point_code,
            Point.point_name,
            Point.point_type,
            Point.device_type,
            Point.device_id,
            Point.area_code,
            Point.unit,
            Point.is_enabled,
            Point.store_interval,  # 新增：存储间隔
            Device.site_id,
            Device.device_name,
            Site.site_name,
        )
        .outerjoin(Device, Point.device_id == Device.id)
        .outerjoin(Site, Device.site_id == Site.id)
    )
    for row in result.all():
        _point_meta_cache[row[0]] = {
            "point_code": row[1],
            "point_name": row[2],
            "point_type": row[3],
            "device_type": row[4],
            "device_id": row[5],
            "area_code": row[6],
            "unit": row[7],
            "is_enabled": row[8],
            "store_interval": row[9] or 300,  # 默认5分钟
            "site_id": row[10],
            "device_name": row[11],
            "site_name": row[12],
        }
    _cache_loaded = True
    logger.info("点位元数据缓存已加载: %d 条", len(_point_meta_cache))


def invalidate_point_cache() -> None:
    """使点位缓存失效（点位配置变更时调用）"""
    global _cache_loaded
    _point_meta_cache.clear()
    _last_store_time.clear()  # 清空降采样缓存
    _cache_loaded = False


# ── 主入口 ──────────────────────────────────────────────────────


async def process_payload(
    points: Sequence[IngestPoint],
    *,
    session: Optional[AsyncSession] = None,
) -> IngestResult:
    """统一入库管道 — 所有数据源的单一入口

    Args:
        points: 标准化的点位数据列表
        session: 可选的外部数据库会话（不传则自动创建）

    Returns:
        IngestResult 包含写入统计和告警信息
    """
    if not points:
        return IngestResult()

    if session is not None:
        return await _process_batch(points, session)

    async with async_session() as db:
        return await _process_batch(points, db)


async def _process_batch(
    points: Sequence[IngestPoint],
    session: AsyncSession,
) -> IngestResult:
    """执行完整的入库批处理"""
    result = IngestResult(total=len(points))

    await _ensure_point_cache(session)

    now = datetime.now()

    # 过滤无效点位
    valid_points: list[IngestPoint] = []
    for pt in points:
        if pt.point_id not in _point_meta_cache:
            result.errors.append(f"点位 {pt.point_id} 不存在")
            continue
        meta = _point_meta_cache[pt.point_id]
        if not meta["is_enabled"]:
            continue
        if pt.timestamp is None:
            pt.timestamp = now
        valid_points.append(pt)

    if not valid_points:
        return result

    # ── Phase 1: 批量写库（单事务）──────────────────────────

    try:
        await _batch_upsert_realtime(valid_points, session, now)
        await _batch_upsert_latest(valid_points, session, now)
        await _batch_insert_history(valid_points, session, now)
        await session.commit()
        result.written = len(valid_points)
    except Exception as e:
        logger.error("入库管道写库失败: %s", e)
        await session.rollback()
        result.errors.append(f"写库失败: {e}")
        return result

    # ── Phase 2: 告警评估（提交后）──────────────────────────

    try:
        alarm_result = await _evaluate_alarms(valid_points, session)
        result.alarms_created = alarm_result["created"]
        result.alarms_resolved = alarm_result["resolved"]
    except Exception as e:
        logger.warning("入库管道告警评估失败: %s", e)

    # ── Phase 3: 副作用（WS + Redis）──────────────────────

    try:
        await _broadcast_realtime(valid_points)
    except Exception as e:
        logger.warning("入库管道 WS 广播失败: %s", e)

    try:
        await _update_redis_cache(valid_points, now)
    except Exception:
        pass  # Redis 失败不影响主流程

    return result


# ── Phase 1: 批量写库 ──────────────────────────────────────────


async def _batch_upsert_realtime(
    points: list[IngestPoint],
    session: AsyncSession,
    now: datetime,
) -> None:
    """批量 upsert PointRealtime — 使用 CASE WHEN 技术"""
    if not points:
        return

    # 状态白名单校验，避免非法值进入 SQL/缓存链路
    for pt in points:
        if pt.status not in ALLOWED_STATUS:
            logger.warning("非法状态值: %s，使用默认值 'unknown'", pt.status)
            pt.status = "unknown"

    point_ids = [pt.point_id for pt in points]

    # 查询已存在的 PointRealtime 记录
    existing_result = await session.execute(select(PointRealtime.point_id).where(PointRealtime.point_id.in_(point_ids)))
    existing_ids = {row[0] for row in existing_result.all()}

    # 分离: 需要 UPDATE 的 vs 需要 INSERT 的
    to_update = [pt for pt in points if pt.point_id in existing_ids]
    to_insert = [pt for pt in points if pt.point_id not in existing_ids]

    # 批量 UPDATE (CASE WHEN)
    if to_update:
        batch_size = 300
        for i in range(0, len(to_update), batch_size):
            batch = to_update[i : i + batch_size]
            [pt.point_id for pt in batch]

            params: dict[str, object] = {"now": now}
            value_cases_parts: list[str] = []
            quality_cases_parts: list[str] = []
            status_cases_parts: list[str] = []
            source_cases_parts: list[str] = []
            id_placeholders: list[str] = []

            for idx, pt in enumerate(batch):
                pid_key = f"pid_{idx}"
                value_key = f"value_{idx}"
                quality_key = f"quality_{idx}"
                status_key = f"status_{idx}"
                source_key = f"source_{idx}"

                params[pid_key] = pt.point_id
                params[value_key] = pt.value
                params[quality_key] = pt.quality
                params[status_key] = pt.status
                params[source_key] = pt.source

                value_cases_parts.append(f"WHEN :{pid_key} THEN :{value_key}")
                quality_cases_parts.append(f"WHEN :{pid_key} THEN :{quality_key}")
                status_cases_parts.append(f"WHEN :{pid_key} THEN :{status_key}")
                source_cases_parts.append(f"WHEN :{pid_key} THEN :{source_key}")
                id_placeholders.append(f":{pid_key}")

            sql = text(
                f"""
                UPDATE point_realtime SET
                    value = CASE point_id {" ".join(value_cases_parts)} END,
                    raw_value = CASE point_id {" ".join(value_cases_parts)} END,
                    quality = CASE point_id {" ".join(quality_cases_parts)} END,
                    status = CASE point_id {" ".join(status_cases_parts)} END,
                    source = CASE point_id {" ".join(source_cases_parts)} END,
                    updated_at = :now
                WHERE point_id IN ({", ".join(id_placeholders)})
                """
            )
            await session.execute(sql, params)

    # 批量 INSERT
    if to_insert:
        for pt in to_insert:
            meta = _point_meta_cache.get(pt.point_id, {})
            value_text = None
            if meta.get("point_type") == "DI":
                value_text = "告警" if pt.value == 1 else "正常"
            record = PointRealtime(
                point_id=pt.point_id,
                value=pt.value,
                raw_value=pt.value,
                quality=pt.quality,
                status=pt.status,
                value_text=value_text,
                source=pt.source,
            )
            session.add(record)


async def _batch_upsert_latest(
    points: list[IngestPoint],
    session: AsyncSession,
    now: datetime,
) -> None:
    """批量 upsert PointDataLatest"""
    if not points:
        return

    # 只处理有 point_key 或 gateway_id 的点（MQTT 来源）
    # 对于 demo/bridge 来源，也写入 PointDataLatest 以保持一致性
    point_keys = []
    for pt in points:
        key = pt.point_key or str(pt.point_id)
        point_keys.append(key)

    # 查询已存在的记录
    existing_result = await session.execute(
        select(PointDataLatest.point_id).where(PointDataLatest.point_id.in_(point_keys))
    )
    existing_keys = {row[0] for row in existing_result.all()}

    update_rows: list[dict[str, object]] = []
    insert_rows: list[dict[str, object]] = []

    for pt, key in zip(points, point_keys):
        row = {
            "value": str(pt.value),
            "quality": pt.quality,
            "timestamp": pt.timestamp or now,
            "gateway_id": pt.gateway_id or "",
            "source": pt.source,
            "updated_at": now,
        }
        if key in existing_keys:
            update_rows.append({"b_point_id": key, **row})
        else:
            insert_rows.append({"point_id": key, **row})

    if update_rows:
        await session.execute(
            update(PointDataLatest)
            .where(PointDataLatest.point_id == bindparam("b_point_id"))
            .values(
                value=bindparam("value"),
                quality=bindparam("quality"),
                timestamp=bindparam("timestamp"),
                gateway_id=bindparam("gateway_id"),
                source=bindparam("source"),
                updated_at=bindparam("updated_at"),
            ),
            update_rows,
        )

    if insert_rows:
        await session.execute(PointDataLatest.__table__.insert(), insert_rows)


async def _batch_insert_history(
    points: list[IngestPoint],
    session: AsyncSession,
    now: datetime,
) -> None:
    """批量插入 PointHistory（仅 AI 类型，按 store_interval 降采样）"""
    ai_points = [pt for pt in points if _point_meta_cache.get(pt.point_id, {}).get("point_type") == "AI"]
    if not ai_points:
        return

    for pt in ai_points:
        point_id = pt.point_id
        timestamp = pt.timestamp or now

        # 获取点位的 store_interval 配置
        meta = _point_meta_cache.get(point_id, {})
        store_interval = meta.get("store_interval", 300)  # 默认5分钟

        # 检查是否需要存储（降采样）
        last_stored = _last_store_time.get(point_id)
        if last_stored:
            elapsed = (timestamp - last_stored).total_seconds()
            if elapsed < store_interval:
                continue  # 跳过，未到存储间隔

        # 写入历史
        session.add(PointHistory(point_id=point_id, value=pt.value, recorded_at=timestamp, source=pt.source))
        _last_store_time[point_id] = timestamp


# ── Phase 2: 告警评估 ──────────────────────────────────────────


async def _evaluate_alarms(
    points: list[IngestPoint],
    session: AsyncSession,
) -> dict:
    """批量告警评估 — 提交后执行"""
    created_count = 0
    resolved_count = 0

    # 收集需要评估的点位（AI/DI 且质量好）
    eval_points = []
    for pt in points:
        meta = _point_meta_cache.get(pt.point_id, {})
        if meta.get("point_type") not in ("AI", "DI"):
            continue
        point_quality = alarm_engine.get_point_quality(pt.point_id)
        if point_quality >= 2:
            continue
        eval_points.append(pt)

    if not eval_points:
        return {"created": 0, "resolved": 0}

    # 批量查询所有涉及点位的活动告警
    eval_ids = [pt.point_id for pt in eval_points]
    active_result = await session.execute(select(Alarm).where(Alarm.point_id.in_(eval_ids), Alarm.status == "active"))
    active_alarms_by_point: dict[int, list] = {}
    for alarm in active_result.scalars().all():
        active_alarms_by_point.setdefault(alarm.point_id, []).append(alarm)

    # 逐点评估
    alarms_to_create: list[Alarm] = []
    alarms_to_resolve: list[Alarm] = []
    alarm_events: list[dict] = []

    for pt in eval_points:
        meta = _point_meta_cache[pt.point_id]
        triggered_list = alarm_engine.evaluate(pt.point_id, pt.value, meta["point_type"])

        if triggered_list:
            # 检查是否已有同阈值的活动告警
            existing = active_alarms_by_point.get(pt.point_id, [])
            existing_threshold_ids = {a.threshold_id for a in existing}

            device_type = meta.get("device_type")
            is_comm_suspect = alarm_engine.check_mass_alarm(device_type) if device_type else False

            for triggered in triggered_list:
                if triggered.threshold_id in existing_threshold_ids:
                    continue  # 已有活动告警

                alarm_no = f"ALM{datetime.now().strftime('%Y%m%d%H%M%S')}{uuid.uuid4().hex[:6].upper()}"
                alarm_msg = triggered.alarm_message or f"{meta['point_name']} 告警"
                if is_comm_suspect:
                    alarm_msg = f"[疑似通信异常] {alarm_msg}"

                alarm = Alarm(
                    alarm_no=alarm_no,
                    point_id=pt.point_id,
                    threshold_id=triggered.threshold_id,
                    alarm_level=triggered.alarm_level,
                    alarm_type="communication" if is_comm_suspect else "threshold",
                    alarm_message=alarm_msg,
                    trigger_value=pt.value,
                    threshold_value=triggered.threshold_value,
                    data_source=pt.source,
                )
                alarms_to_create.append(alarm)
                alarm_events.append(
                    {
                        "alarm": alarm,
                        "point_meta": meta,
                        "triggered": triggered,
                    }
                )
        else:
            # 值安全 → 自动恢复
            if alarm_engine.is_value_safe(pt.point_id, pt.value):
                for active_alarm in active_alarms_by_point.get(pt.point_id, []):
                    alarms_to_resolve.append(active_alarm)

    # 批量创建告警
    if alarms_to_create:
        for alarm in alarms_to_create:
            session.add(alarm)
        await session.flush()  # 获取告警 ID
        created_count = len(alarms_to_create)

        # 广播新告警 + 联动事件
        for evt in alarm_events:
            alarm = evt["alarm"]
            meta = evt["point_meta"]
            triggered = evt["triggered"]
            try:
                await ws_manager.broadcast_alarm(
                    {
                        "action": "new",
                        "id": alarm.id,
                        "alarm_no": alarm.alarm_no,
                        "point_id": alarm.point_id,
                        "point_code": meta["point_code"],
                        "point_name": meta["point_name"],
                        "alarm_level": alarm.alarm_level,
                        "alarm_type": alarm.alarm_type,
                        "alarm_message": alarm.alarm_message,
                        "trigger_value": alarm.trigger_value,
                        "threshold_value": alarm.threshold_value,
                        "status": "active",
                        "created_at": datetime.now().isoformat(),
                    }
                )
            except Exception as e:
                logger.warning("告警 WS 广播失败: %s", e)

            try:
                from ..engines.event_bus import get_event_bus, Event, EventPriority

                _priority_map = {
                    "critical": EventPriority.critical,
                    "major": EventPriority.critical,
                    "minor": EventPriority.normal,
                    "info": EventPriority.normal,
                }
                _evt = Event(
                    event_type="alarm.triggered",
                    source="alarm_engine",
                    priority=_priority_map.get(alarm.alarm_level, EventPriority.normal),
                    payload={
                        "alarm_id": alarm.id,
                        "alarm_no": alarm.alarm_no,
                        "alarm_level": alarm.alarm_level,
                        "alarm_type": alarm.alarm_type,
                        "alarm_message": alarm.alarm_message,
                        "point_id": alarm.point_id,
                        "trigger_value": alarm.trigger_value,
                        "threshold_value": alarm.threshold_value,
                        "threshold_type": triggered.threshold_type if triggered else "",
                        "device_type": meta.get("device_type") or "",
                        "zone": meta.get("area_code") or "default",
                    },
                )
                await get_event_bus().publish("linkage", _evt)
            except Exception as e:
                logger.warning("联动事件发布失败: %s", e)

        # Redis 告警统计递增
        if redis_service.is_available:
            for alarm in alarms_to_create:
                try:
                    key = f"alarm:stats:{alarm.alarm_level}"
                    current = await redis_service.get(key)
                    count = int(current or 0) + 1
                    await redis_service.set(key, str(count), ttl=86400)
                except Exception:
                    pass

    # 批量恢复告警
    if alarms_to_resolve:
        now = datetime.now()
        for alarm in alarms_to_resolve:
            alarm.status = "resolved"
            alarm.resolve_type = "auto"
            alarm.resolved_at = now
            if alarm.created_at:
                alarm.duration_seconds = int((now - alarm.created_at).total_seconds())
            try:
                await ws_manager.broadcast_alarm(
                    {
                        "action": "resolve",
                        "id": alarm.id,
                        "alarm_no": alarm.alarm_no,
                        "point_id": alarm.point_id,
                        "alarm_level": alarm.alarm_level,
                        "status": "resolved",
                        "resolve_type": "auto",
                        "resolved_at": now.isoformat(),
                    }
                )
            except Exception:
                pass
            # Redis 告警统计递减
            if redis_service.is_available:
                try:
                    key = f"alarm:stats:{alarm.alarm_level}"
                    current = await redis_service.get(key)
                    count = max(0, int(current or 0) - 1)
                    await redis_service.set(key, str(count), ttl=86400)
                except Exception:
                    pass
        resolved_count = len(alarms_to_resolve)

    # 提交告警变更
    if alarms_to_create or alarms_to_resolve:
        try:
            await session.commit()
        except Exception as e:
            logger.error("告警提交失败: %s", e)
            await session.rollback()
            alarm_events = []  # commit 失败，清空事件防止 dispatch 使用无效数据

    # Story 34.4: 异步通知分发（commit 成功后，构建纯数据列表）
    if alarm_events:
        import asyncio as _asyncio

        alarm_data_list = []
        for evt in alarm_events:
            _alarm = evt["alarm"]
            _meta = evt["point_meta"]
            alarm_data_list.append(
                {
                    "alarm_id": _alarm.id,
                    "alarm_level": _alarm.alarm_level,
                    "alarm_message": _alarm.alarm_message,
                    "trigger_value": _alarm.trigger_value,
                    "threshold_value": _alarm.threshold_value,
                    "created_at": _alarm.created_at,
                    "site_id": _meta.get("site_id"),
                    "site_name": _meta.get("site_name"),
                    "device_name": _meta.get("device_name"),
                    "point_name": _meta.get("point_name"),
                }
            )

        from ..services.notification import notification_dispatcher as _dispatcher

        async def _dispatch_and_update(data_list):
            """分发通知并按告警回写 is_notified + notify_count"""
            try:
                result_map = await _dispatcher.dispatch(data_list)
                notified = {aid: cnt for aid, cnt in result_map.items() if cnt > 0}
                if notified:
                    async with async_session() as _db:
                        for aid, cnt in notified.items():
                            await _db.execute(
                                update(Alarm).where(Alarm.id == aid).values(is_notified=True, notify_count=cnt)
                            )
                        await _db.commit()
            except Exception as _e:
                logger.error("通知分发异常: %s", _e, exc_info=True)

        _task = _asyncio.create_task(_dispatch_and_update(alarm_data_list))
        _dispatcher._pending_tasks.add(_task)
        _task.add_done_callback(_dispatcher._pending_tasks.discard)

    # 重置大面积告警统计
    alarm_engine.reset_cycle_stats()

    return {"created": created_count, "resolved": resolved_count}


# ── Phase 3: 副作用 ──────────────────────────────────────────


async def _broadcast_realtime(points: list[IngestPoint]) -> None:
    """批量 WebSocket 广播实时数据"""
    for pt in points:
        meta = _point_meta_cache.get(pt.point_id, {})
        data = {
            "point_id": pt.point_id,
            "point_code": meta.get("point_code", ""),
            "point_name": meta.get("point_name", ""),
            "point_type": meta.get("point_type", ""),
            "value": pt.value if meta.get("point_type") == "AI" else int(pt.value),
            "unit": meta.get("unit", ""),
            "status": pt.status,
            "source": pt.source,
            "timestamp": (pt.timestamp or datetime.now()).isoformat(),
        }
        await ws_manager.broadcast_realtime(data)


async def _update_redis_cache(points: list[IngestPoint], now: datetime) -> None:
    """批量更新 Redis 缓存"""
    if not redis_service.is_available:
        return

    for pt in points:
        meta = _point_meta_cache.get(pt.point_id, {})
        value_text = None
        if meta.get("point_type") == "DI":
            value_text = "告警" if pt.value == 1 else "正常"

        cache_data = _json.dumps(
            {
                "value": pt.value if meta.get("point_type") == "AI" else int(pt.value),
                "value_text": value_text,
                "quality": pt.quality,
                "status": pt.status,
                "source": pt.source,
                "alarm_level": None,
                "updated_at": now.isoformat(),
            }
        )
        try:
            await redis_service.set(f"point:{pt.point_id}:latest", cache_data, ttl=60)
        except Exception:
            pass

        # 设备在线状态
        device_id = meta.get("device_id")
        if device_id:
            try:
                await redis_service.set(f"device:{device_id}:online", now.isoformat(), ttl=60)
            except Exception:
                pass
