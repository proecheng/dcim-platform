"""
通知渠道配置 API
Story 34.2 — 通知渠道适配器框架
Story 34.7 — 新增 GET /records 通知记录查询
"""

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, require_role, require_viewer
from app.models.alarm import Alarm
from app.models.notification_record import NotificationRecord
from app.schemas.notification import (
    AlarmNotificationContext,
    ChannelStatusInfo,
    ChannelTestRequest,
    ChannelTestResponse,
    get_subject_for_channel,
    get_template_for_channel,
    render_notification,
)
from app.schemas.notification_record import NotificationRecordInfo
from app.services.notification.adapters import ADAPTER_REGISTRY

router = APIRouter()

require_admin = require_role(["admin"])


@router.get(
    "/channels",
    response_model=list[ChannelStatusInfo],
    summary="查询所有通知渠道状态",
)
async def get_channel_status(_=Depends(require_admin)):
    results = []
    for channel_type, adapter in ADAPTER_REGISTRY.items():
        healthy = False
        try:
            healthy = await adapter.health_check()
        except Exception:
            pass
        results.append(
            ChannelStatusInfo(
                channel_type=channel_type,
                enabled=adapter.is_enabled(),
                healthy=healthy,
            )
        )
    return results


@router.post(
    "/channels/test",
    response_model=ChannelTestResponse,
    summary="测试发送通知",
)
async def test_send_notification(
    data: ChannelTestRequest,
    _=Depends(require_admin),
):
    adapter = ADAPTER_REGISTRY.get(data.channel_type)
    if not adapter:
        return ChannelTestResponse(
            success=False, error_message=f"渠道 {data.channel_type} 未注册"
        )
    if not adapter.is_enabled():
        return ChannelTestResponse(
            success=False, error_message=f"渠道 {data.channel_type} 未启用"
        )

    # 构造测试上下文
    test_context = AlarmNotificationContext(
        alarm_id=0,
        alarm_level="info",
        alarm_message="这是一条测试通知",
        device_name="测试设备",
        point_name="测试点位",
        current_value=25.0,
        threshold_value=30.0,
        site_id=None,
        site_name="测试站点",
        created_at=datetime.now(),
    )
    subject = render_notification(
        get_subject_for_channel(data.channel_type), test_context
    )
    content = render_notification(
        get_template_for_channel(data.channel_type), test_context
    )

    result = await adapter.send(data.contact_value, subject, content, test_context)
    return ChannelTestResponse(
        success=result.success, error_message=result.error_message
    )


@router.get("/records", summary="查询通知记录")
async def list_notification_records(
    channel_type: Optional[str] = None,
    status: Optional[str] = None,
    alarm_level: Optional[str] = None,
    start_time: Optional[datetime] = None,
    end_time: Optional[datetime] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user=Depends(require_viewer),
    session: AsyncSession = Depends(get_db),
):
    """分页查询通知记录，支持多维度筛选"""
    # 基础查询 — outerjoin Alarm 获取 alarm_level
    query = (
        select(
            NotificationRecord,
            Alarm.alarm_level.label("alarm_level"),
        )
        .outerjoin(Alarm, NotificationRecord.alarm_id == Alarm.id)
        .order_by(NotificationRecord.id.desc())
    )

    if channel_type:
        query = query.where(NotificationRecord.channel_type == channel_type)
    if status:
        query = query.where(NotificationRecord.status == status)
    if alarm_level:
        query = query.where(Alarm.alarm_level == alarm_level)
    if start_time:
        query = query.where(NotificationRecord.created_at >= start_time)
    if end_time:
        query = query.where(NotificationRecord.created_at <= end_time)

    # 总数
    count_query = select(func.count()).select_from(query.subquery())
    total = (await session.execute(count_query)).scalar() or 0

    # 分页
    result = await session.execute(
        query.offset((page - 1) * page_size).limit(page_size)
    )
    rows = result.all()

    items = []
    for record, al_level in rows:
        items.append(
            NotificationRecordInfo(
                id=record.id,
                alarm_id=record.alarm_id,
                alarm_level=al_level,
                user_id=record.user_id,
                policy_id=record.policy_id,
                channel_type=record.channel_type,
                platform=record.platform,
                contact_value=record.contact_value,
                content_summary=record.content_summary,
                status=record.status,
                retry_count=record.retry_count,
                error_message=record.error_message,
                sent_at=record.sent_at,
                created_at=record.created_at,
            )
        )

    return {"items": items, "total": total, "page": page, "page_size": page_size}
