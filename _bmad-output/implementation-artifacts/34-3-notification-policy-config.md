# Story 34.3: 通知策略配置

Status: ready-for-dev

## Story

As a 运维管理员,
I want 按告警级别、站点、时段配置通知策略,
So that 不同场景下使用最合适的通知方式。

## Acceptance Criteria

1. **Given** 管理员创建通知策略 **When** 指定站点、级别、时段、渠道、通知对象 **Then** 校验 notify_user_ids 中所有用户在 `UserSite` 表有该站点记录（全局策略 site_id=NULL 跳过校验），校验通过后保存
2. **Given** 创建策略时段与同站点+同级别已有策略重叠 **When** 保存 **Then** 校验失败，返回 422 提示"与策略X时段重叠"；跨午夜时段（start > end）正确处理
3. **Given** 全局默认策略（is_default=True） **When** 管理员尝试删除 **Then** 返回 400 阻止删除，提示"全局默认策略不可删除"
4. **Given** 系统初始化 **When** 数据库无默认策略 **Then** 自动 seed 4 条全局默认策略（每级别一条，site_id=NULL, is_default=True）
5. **Given** CRUD 操作 **When** 管理员创建/查询/更新/删除策略 **Then** API 正常工作，返回正确的响应

## Tasks / Subtasks

