"""
通知渠道配置 API
Story 34.2 — 通知渠道适配器框架
"""

from datetime import datetime

from fastapi import APIRouter, Depends

from app.api.deps import require_role
from app.schemas.notification import (
    AlarmNotificationContext,
    ChannelStatusInfo,
    ChannelTestRequest,
    ChannelTestResponse,
    get_subject_for_channel,
    get_template_for_channel,
    render_notification,
)
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
