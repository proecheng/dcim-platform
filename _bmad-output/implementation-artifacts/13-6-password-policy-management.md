# Story 13-6: 密码策略管理

## Status: Ready for Implementation

## Story
As a 系统管理员,
I want 系统强制执行密码复杂度要求,
So that 用户账号安全性满足等保二级要求。

## Acceptance Criteria (AC)

### AC1: 密码复杂度校验增强
- Given 用户创建或修改密码
- When 提交新密码
- Then 系统校验：最少 8 位，包含大写字母、小写字母、数字、特殊字符中至少 3 类
- And 现有 validate_password_complexity 已满足（要求全部4类），需改为至少3类

### AC2: 密码历史记录
- Given 用户修改密码
- When 提交新密码
- Then 系统检查新密码不能与最近 5 次历史密码相同
- And 密码历史通过 PasswordHistory 模型记录

### AC3: 密码过期提醒
- Given 用户登录
- When 密码超过 90 天未更换
- Then 登录响应中包含 password_expired_warning 字段提示更换（非强制）

### AC4: 密码策略可配置
- Given 系统管理员
- When 调用密码策略配置 API
- Then 可查询和修改策略参数（最小长度、复杂度要求、历史次数、过期天数）
- And 策略存储在 SystemConfig 表中

## Technical Design

### 1. 新增模型: PasswordHistory

文件: `backend/app/models/user.py`

```python
class PasswordHistory(Base):
    __tablename__ = "password_history"
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    password_hash = Column(String(255), nullable=False)
    created_at = Column(DateTime, default=datetime.now)
```

### 2. User 模型添加 password_changed_at

```python
password_changed_at = Column(DateTime, nullable=True, comment="密码最后修改时间")
```

### 3. 修改 validate_password_complexity

改为至少满足 3 类（大写、小写、数字、特殊字符），而非全部 4 类。

### 4. 修改 change_password 端点

- 检查新密码不在最近 5 次历史中
- 保存旧密码到 PasswordHistory
- 更新 password_changed_at

### 5. 修改 login 端点

- 检查 password_changed_at，如果超过 90 天，在响应中添加 warning

### 6. 密码策略配置 API

- `GET /auth/password-policy` — 获取当前策略
- `PUT /auth/password-policy` — 更新策略（admin only）

策略参数存储在 SystemConfig 表：
- config_group: "password_policy"
- config_key: min_length / min_categories / history_count / expire_days

## 测试计划

1. 密码复杂度 — 至少3类通过，少于3类拒绝
2. 密码历史 — 修改密码后不能重用最近5次
3. 密码过期提醒 — 超过90天登录时返回 warning
4. 策略配置 — GET/PUT 密码策略
5. 创建用户时记录密码历史
6. 重置密码时记录密码历史
