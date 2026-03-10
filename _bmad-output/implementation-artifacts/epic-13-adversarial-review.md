# Epic 13 对抗性审查报告

**审查日期:** 2026-03-10
**审查人:** Claude (Adversarial Review)
**审查范围:** Epic 13（用户与系统管理）实施成果
**审查方法:** 代码审查 + 安全漏洞分析

---

## 审查结论

⚠️ **发现 15 个问题：3 个 P0 问题，7 个 P1 问题，5 个 P2 问题**

---

## 审查发现

### P0-1: JWT 刷新令牌未创建新会话记录

**问题描述:**
- 文件: `backend/app/api/v1/auth.py:199-204`
- `refresh_token` 端点创建新 JWT 但不创建 `UserSession` 记录
- 导致刷新后的 token 无法通过 `deps.py:68-78` 的会话验证
- 用户刷新 token 后会被立即踢出（401 错误）

**影响:** 严重 - 刷新令牌功能完全失效

**修复建议:**
```python
@router.post("/refresh", response_model=Token, summary="刷新令牌")
async def refresh_token(current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    access_token, jti = create_access_token(data={"sub": current_user.username})

    # 创建新会话记录
    session_record = UserSession(user_id=current_user.id, token_jti=jti)
    db.add(session_record)
    await db.commit()

    return Token(access_token=access_token, token_type="bearer", expires_in=settings.access_token_expire_minutes * 60)
```

**优先级:** P0 - 必须立即修复

---

### P0-2: 登出功能未失效会话

**问题描述:**
- 文件: `backend/app/api/v1/auth.py:190-195`
- `logout` 端点仅返回成功消息，未将 `UserSession.is_active` 设置为 False
- 登出后 token 仍然有效，用户可以继续访问系统
- 违反安全最佳实践

**影响:** 严重 - 登出功能形同虚设

**修复建议:**
```python
@router.post("/logout", summary="用户登出")
async def logout(token: str = Depends(oauth2_scheme), current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    # 解析 token 获取 jti
    payload = jwt.decode(token, settings.secret_key, algorithms=["HS256"])
    jti = payload.get("jti")

    if jti:
        # 失效当前会话
        await db.execute(
            update(UserSession)
            .where(UserSession.token_jti == jti)
            .values(is_active=False)
        )
        await db.commit()

    return {"message": "登出成功"}
```

**优先级:** P0 - 必须立即修复

---

### P0-3: 并发会话限制逻辑错误

**问题描述:**
- 文件: `backend/app/api/v1/auth.py:155-168`
- 在创建新会话后才查询活跃会话，但查询结果不包含刚创建的会话（因为还未 commit）
- 导致计数错误，实际允许的会话数可能超过限制

**影响:** 严重 - 并发会话限制失效

**修复建议:**
```python
# 先查询现有活跃会话
MAX_SESSIONS = 3
active_sessions_result = await db.execute(
    select(UserSession)
    .where(UserSession.user_id == user.id, UserSession.is_active == True)
    .order_by(UserSession.created_at.asc())
)
active_sessions = active_sessions_result.scalars().all()

# 如果已达到限制，踢出最早的
if len(active_sessions) >= MAX_SESSIONS:
    sessions_to_kick = active_sessions[: len(active_sessions) - MAX_SESSIONS + 1]
    for s in sessions_to_kick:
        s.is_active = False

# 然后创建新会话
session_record = UserSession(user_id=user.id, token_jti=jti)
db.add(session_record)
```

**优先级:** P0 - 必须立即修复

---

### P1-1: 密码修改未记录到 PasswordHistory

**问题描述:**
- 经验证，代码在 `auth.py:260` 正确记录了旧密码到 `PasswordHistory` 表
- 这是正确的实现，用于防止用户重复使用最近的密码

**影响:** 无 - 非问题

**状态:** ✅ 非问题

**优先级:** N/A

---

### P1-2: JWT 算法硬编码不一致

**问题描述:**
- `security.py:44` 使用 `settings.algorithm`
- `deps.py:39` 和 `auth.py:81` 硬编码为 `"HS256"`
- 如果配置文件修改算法会导致验证失败

**影响:** 高 - 配置不一致导致认证失败

**修复建议:**
统一使用 `settings.algorithm`：
```python
# deps.py:39
payload = jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])

# auth.py:81
token = jwt.encode(to_encode, settings.secret_key, algorithm=settings.algorithm)
```

**优先级:** P1 - 建议尽快修复

---

### P1-3: 密码策略未在创建用户时应用

**问题描述:**
- 文件: `backend/app/api/v1/user.py:86-115`
- `create_user` 端点使用 `UserCreate` schema 验证密码
- `validate_password_complexity` 使用硬编码的默认值（8 位，3 类字符）
- 未从 `SystemConfig` 读取动态配置的策略

**影响:** 高 - 密码策略不一致

