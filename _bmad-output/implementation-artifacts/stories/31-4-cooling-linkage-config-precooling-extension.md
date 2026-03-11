# Story 31.4: CoolingLinkageConfig 预冷扩展

Status: done

## Story

As a 系统管理员,
I want 在制冷联动配置中启用/禁用预冷功能并设置目标温度,
So that 我能按区域灵活控制预冷策略。

## 依赖

- Story 29.1（数据模型扩展，precool_target_temp/precool_enabled 已添加）— done
- Story 31.3（预冷计划 API 端点）— done

## Acceptance Criteria

1. Given CoolingLinkageConfig 已有 precool_target_temp 和 precool_enabled 字段
   When 管理员通过 API 查询预冷配置
   Then `GET /api/v1/precool/zones/{zone_id}/config` 返回该 zone 的预冷相关配置
   And 权限要求 operator+

2. Given 管理员需要修改预冷配置
   When 调用 `PUT /api/v1/precool/zones/{zone_id}/config`
   Then 更新 precool_enabled 和 precool_target_temp
   And precool_target_temp 范围验证 18-25°C（ASHRAE 下限到安全上限）
   And precool_enabled 默认 False
   And 权限要求 admin

3. Given 配置变更
   When 管理员修改预冷配置
   Then 系统记录审计日志到 operation_logs 表
   And 记录旧值和新值（JSON 格式）

4. Given zone 无配置记录
   When 查询预冷配置
   Then 返回默认值（precool_enabled=False, precool_target_temp=18.0）

## Tasks / Subtasks

- [x] Task 1: 创建预冷配置 Schema (AC: #1-2)
  - [x] 1.1 在 `backend/app/schemas/precool.py` 追加 `PrecoolConfigOut`（precool_enabled, precool_target_temp, zone_id）
  - [x] 1.2 追加 `PrecoolConfigUpdate`（precool_enabled 可选, precool_target_temp 可选 + 范围验证 18-25°C）

- [x] Task 2: 实现 2 个 API 端点 (AC: #1-4)
  - [x] 2.1 `GET /zones/{zone_id}/config` — 查询 CoolingLinkageConfig 的预冷字段，zone 不存在 → 404，config 不存在 → 返回默认值
  - [x] 2.2 `PUT /zones/{zone_id}/config` — 更新预冷配置（admin only），zone 不存在 → 404，config 不存在 → 自动创建（必须设置 cooling_zone_id=zone_id）

- [x] Task 3: 审计日志 (AC: #3)
  - [x] 3.1 配置变更时写入 OperationLog（module="precool", action="update", old_value/new_value JSON）
  - [x] 3.2 从当前用户获取 username 记录到审计日志

- [x] Task 4: 单元测试 (AC: #1-4)
  - [x] 4.1 创建 `backend/tests/api/test_precool_config_api.py`
  - [x] 4.2 测试查询配置（有/无现有配置）
  - [x] 4.3 测试更新配置成功
  - [x] 4.4 测试 precool_target_temp 范围验证（<18 或 >25 拒绝）
  - [x] 4.5 测试审计日志写入
  - [x] 4.6 测试权限（viewer 被拒，operator 可读，admin 可写）
  - [x] 4.7 测试 zone 不存在返回 404
  - [x] 4.8 目标 ≥10 个测试用例

## Dev Notes

### 端点设计伪代码

```python
# GET /zones/{zone_id}/config
async def get_precool_config(zone_id, db):
    # 1. 校验 CoolingZone 存在 → 404
    # 2. 查询 CoolingLinkageConfig where cooling_zone_id == zone_id
    # 3. 不存在 → 返回默认值 {precool_enabled: False, precool_target_temp: 18.0}
    # 4. 返回 PrecoolConfigOut

# PUT /zones/{zone_id}/config
async def update_precool_config(zone_id, request: PrecoolConfigUpdate, current_user, db):
    # 1. 校验 CoolingZone 存在 → 404
    # 2. 查询 CoolingLinkageConfig，不存在则创建
    # 3. 记录旧值
    # 4. 更新 precool_enabled / precool_target_temp
    # 5. 写入 OperationLog（module="precool", action="update", old_value, new_value）
    # 6. commit
    # 7. 返回 PrecoolConfigOut
```

### 审计日志模式

```python
from app.models.log import OperationLog
import json

log = OperationLog(
    user_id=current_user.id,
    username=current_user.username,
    module="precool",
    action="update",
    target_type="cooling_linkage_config",
    target_id=config.id,
    target_name=f"zone_{zone_id}_precool_config",
    old_value=json.dumps(old_values),
    new_value=json.dumps(new_values),
)
```

### 集成点

- **CoolingLinkageConfig**: 已有 precool_enabled(Boolean) 和 precool_target_temp(Float, nullable) 字段
- **现有 shift.py 端点**: GET/PUT /shift/cooling/config 操作全量配置，本 Story 只操作预冷子集
- **OperationLog**: 使用 `app.models.log.OperationLog` 记录审计
- **PrecoolExecutor**: `_start_execution` 中检查 `config.precool_enabled`，本配置直接影响执行引擎
- **PrecoolScheduler**: `precool_target_temp` 作为预冷目标温度输入

### Project Structure Notes

- 追加文件：`backend/app/api/v1/precool.py`（追加 2 个配置端点）
- 追加文件：`backend/app/schemas/precool.py`（追加 2 个 Schema）
- 新建文件：`backend/tests/api/test_precool_config_api.py`

### References

- [Source: _bmad-output/planning-artifacts/epics.md — Epic 31, Story 31.4]
- [Source: backend/app/models/load_shift.py — CoolingLinkageConfig]
- [Source: backend/app/models/log.py — OperationLog]
- [Source: backend/app/api/v1/shift.py — 现有 cooling/config 端点]
- [Source: backend/app/services/precool/executor.py — _start_execution 检查 precool_enabled]

## Dev Agent Record

### Agent Model Used

Claude Opus 4.6

### Completion Notes List

- R1: 自动创建配置时必须设置 cooling_zone_id（NOT NULL 字段）
- R1: GET 端点 operator+，PUT 端点 admin only
- R2: 无额外问题，确认配置直接影响 executor 和 scheduler
- 14 个测试全部通过，97 个既有测试无回归

### File List

- `backend/app/api/v1/precool.py` — 追加 2 个配置管理端点（GET/PUT）
- `backend/app/schemas/precool.py` — 追加 PrecoolConfigOut, PrecoolConfigUpdate
- `backend/tests/api/test_precool_config_api.py` — 14 个测试用例
- `_bmad-output/implementation-artifacts/stories/31-4-cooling-linkage-config-precooling-extension.md` — Story 文档
- `_bmad-output/implementation-artifacts/sprint-status.yaml` — 状态更新
