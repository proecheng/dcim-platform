# Story 13-2: 认证与会话管理增强

## 状态: 就绪

## Story

As a 系统管理员,
I want 完善的认证和会话管理机制,
So that 系统安全性满足等保二级要求。

## 验收标准 (AC)

1. JWT Token 过期自动登出 — 已有
2. 并发会话限制（最多3个，超限踢出最早会话）
3. 密码 bcrypt 哈希存储 — 已有
4. 登录限流 5次/分钟 — 已有
5. JWT 签名验证失败时记录安全告警日志
6. 被踢出用户返回 401 + 提示"会话已在其他设备登录"

## 棕地分析

### 已有代码
- `auth.py`: login/logout/refresh/me/password/permissions, RateLimiter (5次/分钟)
- `core/security.py`: verify_password, get_password_hash, create_access_token
- `api/deps.py`: get_current_user (JWT decode + user lookup)
- `models/user.py`: User, UserLoginHistory

### 需要新增
- `models/user.py`: UserSession 模型 (user_id, token_jti, created_at, is_active)
- `auth.py`: 登录时创建 session 记录，超过3个踢出最早的
- `api/deps.py`: 验证 token 时检查 session 是否 active
- `auth.py`: JWT 验证失败时写入 OperationLog (安全告警)

## 技术方案

### 1. UserSession 模型
```python
class UserSession(Base):
    __tablename__ = "user_sessions"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    token_jti = Column(String(64), unique=True, nullable=False)  # JWT ID
    created_at = Column(DateTime, default=datetime.now)
    is_active = Column(Boolean, default=True)
```

### 2. 登录流程增强
- 生成 JWT 时加入 jti (JWT ID) claim
- 登录成功后创建 UserSession 记录
- 查询该用户活跃 session 数，超过3个则将最早的标记为 is_active=False

### 3. Token 验证增强
- deps.py 中 get_current_user 增加 session 检查
- 如果 session 不存在或 is_active=False，返回 401 "会话已在其他设备登录"

### 4. 安全日志
- JWT 解码失败时，记录 OperationLog (module="auth", action="jwt_tamper_detected")

## 测试计划
- 6 个测试
- 测试文件: `tests/test_auth_session.py`