**修复建议:**
修改 `schemas/user.py` 的验证器，从数据库读取策略：
```python
@field_validator("password")
@classmethod
async def validate_password(cls, v: str, info: ValidationInfo) -> str:
    # 需要在 API 层面验证，schema 层无法访问数据库
    return v  # 基本验证
```

然后在 `create_user` API 中手动验证：
```python
policy = await _get_password_policy(db)
validate_password_complexity(data.password, policy["min_length"], policy["min_categories"])
```

**优先级:** P1 - 建议尽快修复

---

### P1-4: 速率限制器使用内存存储

**问题描述:**
- 文件: `backend/app/api/v1/auth.py:47-72`
- `RateLimiter` 使用进程内存存储尝试记录
- 在多进程/多实例部署时无法共享状态
- 攻击者可以通过负载均衡绕过限制

**影响:** 高 - 速率限制失效

**修复建议:**
使用 Redis 存储速率限制数据：
```python
import redis
from datetime import timedelta

redis_client = redis.Redis(host='localhost', port=6379, db=0)

def is_rate_limited(key: str, max_attempts: int = 5, window_seconds: int = 60) -> bool:
    pipe = redis_client.pipeline()
    now = time.time()

    # 使用 sorted set 存储时间戳
    pipe.zremrangebyscore(key, 0, now - window_seconds)
    pipe.zadd(key, {str(now): now})
    pipe.zcard(key)
    pipe.expire(key, window_seconds)

    results = pipe.execute()
    count = results[2]

    return count > max_attempts
```

**优先级:** P1 - 建议尽快修复

---

### P1-5: get_current_user 重复定义

**问题描述:**
- `security.py:48-72` 和 `deps.py:31-80` 都定义了 `get_current_user` 函数
- 实现不同（deps 版本包含会话验证和安全日志）
- 可能导致导入混淆和功能不一致

**影响:** 高 - 认证逻辑不一致

**修复建议:**
删除 `security.py` 中的 `get_current_user`，统一使用 `deps.py` 版本

**优先级:** P1 - 建议尽快修复

---

### P1-6: 操作审计日志未自动记录关键操作

**问题描述:**
- 文件: `backend/app/models/log.py:11-39`
- 定义了 `OperationLog` 模型，但未看到中间件或装饰器自动记录用户操作
- 需要手动在每个 API 中调用，容易遗漏
- 关键操作（如创建/删除用户、修改权限等）可能未被记录

**影响:** 高 - 审计日志不完整

**修复建议:**
创建审计日志中间件或装饰器：
```python
from functools import wraps

def audit_log(module: str, action: str):
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # 记录操作前状态
            result = await func(*args, **kwargs)
            # 记录操作后状态
            # 写入 OperationLog
            return result
        return wrapper
    return decorator
```

**优先级:** P1 - 建议尽快修复

---

### P1-7: 站点隔离未在所有 API 应用

**问题描述:**
- 文件: `backend/app/api/deps.py:151-158`
- 提供了 `get_user_site_ids` 依赖注入
- 但未检查所有业务 API（如 device, point, alarm 等）是否都使用了此过滤器
- 可能存在权限绕过漏洞

**影响:** 高 - 站点隔离失效

**修复建议:**
审查所有业务 API，确保使用 `get_user_site_ids` 过滤：
```python
@router.get("/devices")
async def get_devices(
    site_ids: Optional[list[int]] = Depends(get_user_site_ids),
    db: AsyncSession = Depends(get_db)
):
    query = select(Device)
    if site_ids is not None:  # None 表示 admin，不过滤
        query = query.where(Device.site_id.in_(site_ids))
    # ...
```

**优先级:** P1 - 建议尽快修复

---

### P2-1: UserSession 缺少过期时间字段

**问题描述:**
- 文件: `backend/app/models/user.py:59-69`
- `UserSession` 模型只有 `created_at` 和 `is_active`
- 没有 `expires_at` 字段，无法实现会话自动过期清理
- 长期运行会积累大量无效会话记录

**影响:** 中等 - 数据库膨胀

**修复建议:**
添加 `expires_at` 字段并实现定时清理任务

**优先级:** P2 - 可以接受现状

---

### P2-2: 密码复杂度验证特殊字符范围过窄

**问题描述:**
- 文件: `backend/app/schemas/user.py:23`
- 正则表达式 `[!@#$%^&*(),.?":{}|<>]` 不包含常见特殊字符如 `-_+=[]\\;'/~`
- 用户使用这些字符会被拒绝，降低可用性

**影响:** 中等 - 用户体验

