# Story 31.3: 预冷计划 API 端点

Status: done

## Story

As a 前端开发人员,
I want 后端提供预冷计划管理的 REST API,
So that 前端可以展示和管理预冷计划。

## 依赖

- Story 31.1（贪心优化预冷调度算法）— done
- Story 31.2（预冷计划执行引擎）— done

## Acceptance Criteria

1. Given 预冷调度和执行服务已实现
   When 前端调用 `POST /api/v1/precool/zones/{zone_id}/schedule`
   Then 系统生成日前预冷计划，返回计划详情含温度轨迹
   And 权限要求 operator+（admin/operator）
   And 同一 zone+date 不允许重复生成（唯一约束冲突返回 409）

2. Given 已有预冷计划
   When 前端调用 `GET /api/v1/precool/zones/{zone_id}/schedule`
   Then 返回该 zone 的计划列表，支持分页和 status 筛选
   And 权限要求 operator+

3. Given 计划已存在
   When 前端调用 `GET /api/v1/precool/schedules/{schedule_id}`
   Then 返回计划详情含完整温度轨迹（predicted、actual、q_cool、q_cool_actual、timestamps、prices）
   And 权限要求 operator+

4. Given 计划状态为 executing
   When 前端调用 `POST /api/v1/precool/schedules/{schedule_id}/abort`
   Then 中止执行中的计划，返回 `{status, abort_reason}`
   And 恢复制冷功率到基线
   And 非 executing 状态返回 400
   And 权限要求 operator+

## Tasks / Subtasks

