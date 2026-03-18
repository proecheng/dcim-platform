# Story 34.1: 用户通知联系方式管理

Status: ready-for-dev

## Story

As a 系统管理员,
I want 为用户配置多渠道通知联系方式,
So that 通知引擎知道通过哪个渠道联系哪个人。

## Acceptance Criteria

1. **Given** 管理员进入用户管理页面 **When** 编辑某用户信息 **Then** 可以配置多个通知联系方式（UserNotificationContact 记录），每种渠道可独立启用/禁用
2. **Given** 管理员创建 sms/voice 类型联系方式 **When** contact_value 不符合手机号格式（中国手机号 11 位数字） **Then** 返回 422 校验错误
3. **Given** 管理员创建 email 类型联系方式 **When** contact_value 不符合邮箱格式 **Then** 返回 422 校验错误
4. **Given** 管理员调用 import-from-profile **When** 用户已有同渠道同值的联系方式 **Then** 跳过已存在的记录，仅创建缺失的（幂等）
5. **Given** 管理员删除或更新联系方式 **When** 该联系方式不属于 URL 中的 user_id **Then** 返回 404（归属校验）

> **延迟验证说明：** 原 Epic AC #2（联系方式缺失时跳过通知）在 Story 34.4 实现；AC #3（NotificationPolicy 站点权限校验）在 Story 34.3 实现。本 Story 仅需确保数据模型和查询接口支持后续 Story 使用。

## Tasks / Subtasks