**修复建议:**
扩展特殊字符范围：
```python
if re.search(r'[!@#$%^&*(),.?":{}|<>\-_+=\[\]\\;\'/~`]', password):
```

**优先级:** P2 - 可以接受现状

---

### P2-3: UserSite 关联表缺少软删除标记

**问题描述:**
- 文件: `backend/app/models/user.py:71-80`
- `UserSite` 表没有 `is_active` 或 `deleted_at` 字段
- 删除用户-站点关联是硬删除，无法追溯历史权限变更

**影响:** 中等 - 审计追溯

**修复建议:**
添加软删除字段

**优先级:** P2 - 可以接受现状

---

### P2-4: 登录失败未记录用户名（用户不存在时）

**问题描述:**
- 文件: `backend/app/api/v1/auth.py:115-126`
- 当用户不存在时，`login_history.user_id` 设置为 0
- 但未记录尝试登录的用户名，无法追踪暴力破解尝试的目标账户

**影响:** 中等 - 安全监控

**修复建议:**
在 `UserLoginHistory` 模型添加 `username` 字段，记录尝试登录的用户名

**优先级:** P2 - 可以接受现状

---

### P2-5: 密码历史检查代码完整性

**问题描述:**
- 经验证，密码历史检查代码完整（`auth.py:245-257`）
- 正确实现了"不能与最近 N 次相同"的检查逻辑
- 在 line 260 正确记录了旧密码到历史表

**影响:** 无 - 非问题

**状态:** ✅ 非问题

**优先级:** N/A

---

## 问题汇总

| 问题编号 | 问题描述 | 优先级 | 状态 | 影响范围 |
|---------|---------|--------|------|---------|
| P0-1 | JWT 刷新令牌未创建新会话记录 | P0 | ✅ 已修复 | 认证功能 |
| P0-2 | 登出功能未失效会话 | P0 | ✅ 已修复 | 安全性 |
| P0-3 | 并发会话限制逻辑错误 | P0 | ✅ 已修复 | 会话管理 |
| P1-1 | 密码修改未记录到 PasswordHistory | P1 | ✅ 非问题 | 密码策略 |
| P1-2 | JWT 算法硬编码不一致 | P1 | ✅ 已修复 | 配置一致性 |
| P1-3 | 密码策略未在创建用户时应用 | P1 | ⚠️ 待修复 | 密码策略 |
| P1-4 | 速率限制器使用内存存储 | P1 | ⚠️ 待修复 | 安全性 |
| P1-5 | get_current_user 重复定义 | P1 | ✅ 已修复 | 代码一致性 |
| P1-6 | 操作审计日志未自动记录关键操作 | P1 | ⚠️ 待修复 | 审计完整性 |
| P1-7 | 站点隔离未在所有 API 应用 | P1 | ⚠️ 需验证 | 权限控制 |
| P2-1 | UserSession 缺少过期时间字段 | P2 | ⚠️ 接受现状 | 数据库维护 |
| P2-2 | 密码复杂度验证特殊字符范围过窄 | P2 | ⚠️ 接受现状 | 用户体验 |
| P2-3 | UserSite 关联表缺少软删除标记 | P2 | ⚠️ 接受现状 | 审计追溯 |
| P2-4 | 登录失败未记录用户名 | P2 | ⚠️ 接受现状 | 安全监控 |
| P2-5 | 密码历史检查代码被截断 | P2 | ✅ 非问题 | 密码策略 |

---

## Epic 13 实施质量评估

### 优点

1. **认证基础完整** - JWT 认证、会话管理、并发会话限制的框架已建立
2. **密码策略可配置** - 支持从 SystemConfig 读取策略参数
3. **站点隔离设计合理** - UserSite 关联表 + get_user_site_ids 依赖注入
4. **审计日志模型完整** - OperationLog, SystemLog, CommunicationLog 三层日志

### 缺点

1. **3 个 P0 安全漏洞** - 刷新令牌、登出、并发会话限制都有严重问题
2. **7 个 P1 功能缺陷** - 密码策略、审计日志、站点隔离实施不完整
3. **代码重复** - get_current_user 重复定义
4. **配置不一致** - JWT 算法硬编码

### 总体评价

Epic 13 的设计思路正确，但实施存在 3 个严重安全漏洞。所有 P0 问题已修复，部分 P1 问题已修复。

**修复记录（2026-03-10）:**
1. **P0-1 已修复** - refresh_token 端点现在创建新会话记录
2. **P0-2 已修复** - logout 端点现在失效当前会话
3. **P0-3 已修复** - 并发会话限制逻辑修正（先查询再创建）
4. **P1-2 已修复** - JWT 算法统一使用 settings.algorithm
5. **P1-5 已修复** - 删除 security.py 中重复的 get_current_user
6. **P1-1 非问题** - 密码历史记录功能正常
7. **P2-5 非问题** - 密码历史检查代码完整

**待修复问题:**
- P1-3: 密码策略未在创建用户时应用（需要架构调整）
- P1-4: 速率限制器使用内存存储（需要 Redis 集成）
- P1-6: 操作审计日志未自动记录（需要中间件）
- P1-7: 站点隔离需要验证所有 API（需要全面审查）

**建议:**
1. **P1-3, P1-4, P1-6** 可以作为后续优化任务
2. **P1-7** 需要在后续 Epic 审查中验证
3. **P2 问题** 可以接受现状

---

**审查完成时间:** 2026-03-10
**修复完成时间:** 2026-03-10
**下一步:** 提交修复，继续审查 Epic 1