- [x] Task 0: 在 PrecoolExecutor 中新增公共 abort 方法 (AC: #4)
  - [x] 0.1 在 `backend/app/services/precool/executor.py` 新增 `async def abort_plan_by_api(plan, reason, session)` 公共方法
  - [x] 0.2 封装 `_get_current_step_index()` + `_get_actual_temperature()` + `_abort_plan()` 调用
  - [x] 0.3 API 层不再直接调用私有方法

- [x] Task 1: 创建预冷计划 API Schema (AC: #1-4)
  - [x] 1.1 在 `backend/app/schemas/precool.py` 追加 `ScheduleCreateRequest`（schedule_date, time_slots 可选）
  - [x] 1.2 追加 `ScheduleListItem`（不含 temperature_trajectory，用于列表接口）
  - [x] 1.3 追加 `ScheduleDetailOut`（from_attributes=True，含所有字段含 trajectory，用于详情接口）
  - [x] 1.4 追加 `ScheduleAbortRequest`（reason 可选）
  - [x] 1.5 追加 `ScheduleAbortResponse`（status, abort_reason）

- [x] Task 2: 实现 4 个 API 端点 (AC: #1-4)
  - [x] 2.1 `POST /zones/{zone_id}/schedule` — 调用 PrecoolScheduler.generate_precool_plan，API 层自行 session.add + commit（不调用 save_plan 避免双重 commit）
  - [x] 2.2 `GET /zones/{zone_id}/schedule` — 分页查询 + status 筛选，返回 ScheduleListItem（不含 trajectory）
  - [x] 2.3 `GET /schedules/{schedule_id}` — 单条详情查询，返回 ScheduleDetailOut（含 trajectory）
  - [x] 2.4 `POST /schedules/{schedule_id}/abort` — 调用 `precool_executor.abort_plan_by_api()` 公共方法

- [x] Task 3: 错误处理和边界情况 (AC: #1, #4)
  - [x] 3.1 zone_id 不存在返回 404
  - [x] 3.2 同 zone+date 重复生成返回 409（IntegrityError 捕获，rollback 后返回）
  - [x] 3.3 schedule_id 不存在返回 404
  - [x] 3.4 abort 非 executing 状态返回 400
  - [x] 3.5 捕获 PrecoolPlanError 异常返回 422（含 error、reason、suggestions 字段）
  - [x] 3.6 IntegrityError 捕获后必须 `await session.rollback()` 再返回 409

- [x] Task 4: 单元测试 (AC: #1-4)
  - [x] 4.1 创建 `backend/tests/api/test_precool_schedule_api.py`
  - [x] 4.2 测试生成计划成功（mock scheduler）
  - [x] 4.3 测试重复生成返回 409
  - [x] 4.4 测试计划列表分页和筛选
  - [x] 4.5 测试计划详情查询（含 trajectory）
  - [x] 4.6 测试中止计划成功和失败（executing vs 其他状态）
  - [x] 4.7 测试权限检查（viewer 角色被拒）
  - [x] 4.8 测试算法不可行返回 422
  - [x] 4.9 目标 ≥12 个测试用例

## Dev Notes

### 端点设计伪代码

```python
# POST /zones/{zone_id}/schedule
async def create_schedule(zone_id, request: ScheduleCreateRequest, db):
    # 1. 校验 zone 存在（select CoolingZone），不存在 → 404
    # 2. 加载 time_slots（request 提供或从 DB 读取 load_time_slots_from_db）
    # 3. try: PrecoolScheduler().generate_precool_plan(zone_id, schedule_date, session, time_slots)
    #    except PrecoolPlanError as e → 422（含 e.error, e.reason, e.suggestions）
    # 4. session.add(result.schedule) + try await session.commit()
    #    except IntegrityError → await session.rollback() + 409
    # 5. 返回 ScheduleDetailOut

# GET /zones/{zone_id}/schedule
async def list_schedules(zone_id, skip, limit, status, db):
    # 1. 校验 zone 存在，不存在 → 404
    # 2. 查询 PrecoolSchedule where cooling_zone_id == zone_id
    # 3. 可选 status 筛选
    # 4. 分页 + 排序（schedule_date desc）
    # 5. 返回 {items: [ScheduleListItem], total}（不含 trajectory）

# GET /schedules/{schedule_id}
async def get_schedule(schedule_id, db):
    # 1. 查询 PrecoolSchedule by id
    # 2. 不存在 → 404
    # 3. 返回 ScheduleDetailOut（含完整 temperature_trajectory）

# POST /schedules/{schedule_id}/abort
async def abort_schedule(schedule_id, request: ScheduleAbortRequest, db):
    # 1. 查询 PrecoolSchedule by id
    # 2. 不存在 → 404
    # 3. status != "executing" → 400
    # 4. 调用 precool_executor.abort_plan_by_api(plan, reason, session)
    # 5. commit
    # 6. 返回 ScheduleAbortResponse
```

### PrecoolExecutor 公共 abort 方法

```python
# 在 executor.py 中新增
async def abort_plan_by_api(self, plan: PrecoolSchedule, reason: str, session: AsyncSession):
    """API 层调用的公共中止方法（封装内部状态获取）"""
    step_index = self._get_current_step_index()
    actual_temp = await self._get_actual_temperature(plan.cooling_zone_id, session)
    await self._abort_plan(plan, reason, step_index, actual_temp, session)
```

### 集成点

- **PrecoolScheduler**: `generate_precool_plan()` 返回 `PrecoolPlanResult`，schedule=None 表示不可行
- **PrecoolExecutor**: 新增公共方法 `abort_plan_by_api()` 封装私有方法调用
- **PrecoolSchedule 模型**: 已有 UniqueConstraint(cooling_zone_id, schedule_date)
- **save_plan 注意**: API 层不调用 save_plan（它内部 commit），改为 session.add + 自行 commit 以控制事务
- **权限**: 使用 `require_role(["admin", "operator"])` 依赖注入
- **路由**: 追加到现有 `backend/app/api/v1/precool.py`，无需修改 `__init__.py`

### 现有 precool.py 端点（7 个，来自 Story 29.4 和 30.3）

- POST /zones/{zone_id}/predict
- GET /zones/{zone_id}/parameters
- GET /zones/{zone_id}/validation
- GET /dashboard
- GET /zones/{zone_id}/rollback-status
- GET /zones/{zone_id}/rollback-history
- GET /rollback-overview

### Project Structure Notes

- 追加文件：`backend/app/api/v1/precool.py`（追加 4 端点）
- 追加文件：`backend/app/schemas/precool.py`（追加 4 个 Schema）
- 新建文件：`backend/tests/api/test_precool_schedule_api.py`
- 现有路由前缀 `/precool` 已在 `__init__.py` 注册，新增端点自动挂载

### References

- [Source: _bmad-output/planning-artifacts/epics.md — Epic 31, Story 31.3]
- [Source: backend/app/services/precool/scheduler.py — PrecoolScheduler.generate_precool_plan]
- [Source: backend/app/services/precool/executor.py — PrecoolExecutor._abort_plan]
- [Source: backend/app/models/thermal.py — PrecoolSchedule]
- [Source: backend/app/api/v1/precool.py — 现有 7 个端点模式]
- [Source: backend/app/schemas/precool.py — 现有 Schema 模式]

## Dev Agent Record

### Agent Model Used

Claude Opus 4.6

### Completion Notes List

- 两轮对抗性审查发现并修复 3 个 P0 + 3 个 P1 问题
- P0-1: abort 端点需公共方法封装（新增 abort_plan_by_api）
- P0-2: generate_precool_plan 错误通过 PrecoolPlanError 异常而非 schedule=None
- P0-3: API 需捕获 PrecoolPlanError 而非检查 None
- P1-1: 列表接口不返回 trajectory（ScheduleListItem vs ScheduleDetailOut）
- P1-2: API 层自行 commit，不调用 save_plan 避免双重 commit
- P1-3: IntegrityError 捕获后需 rollback
- 修复 PrecoolSchedule 模型重复索引问题（status 列 index=True 与 __table_args__ Index 冲突）
- 18 个测试全部通过，79 个既有测试无回归

### File List

- `backend/app/api/v1/precool.py` — 追加 4 个计划管理端点 + 2 个转换函数
- `backend/app/schemas/precool.py` — 追加 5 个 Schema（ScheduleCreateRequest, ScheduleListItem, ScheduleDetailOut, ScheduleAbortRequest, ScheduleAbortResponse）
- `backend/app/services/precool/executor.py` — 新增 abort_plan_by_api() 公共方法
- `backend/app/models/thermal.py` — 移除重复索引定义
- `backend/tests/api/test_precool_schedule_api.py` — 18 个测试用例
- `_bmad-output/implementation-artifacts/stories/31-3-precooling-plan-api-endpoint.md` — Story 文档
- `_bmad-output/implementation-artifacts/sprint-status.yaml` — 状态更新
