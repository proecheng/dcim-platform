# Story 26.10: HMAC 密钥管理

Status: done

## Story

As a 管理员,
I want 通过 API 管理 HMAC 密钥轮换，查看密钥状态和轮换历史,
So that 故障树签名密钥可以按安全策略定期轮换，且整个过程有审计记录。

## 依赖

- Story 24.4（故障树版本管理与 HMAC 签名）— done（HMACManager、FaultTreeVersion.hmac_signature 已实现）
- Story 26.8（SBOM 管理）— done

## Architecture Reference

- Architecture V4.0.0 Section 18.8: 故障树版本管理（HMAC-SHA-256 签名流程）
- Architecture V4.0.0 Section 18.11: 安全加固架构（FR34-35 密钥管理）
- 现有代码: `backend/app/services/diagnosis/hmac_manager.py`（HMACManager 类）
- 现有代码: `backend/app/services/diagnosis/version_manager.py`（VersionManager.activate_version 中使用 HMAC 签名）
- 现有配置: `backend/app/core/config.py`（fault_tree_hmac_key + fault_tree_hmac_key_previous，启动时校验长度 >= 32）

## Acceptance Criteria

1. Given 管理员需要了解当前 HMAC 密钥状态
   When 调用 `GET /api/v1/diagnosis/hmac-key/status` 端点
   Then 返回密钥状态信息：当前密钥是否配置、密钥长度、是否配置了轮换密钥（previous key）、上次轮换时间、当前密钥签署的活跃版本数量
   And 不返回密钥明文（仅返回长度和前4字符掩码如 `your****`）

2. Given 管理员执行密钥轮换操作
   When 调用 `POST /api/v1/diagnosis/hmac-key/rotate` 并提供新密钥
   Then 系统验证新密钥长度 >= 32 字符
   And 轮换前先验证所有 active 版本的现有签名（使用当前密钥），如有签名验证失败则中止轮换并返回错误
   And 系统用新密钥对所有 active 和 reviewed 状态的 FaultTreeVersion 重新签名（draft 无签名无需处理，archived 保留旧签名由 verify-all 按需检查）
   And 如果任意版本重签名失败，整个操作回滚，不提交部分修改
   And 记录轮换审计日志到 `hmac_key_rotation_logs` 表（含重签名的版本 ID 列表）
   And 返回轮换结果：重新签名的版本数量、版本 ID 列表、操作时间

3. Given 管理员需要验证故障树版本的签名完整性
   When 调用 `POST /api/v1/diagnosis/hmac-key/verify-all` 端点
   Then 系统使用当前密钥（和可选的 previous 密钥）验证所有 active 和 reviewed 版本的签名
   And 返回验证结果：每个版本的 ID、tree_id、version_number、状态、验证结果（valid/invalid/no_signature）
   And 签名验证失败的版本标记为需要关注

4. Given 管理员需要查看密钥轮换历史
   When 调用 `GET /api/v1/diagnosis/hmac-key/rotation-logs` 端点
   Then 返回分页的轮换历史记录
   And 每条记录包含：轮换时间、操作者 ID、重新签名版本数、版本 ID 列表、操作结果

5. Given 密钥轮换涉及安全操作
   When 任何 HMAC 密钥管理 API 被调用
   Then 所有端点需要 admin 权限（`require_admin`）
   And 敏感操作（轮换）记录审计日志
   And 使用 `SELECT ... FOR UPDATE` 防止并发轮换操作（PostgreSQL 生效，SQLite 静默忽略 — 与 version_manager.py 行为一致）

## Technical Notes

### 数据模型

新增 `hmac_key_rotation_logs` 表（类名 `HMACKeyRotationLog`，表名复数，与项目约定一致）：

```python
class HMACKeyRotationLog(Base):
    __tablename__ = "hmac_key_rotation_logs"
    id = Column(Integer, primary_key=True, autoincrement=True)
    rotated_at = Column(DateTime, nullable=False, default=datetime.now)
    rotated_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    versions_resigned = Column(Integer, nullable=False, default=0)
    resigned_version_ids = Column(JSON, nullable=True)  # 重签名的版本 ID 列表
    new_key_prefix = Column(String(4), nullable=False)  # 新密钥前4字符（最小化泄露）
    old_key_prefix = Column(String(4), nullable=True)   # 旧密钥前4字符
    status = Column(String(20), nullable=False)  # success / failed
    error_detail = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.now)
```

### 服务层

新增 `HMACKeyManagementService`（位于 `backend/app/services/diagnosis/hmac_key_service.py`）：

- `get_key_status()` — 查询当前密钥配置状态和活跃版本统计
- `rotate_key(new_key, operator_id)` — 执行密钥轮换：先验证现有签名，再用新密钥对所有 active/reviewed 版本重新签名，使用 `FOR UPDATE` 锁
- `verify_all_signatures()` — 批量验证所有 active/reviewed 版本签名
- `list_rotation_logs(page, page_size)` — 分页查询轮换历史

### API 端点

在 `diagnosis.py` 路由中添加 4 个端点（前缀 `/hmac-key/`）:

```
GET  /api/v1/diagnosis/hmac-key/status        — 密钥状态
POST /api/v1/diagnosis/hmac-key/rotate         — 密钥轮换
POST /api/v1/diagnosis/hmac-key/verify-all     — 批量验证签名
GET  /api/v1/diagnosis/hmac-key/rotation-logs  — 轮换历史
```

### 密钥轮换流程