- [ ] Task 1: NotificationPolicy 数据模型 (AC: #1, #4)
  - [ ] 1.1 创建 `backend/app/models/notification_policy.py` — ORM 模型
  - [ ] 1.2 更新 `backend/app/models/__init__.py` — 注册模型
  - [ ] 1.3 创建 Alembic 迁移脚本
- [ ] Task 2: Pydantic Schema (AC: #1, #2, #5)
  - [ ] 2.1 创建 `backend/app/schemas/notification_policy.py`
- [ ] Task 3: 策略服务层 — 时段冲突检测 + 站点权限校验 (AC: #1, #2, #3)
  - [ ] 3.1 创建 `backend/app/services/notification/policy_service.py`
- [ ] Task 4: CRUD API 端点 (AC: #1~#5)
  - [ ] 4.1 创建 `backend/app/api/v1/notification_policy.py`
  - [ ] 4.2 更新 `backend/app/api/v1/__init__.py` — 注册路由
- [ ] Task 5: 种子数据 (AC: #4)
  - [ ] 5.1 在迁移脚本中 seed 4 条默认策略
- [ ] Task 6: 自动化测试 (AC: #1~#5)
  - [ ] 6.1 创建 `backend/tests/api/test_notification_policy.py`

## Dev Notes

### 数据模型

**NotificationPolicy 表** — 新建文件 `backend/app/models/notification_policy.py`

```python
from datetime import datetime
from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, Index, JSON, Text
from app.core.database import Base

class NotificationPolicy(Base):
    __tablename__ = "notification_policies"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100), nullable=False, comment="策略名称")
    site_id = Column(Integer, ForeignKey("sites.id", ondelete="CASCADE"), nullable=True, comment="站点ID, NULL=全局默认")
    alarm_level = Column(String(20), nullable=False, comment="告警级别: critical|major|minor|info")
    time_range_start = Column(String(5), nullable=True, comment="时段开始 HH:MM, NULL=全天")
    time_range_end = Column(String(5), nullable=True, comment="时段结束 HH:MM")
    channels = Column(JSON, nullable=False, comment='渠道组合: ["im","sms"]')
    notify_user_ids = Column(JSON, nullable=False, comment="通知对象: [1,2,3]")
    channel_escalation_enabled = Column(Boolean, default=False, nullable=False, comment="是否启用渠道升级")
    escalation_timeout_minutes = Column(Integer, default=5, nullable=False, comment="渠道升级超时(分钟)")
    escalation_channel_order = Column(JSON, nullable=True, comment='升级顺序: ["im","sms","voice"]')
    is_enabled = Column(Boolean, default=True, nullable=False, comment="是否启用")
    is_default = Column(Boolean, default=False, nullable=False, comment="是否为系统默认(不可删除)")
    created_at = Column(DateTime, default=datetime.now, comment="创建时间")
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now, comment="更新时间")

    __table_args__ = (
        Index("ix_np_site_level", "site_id", "alarm_level"),
    )
```

**关键约束：**
- `site_id=NULL` 表示全局默认策略
- `time_range_start=NULL` 且 `time_range_end=NULL` 表示全天有效
- `channels` 为 JSON 数组，值为 `["sms", "im", "voice", "email"]` 的子集
- `notify_user_ids` 为 JSON 数组，值为用户 ID 列表
- `is_default=True` 的策略不可删除

**跨午夜时段处理：**
- `time_range_start > time_range_end` 表示跨午夜（如 "22:00" ~ "06:00"）
- 匹配逻辑：`current_time >= start OR current_time < end`
- 冲突检测：将 HH:MM 转为分钟数（0~1439），跨午夜拆为两段 [start, 1440) + [0, end)，用分钟区间做重叠判断，避免字符串比较的边界问题

**分钟转换辅助函数：**
- `_to_minutes("HH:MM") -> int`：将 "22:00" 转为 1320
- 普通时段 [start_min, end_min)，跨午夜拆为 [start_min, 1440) + [0, end_min)
- 两区间重叠判定：`a_start < b_end and b_start < a_end`

[Source: architecture.md#Section 22.2, epics.md#Story 34.3]

### Schema

```python
# backend/app/schemas/notification_policy.py

class NotificationPolicyCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    site_id: Optional[int] = None
    alarm_level: str = Field(..., pattern="^(critical|major|minor|info)$")
    time_range_start: Optional[str] = Field(None, pattern="^([01]\\d|2[0-3]):[0-5]\\d$")
    time_range_end: Optional[str] = Field(None, pattern="^([01]\\d|2[0-3]):[0-5]\\d$")
    channels: list[str]  # model_validator 校验值在 {"sms","im","voice","email"} 中
    notify_user_ids: list[int] = Field(default_factory=list)  # 允许空数组（种子数据/待配置场景）
    channel_escalation_enabled: bool = False
    escalation_timeout_minutes: int = Field(5, ge=1, le=60)
    escalation_channel_order: Optional[list[str]] = None
    is_enabled: bool = True

    @model_validator(mode="after")
    def validate_all(self):
        # 1. time_range_start 和 time_range_end 必须同时有值或同时为 None
        # 2. start == end 时拒绝（零长度时段无意义）
        # 3. channels 值校验：每个值必须在 {"sms","im","voice","email"} 中，且不能为空列表
        # 4. channel_escalation_enabled=True 时 escalation_channel_order 必填且值合法
        ...

class NotificationPolicyUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    time_range_start: Optional[str] = Field(None, pattern="^([01]\\d|2[0-3]):[0-5]\\d$")
    time_range_end: Optional[str] = Field(None, pattern="^([01]\\d|2[0-3]):[0-5]\\d$")
    channels: Optional[list[str]] = None
    notify_user_ids: Optional[list[int]] = None
    channel_escalation_enabled: Optional[bool] = None
    escalation_timeout_minutes: Optional[int] = Field(None, ge=1, le=60)
    escalation_channel_order: Optional[list[str]] = None
    is_enabled: Optional[bool] = None

    @model_validator(mode="after")
    def validate_update_fields(self):
        # 1. channels 值校验：如果提供了 channels，每个值必须在 {"sms","im","voice","email"} 中
        # 2. 服务层使用 self.model_fields_set 区分"未提供"与"显式传 None"
        #    - 字段名在 model_fields_set 中 → 客户端显式提供了该值
        #    - 字段名不在 model_fields_set 中 → 客户端未提供，保留 DB 现有值
        # 3. 时段合并：服务层将未提供的 time_range_start/end 用 DB 现有值填充后再校验
        # 4. escalation 联动：如果 channel_escalation_enabled=True 且 escalation_channel_order
        #    未提供，服务层需检查 DB 现有值是否已有 order，否则返回 422
        return self

class NotificationPolicyInfo(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    site_id: Optional[int] = None
    alarm_level: str
    time_range_start: Optional[str] = None
    time_range_end: Optional[str] = None
    channels: list[str]
    notify_user_ids: list[int]
    channel_escalation_enabled: bool
    escalation_timeout_minutes: int
    escalation_channel_order: Optional[list[str]] = None
    is_enabled: bool
    is_default: bool
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
```

### 策略服务层

```python
# backend/app/services/notification/policy_service.py

class NotificationPolicyService:

    @staticmethod
    def _to_minutes(hhmm: str) -> int:
        """将 'HH:MM' 转为分钟数 0~1439"""
        h, m = hhmm.split(":")
        return int(h) * 60 + int(m)

    @staticmethod
    def _segments(start: Optional[str], end: Optional[str]) -> list[tuple[int, int]]:
        """将时段转为分钟区间列表，全天返回 [(0, 1440)]，跨午夜拆为两段"""
        if start is None or end is None:
            return [(0, 1440)]
        s = NotificationPolicyService._to_minutes(start)
        e = NotificationPolicyService._to_minutes(end)
        if s == e:
            raise ValueError(f"时段起止相同({start})，零长度时段无效")
        if s < e:
            return [(s, e)]
        else:  # 跨午夜
            return [(s, 1440), (0, e)]

    @staticmethod
    def time_ranges_overlap(
        start1: Optional[str], end1: Optional[str],
        start2: Optional[str], end2: Optional[str]
    ) -> bool:
        """判断两个时段是否重叠（支持跨午夜），使用分钟区间比较"""
        segs1 = NotificationPolicyService._segments(start1, end1)
        segs2 = NotificationPolicyService._segments(start2, end2)
        for a in segs1:
            for b in segs2:
                if a[0] < b[1] and b[0] < a[1]:
                    return True
        return False

    @staticmethod
    async def check_time_overlap(
        db: AsyncSession, site_id: Optional[int], alarm_level: str,
        start: Optional[str], end: Optional[str], exclude_id: Optional[int] = None
    ) -> Optional[int]:
        """检测时段冲突，返回冲突策略 ID 或 None"""
        # 1. 查询同 site_id + alarm_level 的所有策略（排除 exclude_id），包括禁用的
        #    原因：禁用策略可能被重新启用，提前检测避免未来冲突
        # 2. 对每条策略调用 time_ranges_overlap()
        # 3. 返回第一个冲突的策略 ID

    @staticmethod
    async def validate_site_exists(db: AsyncSession, site_id: int) -> bool:
        """校验 site_id 对应的站点是否存在"""
        # 查询 Site 表

    @staticmethod
    async def validate_user_site_access(
        db: AsyncSession, site_id: Optional[int], user_ids: list[int]
    ) -> list[int]:
        """校验用户站点权限，返回无权限的 user_id 列表"""
        # site_id=NULL 跳过校验
        # 空 user_ids 列表跳过校验
        # 查询 UserSite 表
```

### API 设计

```
GET    /api/v1/notification/policies              — 查询策略列表（支持 site_id, alarm_level 筛选）
POST   /api/v1/notification/policies              — 创建策略
PUT    /api/v1/notification/policies/{policy_id}   — 更新策略
DELETE /api/v1/notification/policies/{policy_id}   — 删除策略（is_default=True 不可删除）
```

权限：`require_admin`

**创建/更新时校验流程：**
1. site_id 非 NULL 时，校验 Site 表中存在该站点，否则 422
2. notify_user_ids 非空且 site_id 非 NULL 时，校验 UserSite 权限
3. 时段冲突检测（更新时合并 DB 现有值后再检测）

### 种子数据

在迁移脚本中 seed 4 条全局默认策略：

```python
default_policies = [
    ("全局紧急告警默认策略", "critical", ["im", "sms"]),
    ("全局重要告警默认策略", "major", ["im"]),
    ("全局次要告警默认策略", "minor", ["im"]),
    ("全局信息告警默认策略", "info", ["im"]),
]
# site_id=NULL, notify_user_ids=[], is_default=True, is_enabled=True
# time_range_start=NULL, time_range_end=NULL (全天)
# 使用 raw SQL INSERT 时，channels 用 json.dumps() 序列化；使用 ORM/bulk_insert 时直接传 Python list
```

> **notify_user_ids 为空数组说明：** 默认策略的通知对象需要管理员后续配置。空数组表示"策略存在但尚未配置通知对象"，通知分发器遇到空 notify_user_ids 时跳过发送。

### 迁移脚本

- Revision: `20260319_0200`
- Down revision: `20260319_0100`（Story 34.2）
- 创建 `notification_policies` 表 + 索引 + seed 4 条默认策略
- **幂等性**：使用 `inspect()` 检查表是否已存在；seed 前用 `SELECT COUNT(*)` 检查是否已有默认策略

### 文件清单

| 操作 | 文件 |
|------|------|
| 新建 | `backend/app/models/notification_policy.py` |
| 新建 | `backend/app/schemas/notification_policy.py` |
| 新建 | `backend/app/services/notification/policy_service.py` |
| 新建 | `backend/app/api/v1/notification_policy.py` |
| 新建 | `backend/alembic/versions/20260319_0200_story_34_3_notification_policies.py` |
| 新建 | `backend/tests/api/test_notification_policy.py` |
| 修改 | `backend/app/models/__init__.py` — 注册 NotificationPolicy |
| 修改 | `backend/app/api/v1/__init__.py` — 注册 notification_policy 路由，`prefix="/notification/policies"`, `tags=["通知策略"]` |

### 测试场景

1. 创建策略 — 正常创建，返回 201
2. 创建策略 — notify_user_ids 中用户无站点权限 → 422
3. 创建策略 — 全局策略(site_id=NULL) 跳过站点权限校验 → 201
4. 创建策略 — 时段与已有策略重叠 → 422
5. 创建策略 — 跨午夜时段（22:00~06:00）正常创建 → 201
6. 创建策略 — 跨午夜时段与已有策略冲突 → 422
7. 创建策略 — channels 包含无效值 → 422
8. 创建策略 — time_range_start 有值但 time_range_end 为 None → 422
9. 创建策略 — site_id 指向不存在的站点 → 422
10. 创建策略 — notify_user_ids 为空数组 → 201（允许待配置）
11. 查询策略列表 — 返回所有策略
12. 查询策略列表 — 按 site_id 筛选
13. 查询策略列表 — 按 alarm_level 筛选
14. 更新策略 — 正常更新
15. 更新策略 — 更新时段导致冲突 → 422
16. 更新策略 — 单独更新 time_range_start，与 DB 现有 end 合并后校验
17. 删除策略 — 正常删除 → 204
18. 删除默认策略 — is_default=True → 400
19. 非 admin 用户访问 → 403
20. 时段重叠检测 — 全天策略与任何时段重叠
21. 时段重叠检测 — 不重叠的时段返回 False
22. 时段重叠检测 — 分钟边界精确（22:00~06:00 vs 06:00~08:00 不重叠）
23. 种子数据 — 4 条默认策略存在且 is_default=True
24. 创建策略 — time_range_start == time_range_end → 422（零长度时段）
25. 更新策略 — channels 包含无效值 → 422
26. 更新策略 — 启用 escalation 但未提供 order 且 DB 无现有值 → 422
