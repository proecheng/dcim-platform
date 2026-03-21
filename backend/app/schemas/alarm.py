"""
告警相关 Schema
"""

import json
from typing import Optional, Dict, List
from datetime import datetime
from pydantic import BaseModel, ConfigDict, field_validator, model_validator


class AlarmInfo(BaseModel):
    """告警信息"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    alarm_no: str
    point_id: Optional[int] = None
    point_code: Optional[str] = None
    point_name: Optional[str] = None
    alarm_level: str
    alarm_type: Optional[str] = None
    alarm_message: str
    trigger_value: Optional[float] = None
    threshold_value: Optional[float] = None
    status: str
    acknowledged_by: Optional[int] = None
    acknowledged_at: Optional[datetime] = None
    ack_remark: Optional[str] = None
    resolved_by: Optional[int] = None
    resolved_at: Optional[datetime] = None
    resolve_remark: Optional[str] = None
    resolve_type: Optional[str] = None
    duration_seconds: Optional[int] = None
    process_remark: Optional[str] = None
    processed_by: Optional[int] = None
    processed_at: Optional[datetime] = None
    escalation_count: Optional[int] = None
    escalated_from: Optional[str] = None
    escalation_remark: Optional[str] = None
    last_escalated_at: Optional[datetime] = None
    data_source: Optional[str] = None
    source: Optional[str] = None
    created_at: Optional[datetime] = None


class AlarmAcknowledge(BaseModel):
    """确认告警"""

    remark: Optional[str] = None


class AlarmResolve(BaseModel):
    """解决告警"""

    remark: Optional[str] = None
    resolve_type: str = "manual"


class AlarmProcess(BaseModel):
    """处理告警"""

    process_remark: str


class BatchAcknowledgeRequest(BaseModel):
    """批量确认告警"""

    alarm_ids: List[int]
    remark: Optional[str] = None


class AlarmCount(BaseModel):
    """告警数量统计"""

    critical: int = 0
    major: int = 0
    minor: int = 0
    info: int = 0
    total: int = 0


class AlarmStatistics(BaseModel):
    """告警统计"""

    total: int
    by_level: Dict[str, int] = {}
    by_status: Dict[str, int] = {}
    by_device_type: Dict[str, int] = {}
    avg_duration_seconds: int = 0
    start_time: datetime
    end_time: datetime


class AlarmTrend(BaseModel):
    """告警趋势"""

    date: str
    critical: int = 0
    major: int = 0
    minor: int = 0
    info: int = 0


# 向后兼容
class AlarmThresholdBase(BaseModel):
    point_id: int
    threshold_type: str
    threshold_value: float
    alarm_level: str = "minor"
    alarm_message: Optional[str] = None
    delay_seconds: int = 0


class AlarmThresholdCreate(AlarmThresholdBase):
    pass


class AlarmThresholdUpdate(BaseModel):
    threshold_type: Optional[str] = None
    threshold_value: Optional[float] = None
    alarm_level: Optional[str] = None
    alarm_message: Optional[str] = None
    delay_seconds: Optional[int] = None
    is_enabled: Optional[bool] = None


class AlarmThresholdResponse(AlarmThresholdBase):
    model_config = ConfigDict(from_attributes=True)
    id: int
    is_enabled: bool


AlarmResponse = AlarmInfo


class AlarmStats(BaseModel):
    """告警统计"""

    total: int
    active: int
    acknowledged: int
    resolved: int
    by_level: dict


# 告警规则相关 Schema
class AlarmRuleBase(BaseModel):
    """告警规则基础"""

    rule_name: str
    rule_type: str = "and"  # and/or/sequence
    condition_expr: Optional[str] = None
    alarm_level: str = "minor"  # critical/major/minor/info
    alarm_message: Optional[str] = None
    is_enabled: bool = True

    @field_validator("condition_expr", mode="before")
    @classmethod
    def validate_condition_expr(cls, v):
        """校验 condition_expr 是合法的条件树 JSON"""
        if v is None:
            return v
        if not isinstance(v, str):
            raise ValueError("condition_expr 必须是 JSON 字符串")
        try:
            parsed = json.loads(v)
        except json.JSONDecodeError:
            raise ValueError("condition_expr 不是合法的 JSON")
        # 校验顶层结构
        if not isinstance(parsed, dict):
            raise ValueError("condition_expr 必须是 JSON 对象")
        if parsed.get("type") not in ("group", "condition"):
            raise ValueError("condition_expr.type 必须是 group 或 condition")
        if parsed["type"] == "group":
            if "logic" not in parsed or parsed["logic"] not in ("AND", "OR"):
                raise ValueError("条件组的 logic 必须是 AND 或 OR")
            if "children" not in parsed or not isinstance(parsed["children"], list):
                raise ValueError("条件组必须包含 children 数组")
        return v


class AlarmRuleCreate(AlarmRuleBase):
    """创建告警规则"""

    pass


class AlarmRuleUpdate(BaseModel):
    """更新告警规则"""

    rule_name: Optional[str] = None
    rule_type: Optional[str] = None
    condition_expr: Optional[str] = None
    alarm_level: Optional[str] = None
    alarm_message: Optional[str] = None
    is_enabled: Optional[bool] = None

    @field_validator("condition_expr", mode="before")
    @classmethod
    def validate_condition_expr(cls, v):
        """校验 condition_expr 是合法的条件树 JSON"""
        if v is None:
            return v
        if not isinstance(v, str):
            raise ValueError("condition_expr 必须是 JSON 字符串")
        try:
            parsed = json.loads(v)
        except json.JSONDecodeError:
            raise ValueError("condition_expr 不是合法的 JSON")
        if not isinstance(parsed, dict):
            raise ValueError("condition_expr 必须是 JSON 对象")
        if parsed.get("type") not in ("group", "condition"):
            raise ValueError("condition_expr.type 必须是 group 或 condition")
        if parsed["type"] == "group":
            if "logic" not in parsed or parsed["logic"] not in ("AND", "OR"):
                raise ValueError("条件组的 logic 必须是 AND 或 OR")
            if "children" not in parsed or not isinstance(parsed["children"], list):
                raise ValueError("条件组必须包含 children 数组")
        return v


class AlarmRuleInfo(AlarmRuleBase):
    """告警规则信息"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: Optional[datetime] = None


