"""
通知 Schema + 消息模板
Story 34.2 — 通知渠道适配器框架
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


# ==================== AlarmNotificationContext DTO ====================

@dataclass
class AlarmNotificationContext:
    """通知上下文 DTO — 避免跨层传递 ORM 对象"""
    alarm_id: int
    alarm_level: str
    alarm_message: str
    device_name: Optional[str]
    point_name: Optional[str]
    current_value: Optional[float]
    threshold_value: Optional[float]
    site_id: Optional[int]
    site_name: Optional[str]
    created_at: datetime


# ==================== 告警级别中文映射 ====================

ALARM_LEVEL_CN = {
    "critical": "紧急",
    "major": "重要",
    "minor": "次要",
    "info": "信息",
}


# ==================== 消息模板 ====================

SMS_TEMPLATE = "[DCIM] {site_name} {alarm_level_cn}告警: {device_name}/{point_name} 当前值{current_value}"

EMAIL_SUBJECT_TEMPLATE = "[DCIM告警] {site_name} - {alarm_level_cn}: {device_name}"

EMAIL_BODY_TEMPLATE = """<html><body>
<h3 style="color:#e74c3c">⚠️ {alarm_level_cn}告警</h3>
<table border="1" cellpadding="8" cellspacing="0" style="border-collapse:collapse">
<tr><td><b>站点</b></td><td>{site_name}</td></tr>
<tr><td><b>设备</b></td><td>{device_name}</td></tr>
<tr><td><b>点位</b></td><td>{point_name}</td></tr>
<tr><td><b>当前值</b></td><td>{current_value}</td></tr>
<tr><td><b>阈值</b></td><td>{threshold_value}</td></tr>
<tr><td><b>时间</b></td><td>{created_at}</td></tr>
<tr><td><b>详情</b></td><td>{alarm_message}</td></tr>
</table>
</body></html>"""

IM_MARKDOWN_TEMPLATE = """### ⚠️ {alarm_level_cn}告警
- **站点：** {site_name}
- **设备：** {device_name}
- **点位：** {point_name}
- **当前值：** {current_value}
- **阈值：** {threshold_value}
- **时间：** {created_at}
- **详情：** {alarm_message}"""

VOICE_TTS_TEMPLATE = "{site_name}发生{alarm_level_cn}告警，设备{device_name}，点位{point_name}，当前值{current_value}，请及时处理。"

# 渠道 → 内容模板
_CHANNEL_CONTENT_TEMPLATES = {
    "sms": SMS_TEMPLATE,
    "email": EMAIL_BODY_TEMPLATE,
    "im": IM_MARKDOWN_TEMPLATE,
    "voice": VOICE_TTS_TEMPLATE,
}

# 渠道 → 主题模板
_CHANNEL_SUBJECT_TEMPLATES = {
    "sms": SMS_TEMPLATE,
    "email": EMAIL_SUBJECT_TEMPLATE,
    "im": EMAIL_SUBJECT_TEMPLATE,
    "voice": VOICE_TTS_TEMPLATE,
}


def get_template_for_channel(channel_type: str) -> str:
    return _CHANNEL_CONTENT_TEMPLATES.get(channel_type, SMS_TEMPLATE)


def get_subject_for_channel(channel_type: str) -> str:
    return _CHANNEL_SUBJECT_TEMPLATES.get(channel_type, SMS_TEMPLATE)


def render_notification(template: str, context: AlarmNotificationContext) -> str:
    """渲染消息模板，None 值替换为'未知'"""
    values = {
        "alarm_id": context.alarm_id,
        "alarm_level": context.alarm_level,
        "alarm_level_cn": ALARM_LEVEL_CN.get(context.alarm_level, context.alarm_level),
        "alarm_message": context.alarm_message or "未知",
        "device_name": context.device_name or "未知",
        "point_name": context.point_name or "未知",
        "current_value": context.current_value if context.current_value is not None else "未知",
        "threshold_value": context.threshold_value if context.threshold_value is not None else "未知",
        "site_id": context.site_id or "",
        "site_name": context.site_name or "未知",
        "created_at": context.created_at.strftime("%Y-%m-%d %H:%M:%S") if context.created_at else "未知",
    }
    return template.format(**values)


# ==================== 风暴摘要模板 (Story 34.6) ====================

STORM_SUMMARY_TEMPLATE = (
    "[告警风暴] {site_name} 在 {window}s 内触发 {total_count} 条告警\n"
    "级别分布: {level_summary}\n"
    "{critical_detail}"
)


def build_storm_summary(
    site_name: str,
    alarm_data_list: list[dict],
    window: int,
) -> str:
    """构建风暴摘要通知内容。window 必传，从 StormDetector.get_config() 获取。"""
    from collections import Counter

    level_counter = Counter(d["alarm_level"] for d in alarm_data_list)
    level_summary = ", ".join(
        f"{ALARM_LEVEL_CN.get(k, k)} {v}条" for k, v in level_counter.most_common()
    )

    critical_detail = ""
    critical_alarms = [d for d in alarm_data_list if d["alarm_level"] == "critical"]
    if critical_alarms:
        devices = set(d.get("device_name") or "未知设备" for d in critical_alarms)
        critical_detail = f"⚠ 紧急告警 {len(critical_alarms)} 条，涉及设备: {', '.join(sorted(devices)[:5])}\n"

    return STORM_SUMMARY_TEMPLATE.format(
        site_name=site_name or "未知站点",
        window=window,
        total_count=len(alarm_data_list),
        level_summary=level_summary,
        critical_detail=critical_detail,
    )


# ==================== API Schema ====================

class ChannelTestRequest(BaseModel):
    channel_type: str = Field(..., pattern="^(sms|im|voice|email)$")
    contact_value: str = Field(..., min_length=1, max_length=200)


class ChannelTestResponse(BaseModel):
    success: bool
    error_message: Optional[str] = None


class ChannelStatusInfo(BaseModel):
    channel_type: str
    enabled: bool
    healthy: bool