1. 接收新密钥 → 验证长度 >= 32
2. `SELECT ... FOR UPDATE` 锁定所有 active/reviewed 版本（防止并发）
3. 使用当前密钥验证所有 active 版本签名 → 任一失败则中止
4. 对每个 active/reviewed 版本用新密钥重新生成签名（直接使用 `hmac.new()`）
5. 更新 `hmac_signature` 字段
6. 记录审计日志（含版本 ID 列表）
7. 提交事务，返回操作结果

**⚠️ 部署同步要求**: 密钥轮换 API 接收新密钥但 **不修改** config.py / .env 文件。管理员必须按以下顺序操作：
1. 先通过 API 用新密钥重签所有版本
2. **立即** 更新环境变量：`FAULT_TREE_HMAC_KEY=<新密钥>`, `FAULT_TREE_HMAC_KEY_PREVIOUS=<旧密钥>`
3. **停止所有实例** 后重启（`@lru_cache` 缓存在进程重启时自然重建，新配置生效）
4. **注意**: 步骤 1 和 2 之间如果服务重启，新版本的签名将无法验证（因为配置仍是旧密钥）

如果管理员直接手动修改 .env（不通过 API），应在重启后调用 `verify-all` 端点检查签名完整性。

**关于 `@lru_cache` 缓存**: `get_settings()` 使用 `@lru_cache()`，配置在进程生命周期内不变。密钥轮换后必须重启服务才能加载新密钥。这是已有设计（Story 24.4），本 Story 不改变此行为。

### 安全约束

- 新密钥通过 request body 传入（HTTPS 加密传输），不记录到日志中
- 日志中仅记录密钥前缀（前4字符，最小化泄露同时保留可识别性）
- 使用 `hmac.compare_digest()` 防止时序攻击（验证时复用 HMACManager 现有逻辑）
- `SELECT ... FOR UPDATE` 防止并发轮换操作导致签名不一致（PostgreSQL 生效，SQLite 静默忽略 — 与 version_manager.py 一致）

### HMACManager 扩展

为 `HMACManager` 新增静态方法 `generate_signature_with_key(data, key)` 用于轮换场景：

```python
@staticmethod
def generate_signature_with_key(data: str, key: str) -> str:
    """使用指定密钥生成签名（用于密钥轮换）"""
    return hmac.new(key.encode(), data.encode(), hashlib.sha256).hexdigest()
```

这样签名生成逻辑集中在 HMACManager 中，避免重复代码。

## Tasks

1. 数据模型
   - [ ] 1.1 在 `diagnosis.py` 模型文件中添加 `HMACKeyRotationLog` 模型
   - [ ] 1.2 在 `__init__.py` 中导出新模型
   - [ ] 1.3 创建 Alembic 迁移文件（down_revision = '20260314_0100'，即 Story 26.9 的迁移）

2. 服务层
   - [ ] 2.1 在 `HMACManager` 中新增 `generate_signature_with_key(data, key)` 静态方法
   - [ ] 2.2 创建 `hmac_key_service.py`，实现 `HMACKeyManagementService`
   - [ ] 2.3 实现 `get_key_status()` — 密钥状态查询
   - [ ] 2.4 实现 `rotate_key(new_key, operator_id)` — 密钥轮换与重签名（含前置验证、FOR UPDATE 锁、事务回滚）
   - [ ] 2.5 实现 `verify_all_signatures()` — 批量验证 active/reviewed 版本
   - [ ] 2.6 实现 `list_rotation_logs(page, page_size)` — 轮换日志查询

3. API 端点
   - [ ] 3.1 添加 `GET /hmac-key/status` 端点
   - [ ] 3.2 添加 `POST /hmac-key/rotate` 端点（接收 `{"new_key": "..."}` body）
   - [ ] 3.3 添加 `POST /hmac-key/verify-all` 端点
   - [ ] 3.4 添加 `GET /hmac-key/rotation-logs` 端点

4. 测试
   - [ ] 4.1 创建 `test_hmac_key_service.py` 测试文件
   - [ ] 4.2 测试密钥状态查询（有/无 previous key、有/无活跃版本）
   - [ ] 4.3 测试密钥轮换成功（active + reviewed 版本均被重签名）
   - [ ] 4.4 测试密钥轮换失败（密钥太短、无版本、现有签名无效中止轮换）
   - [ ] 4.5 测试批量验证（全部通过/部分失败/无签名版本）
   - [ ] 4.6 测试轮换日志分页查询
   - [ ] 4.7 测试并发轮换保护（FOR UPDATE 锁）

## Dev Notes

- 复用 `HMACManager.verify_signature()` 进行签名验证（支持 current + previous key）
- 使用新增 `HMACManager.generate_signature_with_key()` 进行轮换签名（不依赖 settings）
- 所有端点使用 `_: User = Depends(require_admin)` 模式（与 26.9 一致）
- 错误处理使用 `raise HTTPException(status_code=..., detail=...)` 模式
- API 响应格式统一使用 `{"code": 200, "message": "...", "data": {...}}` 模式（与 training-audit 端点一致）
- `fault_tree_hmac_key` 在启动时由 config.py validator 强制校验（必须设置且 >= 32 字符），因此 `get_key_status()` 中密钥总是已配置的
- 测试中 HMAC 密钥来自 conftest.py 的 `os.environ["FAULT_TREE_HMAC_KEY"]`（已配置 >= 32 字符）
- 测试需要创建 FaultTreeVersion fixtures（需先有 FaultTree + User 记录）
- `with_for_update()` 在 SQLite 下被静默忽略（与 version_manager.py 现有行为一致），仅 PostgreSQL 生产环境提供并发保护
- Alembic 迁移 down_revision = '20260314_0100'（Story 26.9 迁移）