# 告警屏蔽相关 Schema
class AlarmShieldBase(BaseModel):
    """告警屏蔽基础"""

    point_id: Optional[int] = None  # 空表示全局屏蔽
    alarm_level: Optional[str] = None  # 空表示屏蔽全部级别
    start_time: datetime
    end_time: datetime
    reason: Optional[str] = None


class AlarmShieldCreate(AlarmShieldBase):
    """创建告警屏蔽"""

    pass


class AlarmShieldInfo(AlarmShieldBase):
    """告警屏蔽信息"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    created_by: Optional[int] = None
    created_at: Optional[datetime] = None
    # 关联信息
    point_code: Optional[str] = None
    point_name: Optional[str] = None
    creator_name: Optional[str] = None
    # 状态（前端计算）
    status: Optional[str] = None  # active(生效中) / expired(已过期)


# 告警升级相关 Schema
LEVEL_ORDER = {"info": 0, "minor": 1, "major": 2, "critical": 3}


class AlarmEscalationBase(BaseModel):
    """告警升级规则基础"""

    rule_name: str
    source_level: str
    timeout_minutes: int
    target_level: str
    notify_user_ids: List[int] = []
    is_enabled: bool = True
    description: Optional[str] = None
    escalation_chain: Optional[str] = None

    @model_validator(mode="after")
    def validate_level_order(self):
        """target_level 必须高于 source_level"""
        src = LEVEL_ORDER.get(self.source_level, -1)
        tgt = LEVEL_ORDER.get(self.target_level, -1)
        if src >= 0 and tgt >= 0 and tgt <= src:
            raise ValueError(f"升级后级别({self.target_level})必须高于源级别({self.source_level})")
        return self


class AlarmEscalationCreate(AlarmEscalationBase):
    """创建告警升级规则"""

    pass


class AlarmEscalationUpdate(BaseModel):
    """更新告警升级规则"""

    rule_name: Optional[str] = None
    source_level: Optional[str] = None
    timeout_minutes: Optional[int] = None
    target_level: Optional[str] = None
    notify_user_ids: Optional[List[int]] = None
    is_enabled: Optional[bool] = None
    description: Optional[str] = None
    escalation_chain: Optional[str] = None


class AlarmEscalationInfo(AlarmEscalationBase):
    """告警升级规则信息"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    @field_validator("notify_user_ids", mode="before")
    @classmethod
    def parse_notify_ids(cls, v):
        if isinstance(v, str):
            return [int(x.strip()) for x in v.split(",") if x.strip()] if v else []
        return v or []
