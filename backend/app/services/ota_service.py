"""OTA 升级服务 — Story 15.5"""
import asyncio
import json
import logging
import math
import uuid
from datetime import datetime
from typing import Callable, Coroutine, Optional

from sqlalchemy import select, update, func
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.gateway import Gateway, FirmwarePackage, OtaTask, OtaTaskGateway

logger = logging.getLogger(__name__)

# 单个网关升级超时（秒）
GATEWAY_UPGRADE_TIMEOUT = 600
# 批次失败率阈值，超过则自动暂停任务
BATCH_FAIL_THRESHOLD = 0.3
# 合法的网关 OTA 状态值
VALID_GW_STATUSES = {"downloading", "installing", "verifying", "success", "failed", "rollback"}


class OtaService:
    """OTA 升级核心服务"""

    async def create_task(
        self,
        firmware_id: int,
        gateway_ids: list[int],
        strategy: str,
        batch_size: int,
        batch_interval: int,
        canary_percent: int,
        created_by: Optional[str],
        db: AsyncSession,
    ) -> OtaTask:
        """创建升级任务 — 验证固件、分配批次、写入数据库"""
        # 验证固件包存在且可用
        fw_result = await db.execute(
            select(FirmwarePackage).where(
                FirmwarePackage.id == firmware_id,
                FirmwarePackage.is_active == True,  # noqa: E712
            )
        )
        firmware = fw_result.scalar_one_or_none()
        if not firmware:
            raise ValueError(f"固件包不存在或已禁用: id={firmware_id}")

        # 验证目标网关存在且在线
        gw_result = await db.execute(
            select(Gateway).where(Gateway.id.in_(gateway_ids))
        )
        gateways = gw_result.scalars().all()
        if not gateways:
            raise ValueError("未找到任何目标网关")

        found_ids = {gw.id for gw in gateways}
        missing = set(gateway_ids) - found_ids
        if missing:
            raise ValueError(f"网关不存在: {missing}")

        # 检查版本兼容性（min_version）
        if firmware.min_version:
            incompatible = [
                gw.gateway_id for gw in gateways
                if gw.version and self._version_lt(gw.version, firmware.min_version)
            ]
            if incompatible:
                raise ValueError(
                    f"网关版本不兼容 (需 >= {firmware.min_version}): {incompatible}"
                )

        # 创建任务
        task_id = str(uuid.uuid4())[:12]
        task = OtaTask(
            task_id=task_id,
            firmware_id=firmware_id,
            target_version=firmware.version,
            strategy=strategy,
            batch_size=batch_size,
            batch_interval=batch_interval,
            canary_percent=canary_percent,
            status="pending",
            total_gateways=len(gateways),
            created_by=created_by,
        )
        db.add(task)
        await db.flush()

        # 分配批次
        batch_assignments = self._assign_batches(
            gateways, strategy, batch_size, canary_percent
        )

        for gw, batch_idx in batch_assignments:
            tg = OtaTaskGateway(
                task_id=task_id,
                gateway_id=gw.gateway_id,
                batch_index=batch_idx,
                status="pending",
                old_version=gw.version,
            )
            db.add(tg)

        await db.commit()
        logger.info(
            "OTA 任务已创建: task_id=%s, firmware=%s, gateways=%d, strategy=%s",
            task_id, firmware.version, len(gateways), strategy,
        )
        return task

    async def start_task(
        self,
        task_id: str,
        mqtt_publish_fn: Callable[..., Coroutine],
        db: AsyncSession,
    ) -> None:
        """启动任务 — 发送第一批次的 MQTT 指令"""
        task = await self._get_task(task_id, db)
        if task.status != "pending":
            raise ValueError(f"任务状态不允许启动: {task.status}")

        await db.execute(
            update(OtaTask).where(OtaTask.task_id == task_id).values(
                status="running", updated_at=datetime.now()
            )
        )
        await db.commit()

        await self._dispatch_batch(task_id, 0, mqtt_publish_fn, db)

    async def handle_ota_status(self, payload: dict, db: AsyncSession) -> None:
        """处理网关上报的 OTA 状态"""
        task_id = payload.get("task_id")
        gw_id = payload.get("gw_id")
        status = payload.get("status")
        progress = payload.get("progress", 0)
        error = payload.get("error")

        if not task_id or not gw_id or not status:
            logger.warning("OTA 状态消息缺少必要字段: %s", payload)
            return

        if status not in VALID_GW_STATUSES:
            logger.warning("无效的 OTA 状态值: %s (task=%s, gw=%s)", status, task_id, gw_id)
            return

        # 更新网关升级状态
        now = datetime.now()
        update_values: dict = {
            "status": status,
            "progress": progress,
            "updated_at": now,
        }
        if error:
            update_values["error_message"] = str(error)[:500]

        # 标记开始/完成时间
        if status == "downloading":
            update_values["started_at"] = now
        elif status in ("success", "failed", "rollback"):
            update_values["completed_at"] = now

        await db.execute(
            update(OtaTaskGateway).where(
                OtaTaskGateway.task_id == task_id,
                OtaTaskGateway.gateway_id == gw_id,
            ).values(**update_values)
        )

        # 更新任务级别的成功/失败计数
        if status == "success":
            await db.execute(
                update(OtaTask).where(OtaTask.task_id == task_id).values(
                    success_count=OtaTask.success_count + 1,
                    updated_at=now,
                )
            )
            # 更新网关版本
            task_result = await db.execute(
                select(OtaTask).where(OtaTask.task_id == task_id)
            )
            task = task_result.scalar_one_or_none()
            if task:
                await db.execute(
                    update(Gateway).where(Gateway.gateway_id == gw_id).values(
                        version=task.target_version, updated_at=now,
                    )
                )
        elif status in ("failed", "rollback"):
            await db.execute(
                update(OtaTask).where(OtaTask.task_id == task_id).values(
                    fail_count=OtaTask.fail_count + 1,
                    updated_at=now,
                )
            )

        await db.commit()

        # 检查当前批次是否完成
        if status in ("success", "failed", "rollback"):
            # 通过 lazy import 获取 mqtt_publish_fn 以支持批次推进
            try:
                from ..mqtt import mqtt_service
                publish_fn = mqtt_service.publish
            except Exception:
                publish_fn = None
            await self._check_batch_completion(task_id, db, mqtt_publish_fn=publish_fn)

        logger.debug(
            "OTA 状态更新: task=%s, gw=%s, status=%s, progress=%d",
            task_id, gw_id, status, progress,
        )

    async def cancel_task(
        self,
        task_id: str,
        mqtt_publish_fn: Callable[..., Coroutine],
        db: AsyncSession,
    ) -> None:
        """取消任务 — 向未完成网关发送 cancel 指令"""
        task = await self._get_task(task_id, db)
        if task.status in ("completed", "cancelled"):
            raise ValueError(f"任务已结束: {task.status}")

        # 查找未完成的网关
        result = await db.execute(
            select(OtaTaskGateway).where(
                OtaTaskGateway.task_id == task_id,
                OtaTaskGateway.status.in_(["pending", "downloading", "installing", "verifying"]),
            )
        )
        pending_gws = result.scalars().all()

        # 发送取消指令
        for tg in pending_gws:
            gw_result = await db.execute(
                select(Gateway).where(Gateway.gateway_id == tg.gateway_id)
            )
            gw = gw_result.scalar_one_or_none()
            if gw:
                topic = f"dcim/{gw.site_id}/gw/{gw.gateway_id}/ota"
                cancel_payload = json.dumps({
                    "task_id": task_id,
                    "action": "cancel",
                })
                try:
                    await mqtt_publish_fn(topic, cancel_payload, qos=2)
                except Exception as e:
                    logger.warning("取消指令发送失败: gw=%s, err=%s", tg.gateway_id, e)

            # 标记为 cancelled（不计入 fail_count）
            await db.execute(
                update(OtaTaskGateway).where(
                    OtaTaskGateway.id == tg.id
                ).values(status="cancelled", error_message="任务已取消", completed_at=datetime.now())
            )

        await db.execute(
            update(OtaTask).where(OtaTask.task_id == task_id).values(
                status="cancelled", updated_at=datetime.now()
            )
        )
        await db.commit()
        logger.info("OTA 任务已取消: %s (%d 个网关)", task_id, len(pending_gws))

    async def pause_task(self, task_id: str, db: AsyncSession) -> None:
        """暂停任务 — 停止发送后续批次"""
        task = await self._get_task(task_id, db)
        if task.status != "running":
            raise ValueError(f"只能暂停运行中的任务: {task.status}")

        await db.execute(
            update(OtaTask).where(OtaTask.task_id == task_id).values(
                status="paused", updated_at=datetime.now()
            )
        )
        await db.commit()
        logger.info("OTA 任务已暂停: %s", task_id)

    async def resume_task(
        self,
        task_id: str,
        mqtt_publish_fn: Callable[..., Coroutine],
        db: AsyncSession,
    ) -> None:
        """恢复任务 — 继续发送下一批次"""
        task = await self._get_task(task_id, db)
        if task.status != "paused":
            raise ValueError(f"只能恢复已暂停的任务: {task.status}")

        await db.execute(
            update(OtaTask).where(OtaTask.task_id == task_id).values(
                status="running", updated_at=datetime.now()
            )
        )
        await db.commit()

        # 找到下一个未完成的批次
        next_batch = await self._find_next_pending_batch(task_id, db)
        if next_batch is not None:
            await self._dispatch_batch(task_id, next_batch, mqtt_publish_fn, db)
        else:
            # 所有批次已完成
            await self._finalize_task(task_id, db)

    async def _dispatch_batch(
        self,
        task_id: str,
        batch_index: int,
        mqtt_publish_fn: Callable[..., Coroutine],
        db: AsyncSession,
    ) -> None:
        """发送一个批次的升级指令"""
        # 获取固件信息
        task_result = await db.execute(
            select(OtaTask).where(OtaTask.task_id == task_id)
        )
        task = task_result.scalar_one()
        fw_result = await db.execute(
            select(FirmwarePackage).where(FirmwarePackage.id == task.firmware_id)
        )
        firmware = fw_result.scalar_one()

        # 获取该批次的网关
        tg_result = await db.execute(
            select(OtaTaskGateway).where(
                OtaTaskGateway.task_id == task_id,
                OtaTaskGateway.batch_index == batch_index,
                OtaTaskGateway.status == "pending",
            )
        )
        task_gateways = tg_result.scalars().all()

        if not task_gateways:
            logger.info("批次 %d 无待升级网关, task=%s", batch_index, task_id)
            return

        upgrade_payload = {
            "task_id": task_id,
            "action": "upgrade",
            "firmware": {
                "version": firmware.version,
                "download_url": firmware.download_url,
                "checksum_sha256": firmware.checksum_sha256,
                "file_size": firmware.file_size,
            },
        }
        payload_str = json.dumps(upgrade_payload)

        for tg in task_gateways:
            gw_result = await db.execute(
                select(Gateway).where(Gateway.gateway_id == tg.gateway_id)
            )
            gw = gw_result.scalar_one_or_none()
            if not gw:
                continue

            topic = f"dcim/{gw.site_id}/gw/{gw.gateway_id}/ota"
            try:
                await mqtt_publish_fn(topic, payload_str, qos=2)
                logger.info("OTA 指令已发送: gw=%s, topic=%s", tg.gateway_id, topic)
            except Exception as e:
                logger.error("OTA 指令发送失败: gw=%s, err=%s", tg.gateway_id, e)
                await db.execute(
                    update(OtaTaskGateway).where(
                        OtaTaskGateway.id == tg.id
                    ).values(
                        status="failed",
                        error_message=f"MQTT 发送失败: {e}"[:500],
                        completed_at=datetime.now(),
                    )
                )
                await db.execute(
                    update(OtaTask).where(OtaTask.task_id == task_id).values(
                        fail_count=OtaTask.fail_count + 1,
                        updated_at=datetime.now(),
                    )
                )

        await db.commit()
        logger.info(
            "OTA 批次 %d 已发送: task=%s, count=%d",
            batch_index, task_id, len(task_gateways),
        )

    async def _check_batch_completion(
        self,
        task_id: str,
        db: AsyncSession,
        mqtt_publish_fn: Optional[Callable[..., Coroutine]] = None,
    ) -> None:
        """检查当前批次是否全部完成，决定是否发送下一批"""
        task = await self._get_task(task_id, db)
        if task.status != "running":
            return

        # 统计当前进行中的网关
        in_progress_result = await db.execute(
            select(func.count()).select_from(OtaTaskGateway).where(
                OtaTaskGateway.task_id == task_id,
                OtaTaskGateway.status.in_(["downloading", "installing", "verifying"]),
            )
        )
        in_progress = in_progress_result.scalar() or 0

        if in_progress > 0:
            return  # 还有网关在升级中

        # 检查失败率
        total = task.total_gateways or 1
        fail_rate = (task.fail_count or 0) / total
        if fail_rate >= BATCH_FAIL_THRESHOLD:
            await db.execute(
                update(OtaTask).where(OtaTask.task_id == task_id).values(
                    status="paused", updated_at=datetime.now()
                )
            )
            await db.commit()
            logger.warning(
                "OTA 任务自动暂停: task=%s, 失败率=%.1f%% >= %.1f%%",
                task_id, fail_rate * 100, BATCH_FAIL_THRESHOLD * 100,
            )
            return

        # 找下一个待处理批次
        next_batch = await self._find_next_pending_batch(task_id, db)
        if next_batch is not None:
            if mqtt_publish_fn:
                await self._dispatch_batch(task_id, next_batch, mqtt_publish_fn, db)
            else:
                logger.warning(
                    "无法触发下一批次: mqtt_publish_fn 不可用, task=%s, batch=%d",
                    task_id, next_batch,
                )
        else:
            await self._finalize_task(task_id, db)

    async def _finalize_task(self, task_id: str, db: AsyncSession) -> None:
        """完成任务 — 根据结果设置最终状态"""
        task = await self._get_task(task_id, db)
        final_status = "completed" if (task.fail_count or 0) == 0 else "failed"
        await db.execute(
            update(OtaTask).where(OtaTask.task_id == task_id).values(
                status=final_status, updated_at=datetime.now()
            )
        )
        await db.commit()
        logger.info(
            "OTA 任务完成: task=%s, status=%s, success=%d, fail=%d",
            task_id, final_status, task.success_count or 0, task.fail_count or 0,
        )

    async def _get_task(self, task_id: str, db: AsyncSession) -> OtaTask:
        """获取任务，不存在则抛异常"""
        result = await db.execute(
            select(OtaTask).where(OtaTask.task_id == task_id)
        )
        task = result.scalar_one_or_none()
        if not task:
            raise ValueError(f"OTA 任务不存在: {task_id}")
        return task

    async def _find_next_pending_batch(
        self, task_id: str, db: AsyncSession
    ) -> Optional[int]:
        """找到下一个有 pending 网关的最小批次号"""
        result = await db.execute(
            select(func.min(OtaTaskGateway.batch_index)).where(
                OtaTaskGateway.task_id == task_id,
                OtaTaskGateway.status == "pending",
            )
        )
        return result.scalar()

    @staticmethod
    def _parse_version(v: str) -> tuple:
        """将版本字符串解析为可比较的整数元组"""
        try:
            return tuple(int(x) for x in v.split("."))
        except (ValueError, AttributeError):
            return (0,)

    @staticmethod
    def _version_lt(a: str, b: str) -> bool:
        """语义版本比较: a < b"""
        return OtaService._parse_version(a) < OtaService._parse_version(b)

    @staticmethod
    def _assign_batches(
        gateways: list,
        strategy: str,
        batch_size: int,
        canary_percent: int,
    ) -> list[tuple]:
        """分配批次 — 返回 [(gateway, batch_index), ...]"""
        if strategy == "immediate" or len(gateways) <= 1:
            return [(gw, 0) for gw in gateways]

        if strategy == "canary":
            canary_count = max(1, math.ceil(len(gateways) * canary_percent / 100))
            result = []
            for i, gw in enumerate(gateways):
                batch_idx = 0 if i < canary_count else 1
                result.append((gw, batch_idx))
            return result

        # batch 策略
        if batch_size <= 0:
            batch_size = len(gateways)
        result = []
        for i, gw in enumerate(gateways):
            batch_idx = i // batch_size
            result.append((gw, batch_idx))
        return result


# 模块级单例
ota_service = OtaService()