- [ ] Task 1: UserNotificationContact 数据模型 (AC: #1)
  - [ ] 1.1 创建 `backend/app/models/user_notification_contact.py` — ORM 模型
  - [ ] 1.2 更新 `backend/app/models/__init__.py` — 注册模型到 `__all__`
  - [ ] 1.3 创建 Alembic 迁移脚本（使用 `alembic revision --autogenerate`）
- [ ] Task 2: Pydantic Schema (AC: #1, #2, #3)
  - [ ] 2.1 创建 `backend/app/schemas/user_notification_contact.py`（含手机号/邮箱格式校验）
- [ ] Task 3: CRUD API 端点 (AC: #1, #2, #3, #4, #5)
  - [ ] 3.1 创建 `backend/app/api/v1/user_notification_contacts.py` — REST API（独立文件）
  - [ ] 3.2 更新 `backend/app/api/v1/__init__.py` — 注册路由
  - [ ] 3.3 实现"从账户信息导入"功能（幂等：跳过已存在的同渠道同值记录）
  - [ ] 3.4 实现 PUT/DELETE 归属校验（contact.user_id == url.user_id）
- [ ] Task 4: 自动化测试 (AC: #1~#5)
  - [ ] 4.1 创建 `backend/tests/api/test_user_notification_contacts.py`

## Dev Notes

### 数据模型

**UserNotificationContact 表** — 新建文件 `backend/app/models/user_notification_contact.py`

```python
# backend/app/models/user_notification_contact.py
from datetime import datetime
from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey
from app.core.database import Base

class UserNotificationContact(Base):
    __tablename__ = "user_notification_contacts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, comment="用户ID")
    channel_type = Column(String(20), nullable=False, comment="渠道类型: sms|im|voice|email")
    platform = Column(String(20), nullable=True, comment="平台: dingtalk|wecom|null")
    contact_value = Column(String(200), nullable=False, comment="联系方式值")
    is_enabled = Column(Boolean, default=True, nullable=False, comment="是否启用")
    created_at = Column(DateTime, default=datetime.now, comment="创建时间")
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now, comment="更新时间")
```

[Source: architecture.md#Section 22.2]

**关键约束：**
- `channel_type` 枚举值：`sms`, `im`, `voice`, `email`
- `platform` 仅在 `channel_type=im` 时有值（`dingtalk` 或 `wecom`），其他渠道为 NULL
- 同一用户可有多条同类型记录（如多个钉钉账号）
- 索引：`ix_unc_user_id` on `user_id`（高频查询）
- 无 UniqueConstraint — 允许同用户同渠道多条记录

**与 User.phone/email 的关系：**
- User.phone/email 是账户信息（登录用），UserNotificationContact 是通知专用
- 通知分发器仅查 UserNotificationContact，不直接读 User.phone/email
- 提供"从账户信息导入"API，一键复制 User.email→email contact, User.phone→sms+voice contacts

[Source: epics.md#Story 34.1 Technical Notes]

### API 设计

路由前缀：`/api/v1/users/{user_id}/notification-contacts`

| 方法 | 路径 | 权限 | 说明 |
|------|------|------|------|
| GET | `/api/v1/users/{user_id}/notification-contacts` | require_admin | 获取用户所有通知联系方式 |
| POST | `/api/v1/users/{user_id}/notification-contacts` | require_admin | 新增通知联系方式 |
| PUT | `/api/v1/users/{user_id}/notification-contacts/{id}` | require_admin | 更新通知联系方式 |
| DELETE | `/api/v1/users/{user_id}/notification-contacts/{id}` | require_admin | 删除通知联系方式 |
| POST | `/api/v1/users/{user_id}/notification-contacts/import-from-profile` | require_admin | 从账户信息导入 |

**路由注册方式：** 创建独立文件 `backend/app/api/v1/user_notification_contacts.py`，使用独立 router 注册到 `api_router`。

```python
# backend/app/api/v1/user_notification_contacts.py
router = APIRouter()

@router.get("/{user_id}/notification-contacts", ...)
@router.post("/{user_id}/notification-contacts", ...)
@router.put("/{user_id}/notification-contacts/{contact_id}", ...)
@router.delete("/{user_id}/notification-contacts/{contact_id}", ...)
@router.post("/{user_id}/notification-contacts/import-from-profile", ...)

# backend/app/api/v1/__init__.py 中注册：
from .user_notification_contacts import router as notification_contacts_router
api_router.include_router(notification_contacts_router, prefix="/users", tags=["通知联系方式"])
```

**GET 端点不分页** — 单用户联系方式通常 <20 条，直接返回 `List[NotificationContactInfo]`，不使用 `PageResponse`。

**import-from-profile 返回值** — 返回 `ImportFromProfileResponse`（created: 新创建的记录列表, skipped: 跳过数量）。

### Schema 设计

```python
# backend/app/schemas/user_notification_contact.py
import re
from pydantic import BaseModel, Field, ConfigDict, model_validator, EmailStr
from typing import Optional
from datetime import datetime

PHONE_PATTERN = re.compile(r"^1[3-9]\d{9}$")  # 中国手机号

class NotificationContactCreate(BaseModel):
    channel_type: str = Field(..., pattern="^(sms|im|voice|email)$")
    platform: Optional[str] = Field(None, pattern="^(dingtalk|wecom)$")
    contact_value: str = Field(..., min_length=1, max_length=200)
    is_enabled: bool = True

    @model_validator(mode="after")
    def validate_all(self):
        # 1. platform 校验
        if self.channel_type == "im" and not self.platform:
            raise ValueError("im 渠道必须指定 platform (dingtalk/wecom)")
        if self.channel_type != "im" and self.platform:
            raise ValueError("非 im 渠道不应指定 platform")
        # 2. contact_value 格式校验
        if self.channel_type in ("sms", "voice"):
            if not PHONE_PATTERN.match(self.contact_value):
                raise ValueError("sms/voice 渠道的联系方式必须为有效中国手机号（11位数字，1开头）")
        if self.channel_type == "email":
            # 使用简单正则，不引入 EmailStr 依赖（Create 时 channel_type 已知）
            if not re.match(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$", self.contact_value):
                raise ValueError("email 渠道的联系方式必须为有效邮箱格式")
        return self

class NotificationContactUpdate(BaseModel):
    """更新时 contact_value 格式校验在 API 层执行（需从 DB 读取 channel_type）"""
    contact_value: Optional[str] = Field(None, min_length=1, max_length=200)
    is_enabled: Optional[bool] = None

class NotificationContactInfo(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    user_id: int
    channel_type: str
    platform: Optional[str] = None
    contact_value: str
    is_enabled: bool
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

class ImportFromProfileResponse(BaseModel):
    """从账户信息导入的返回值"""
    created: list[NotificationContactInfo] = []
    skipped: int = 0  # 已存在被跳过的数量
```

**NotificationContactUpdate 格式校验说明：**
- Update schema 不含 channel_type，无法在 schema 层校验 contact_value 格式
- API 层在处理 PUT 请求时，先从 DB 加载现有记录获取 channel_type，再用 `NotificationContactCreate` 的校验逻辑验证新 contact_value
- 实现方式：API 端点中调用独立的 `validate_contact_value(channel_type, contact_value)` 函数

### 站点权限校验

AC #3（站点权限校验）的完整实现在 Story 34.3（NotificationPolicy）中。本 Story 仅需：
- 确保 API 中验证 `user_id` 对应的用户存在（不存在返回 404）
- 确保 PUT/DELETE 中验证 contact 记录归属于 URL 中的 user_id（不匹配返回 404）
- UserSite 表查询能力已存在，无需本 Story 额外实现

### 现有代码集成点

| 文件 | 行号 | 说明 |
|------|------|------|
| `backend/app/models/user.py` | L11-31 | User 模型，phone(L21), email(L20) |
| `backend/app/models/user.py` | L71-80 | UserSite 模型，表名 `user_sites` |
| `backend/app/api/v1/user.py` | L264-284 | `/users/{user_id}/sites` 端点模式参考 |
| `backend/app/api/deps.py` | L102 | `require_admin` 装饰器 |
| `backend/app/schemas/user.py` | L62-88 | UserCreate/UserUpdate schema 模式参考 |
| `backend/app/models/__init__.py` | L116-320 | `__all__` 列表，需添加新模型 |
| `backend/app/api/v1/__init__.py` | L1-129 | 路由注册模式 |

### 迁移脚本

文件名：使用 `alembic revision --autogenerate -m "story_34_1_user_notification_contacts"` 自动生成，`down_revision` 由 Alembic 自动链接到当前最新迁移。

参考现有迁移模式（如 `3110920d5085_story_24_8_add_system_notifications_.py`）：
- 使用 `inspect(conn).get_table_names()` 检查表是否已存在
- 创建表 + 索引（`ix_unc_user_id` on `user_id`）
- downgrade 中 drop 索引 + drop 表

### 测试要求

测试文件：`backend/tests/api/test_user_notification_contacts.py`

覆盖场景：
1. 创建通知联系方式（sms/im/voice/email 各一条）
2. im 渠道缺少 platform 时返回 422
3. 非 im 渠道带 platform 时返回 422
4. sms/voice 渠道 contact_value 非手机号格式时返回 422
5. email 渠道 contact_value 非邮箱格式时返回 422
6. 获取用户所有联系方式（返回列表）
7. 更新联系方式（修改 contact_value, is_enabled）
8. 更新时 contact 不属于 URL user_id 返回 404（归属校验）
9. 删除联系方式
10. 删除时 contact 不属于 URL user_id 返回 404（归属校验）
11. 从账户信息导入（User 有 phone+email → 创建 3 条记录：sms+voice+email）
12. 从账户信息导入幂等性（重复调用不创建重复记录）
13. 从账户信息导入（User 无 phone/email → 返回空列表）
14. 用户不存在时返回 404
15. 非 admin 角色访问返回 403
16. channel_type 为无效值时返回 422

### Project Structure Notes

```
backend/app/
├── models/
│   ├── user.py                          # 现有 — User, UserSite（不修改）
│   ├── user_notification_contact.py     # 新增 — UserNotificationContact
│   └── __init__.py                      # 修改 — 添加 import + __all__
├── schemas/
│   └── user_notification_contact.py     # 新增
├── api/v1/
│   ├── user_notification_contacts.py    # 新增
│   └── __init__.py                      # 修改 — 注册路由
└── tests/api/
    └── test_user_notification_contacts.py  # 新增
```

### References

- [Source: architecture.md#Section 22.2 数据模型扩展]
- [Source: epics.md#Epic 34 Story 34.1]
- [Source: prd.md#FR-N05]
- [Source: backend/app/models/user.py#L11-80]
- [Source: backend/app/api/v1/user.py#L264-284]
- [Source: backend/app/api/deps.py#L102]

## Dev Agent Record

### Agent Model Used

Claude Opus 4.6

### Completion Notes List

- 仅后端 API + 数据模型，前端统一到 Story 34.7
- NotificationPolicy 和 NotificationRecord 表在后续 Story 中创建，本 Story 不涉及
- 原 Epic AC #2（联系方式缺失时跳过通知）的执行逻辑在 Story 34.4 实现
- 原 Epic AC #3（NotificationPolicy 站点权限校验）在 Story 34.3 实现
- R1 对抗性审查修复 11 处：AC 重写为本 Story 可交付范围、新增手机号/邮箱格式校验、import 幂等性、PUT/DELETE 归属校验、路由方案明确为独立文件、迁移脚本使用 autogenerate、新增 updated_at 字段、测试场景扩充到 16 个
- R2 对抗性审查修复 8 处：Update 格式校验方案（API层校验）、合并两个 model_validator 为一个、路由注册代码示例、import-from-profile 返回值定义（ImportFromProfileResponse）、email 正则增强、模型 import 语句补全、File List 迁移文件名改为通配、GET 端点明确不分页

### File List

- `backend/app/models/user_notification_contact.py` — 新增
- `backend/app/schemas/user_notification_contact.py` — 新增
- `backend/app/api/v1/user_notification_contacts.py` — 新增
- `backend/app/models/__init__.py` — 修改
- `backend/app/api/v1/__init__.py` — 修改
- `backend/alembic/versions/*_story_34_1_user_notification_contacts.py` — 新增（autogenerate）
- `backend/tests/api/test_user_notification_contacts.py` — 新增
