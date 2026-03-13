# Story 32.2: 分阶段部署控制

Status: done

## Story

As a 系统管理员,
I want 通过特性开关控制预冷功能的分阶段上线,
So that 我能安全地逐步推进功能部署。

## 依赖

- Story 29.2（热模型服务，包含 THM/TCL 切换）— done
- Story 32.1（RC 校准服务，calibrator.py）— done

## Acceptance Criteria

1. Given 系统配置表 system_configs 已有特性开关机制
   When 配置预冷部署阶段
   Then 支持 4 个阶段切换：
   - Phase 1: THM 模式（0-2 周）— 仅使用 THM 估算，不执行预冷
   - Phase 2: 校准模式（2-4 周）— 运行 RC 校准，对比 THM 与 TCL 结果
   - Phase 3: TCL 上线（4 周+）— 使用校准后的 TCL 模型执行预冷
   - Phase 4: VPP 接入（8 周+）— 开放 VPP 接口

2. Given 阶段切换到 Phase 3（TCL 上线）
   When 执行前置检查
   Then 检查所有非 demo 区域的 ThermalParameter 记录（`is_active=True` 且 `fitting_method='auto_fit'`，注意：模型无 `is_calibrated` 字段）
   And 检查 `fitting_r_squared >= 0.85`（注意：校准阈值 0.7 是写入门槛，0.85 是上线门槛）
   And 不满足时阻止切换并返回 `{error: "precondition_failed", details: ["区域A未校准", "区域B R²=0.72<0.85"]}`
   And 可通过 `force=true` 参数跳过（仅 admin 角色，记录审计日志）

3. Given 阶段切换到 Phase 4（VPP 接入）
   When 执行前置检查
   Then 检查 `precool_schedules` 表中 `status='completed'` 的记录覆盖 ≥ 7 个不同日期
   And 不满足时阻止切换并返回详细原因
   And 可通过 `force=true` 参数跳过（仅 admin 角色，记录审计日志）

4. Given 部署阶段配置
   When 通过服务层查询/更新
   Then 存储在 `system_configs` 表（`config_group='precool'`, `config_key='deployment_phase'`）
   And 每个阶段可独立开启/关闭
   And 默认初始阶段为 1（THM 模式）

5. Given 阶段切换操作
   When 执行切换
   Then 记录审计日志到 OperationLog（包含旧阶段、新阶段、force 标记、检查结果）
   And 阶段切换记录时间戳

## Tasks / Subtasks

- [ ] Task 1: 部署阶段服务层 (AC: #1, #4)
  - [ ] 1.1 新建 `backend/app/services/precool/deployment_phase.py`
  - [ ] 1.2 实现 `DeploymentPhaseService` 类
  - [ ] 1.3 实现 `get_current_phase()` — 从 system_configs 读取当前阶段
  - [ ] 1.4 实现 `update_phase(new_phase, force, user_id)` — 切换阶段主方法

- [ ] Task 2: 前置检查逻辑 (AC: #2, #3)
  - [ ] 2.1 实现 `_check_phase3_preconditions()` — 校准完成度检查
  - [ ] 2.2 实现 `_check_phase4_preconditions()` — 预冷运行历史检查
  - [ ] 2.3 实现 `_run_precondition_checks(target_phase)` — 统一调度

- [ ] Task 3: 审计日志 (AC: #5)
  - [ ] 3.1 阶段切换写入 OperationLog（module='precool', action='phase_switch'）
  - [ ] 3.2 force 跳过时额外记录告警

- [ ] Task 4: Schema 定义 (AC: #1-5)
  - [ ] 4.1 在 `backend/app/schemas/precool.py` 追加 DeploymentPhase 相关 Schema

- [ ] Task 5: 单元测试 (AC: #1-5)
  - [ ] 5.1 新建 `backend/tests/services/precool/test_deployment_phase.py`
  - [ ] 5.2 测试 get_current_phase（正常/默认值/无记录）
  - [ ] 5.3 测试 Phase 3 前置检查（通过/未校准/R²不足）
  - [ ] 5.4 测试 Phase 4 前置检查（通过/天数不足）
  - [ ] 5.5 测试 force 跳过检查
  - [ ] 5.6 测试阶段切换审计日志
  - [ ] 5.7 测试无效阶段号（<1 或 >4）

## Dev Notes

### 架构设计：分阶段部署控制

参考架构文档 Section 21.7 分阶段实施路径：

| 阶段 | 时间 | 内容 | 安全策略 |
|------|------|------|---------|
| Phase 1 | 0-2 周 | 收集温度/功率数据，部署 THM | 温度裕度法兜底 |
| Phase 2 | 2-4 周 | R/C 自动标定，TCL 与 THM 并行 | TCL 偏差 > 3°C 自动切回 THM |
| Phase 3 | 4 周+ | 正式启用 TCL，推广全部冷通道 | 7 项自动回退保护 |
| Phase 4 | 8 周+ | VPP 可调容量上报，预冷调度优化 | 累积运行数据后开放 |

### SystemConfig 存储模式

使用现有 `system_configs` 表存储部署阶段，**无需新建表或迁移**：

```python
from app.models.config import SystemConfig

# 存储方式
config_group = "precool"
config_key = "deployment_phase"
config_value = "1"        # 阶段号字符串
value_type = "number"
description = "预冷功能部署阶段: 1=THM, 2=校准, 3=TCL上线, 4=VPP接入"
```

**⚠️ 模型导入路径注意:** 正确路径是 `app.models.config.SystemConfig`（不是 `app.models.system_config`）。已有代码中 `datacenter_shift_strategy.py` 用了错误导入路径，不要跟它学。

**现有用法参考：** `command_service.py` 使用 `config_group="command_risk"`，`diagnosis` 服务使用 `config_group="diagnosis"`。本服务使用 `config_group="precool"`。

### Phase 3 前置检查实现

```python
from sqlalchemy import select, and_
from app.models.thermal import ThermalParameter, CoolingZone

async def _check_phase3_preconditions(self, session) -> dict:
    """检查所有非 demo 区域校准状态"""
    # 1. 获取所有非 demo 的 CoolingZone
    # 排除 demo zone: 通过 ThermalParameter.is_demo == True 的 zone_id
    demo_zone_ids = (
        select(ThermalParameter.cooling_zone_id)
        .where(ThermalParameter.is_demo == True)
        .where(ThermalParameter.is_active == True)
        .distinct()
    ).scalar_subquery()

    zones = (await session.execute(
        select(CoolingZone).where(CoolingZone.id.notin_(demo_zone_ids))
    )).scalars().all()

    # 2. 检查每个 zone 的校准状态
    failures = []
    for zone in zones:
        param = (await session.execute(
            select(ThermalParameter)
            .where(ThermalParameter.cooling_zone_id == zone.id)
            .where(ThermalParameter.is_active == True)
            .where(ThermalParameter.is_demo == False)
        )).scalar_one_or_none()

        if param is None or param.fitting_method not in ("auto_fit", "manual"):
            failures.append(f"区域{zone.zone_name}(id={zone.id})未校准(fitting_method={getattr(param, 'fitting_method', None)})")
        elif param.fitting_r_squared is None or param.fitting_r_squared < 0.85:
            r2 = param.fitting_r_squared or 0
            failures.append(f"区域{zone.zone_name}(id={zone.id}) R²={r2:.2f}<0.85")

    # 无非 demo zone 时视为通过（无需校准）
    if not zones:
        return {"passed": True, "details": []}

    return {"passed": len(failures) == 0, "details": failures}
```

### Phase 4 前置检查实现

```python
from sqlalchemy import func
from app.models.thermal import PrecoolSchedule

async def _check_phase4_preconditions(self, session) -> dict:
    """检查预冷执行历史 >= 7 天"""
    result = await session.execute(
        select(func.count(func.distinct(PrecoolSchedule.schedule_date)))
        .where(PrecoolSchedule.status == "completed")
    )
    completed_days = result.scalar() or 0

    if completed_days >= 7:
        return {"passed": True, "details": []}
    else:
        return {
            "passed": False,
            "details": [f"已完成预冷天数={completed_days}<7天，需至少7天成功执行记录"]
        }
```

### 阶段切换主方法

```python
async def update_phase(self, new_phase: int, force: bool, user_id: int, username: str = "") -> dict:
    """切换部署阶段"""
    if new_phase < 1 or new_phase > 4:
        return {"error": "invalid_phase", "details": f"阶段必须在1-4之间，当前请求: {new_phase}"}

    async with async_session() as session:
        # 1. 获取当前阶段
        current = await self._get_phase_config(session)
        old_phase = int(current.config_value) if current else 1

        if old_phase == new_phase:
            return {"error": "same_phase", "details": f"已处于阶段{new_phase}"}

        # 2. 前置检查（仅向上切换时）
        check_result = {"passed": True, "details": []}
        if new_phase >= 3 and not force:
            check_result = await self._check_phase3_preconditions(session)
        if new_phase >= 4 and not force:
            phase4_result = await self._check_phase4_preconditions(session)
            if not phase4_result["passed"]:
                check_result["passed"] = False
                check_result["details"].extend(phase4_result["details"])

        if not check_result["passed"] and not force:
            return {
                "error": "precondition_failed",
                "details": check_result["details"]
            }

        # 3. 更新阶段
        if current:
            current.config_value = str(new_phase)
            current.updated_by = user_id
        else:
            session.add(SystemConfig(
                config_group="precool",
                config_key="deployment_phase",
                config_value=str(new_phase),
                value_type="number",
                description="预冷功能部署阶段: 1=THM, 2=校准, 3=TCL上线, 4=VPP接入",
                updated_by=user_id,
            ))

        # 4. 审计日志
        from app.models.log import OperationLog
        log = OperationLog(
            user_id=user_id,
            username=username,
            module="precool",
            action="phase_switch",
            target_type="deployment_phase",
            target_id=0,
            target_name=f"phase_{old_phase}_to_{new_phase}",
            old_value=json.dumps({"phase": old_phase}),
            new_value=json.dumps({
                "phase": new_phase,
                "force": force,
                "check_result": check_result
            }),
        )
        session.add(log)

        try:
            await session.commit()
        except Exception as e:
            await session.rollback()
            logger.error(f"部署阶段切换提交失败: {e}")
            return {"error": "commit_failed", "details": str(e)}

        return {"phase": new_phase, "old_phase": old_phase, "force_used": force}
```

### OperationLog 审计模式

参考 `precool.py:906-917` 已有审计日志模式：

```python
from app.models.log import OperationLog

log = OperationLog(
    user_id=current_user.id,
    username=current_user.username,
    module="precool",
    action="phase_switch",           # 固定动作名
    target_type="deployment_phase",   # 目标类型
    target_id=0,                      # 无关联 ID
    target_name=f"phase_{old}_to_{new}",
    old_value=json.dumps({"phase": old_phase}),
    new_value=json.dumps({"phase": new_phase, "force": force}),
)
```

### Schema 追加（在 precool.py 末尾）

```python
# ==================== Story 32.2: 部署阶段 Schema ====================

class DeploymentPhaseOut(BaseModel):
    """部署阶段查询响应"""
    current_phase: int = Field(ge=1, le=4)
    phase_name: str
    description: str
    updated_at: Optional[datetime] = None

class DeploymentPhaseUpdate(BaseModel):
    """部署阶段切换请求"""
    phase: int = Field(ge=1, le=4, description="目标阶段: 1=THM, 2=校准, 3=TCL上线, 4=VPP接入")
    force: bool = Field(default=False, description="强制跳过前置检查（仅 admin）")

class PreconditionCheckResult(BaseModel):
    """前置检查结果"""
    passed: bool
    details: List[str] = []
```

### 阶段名称映射

```python
PHASE_NAMES = {
    1: ("THM 模式", "仅使用 THM 估算，不执行预冷"),
    2: ("校准模式", "运行 RC 校准，对比 THM 与 TCL 结果"),
    3: ("TCL 上线", "使用校准后的 TCL 模型执行预冷"),
    4: ("VPP 接入", "开放 VPP 接口"),
}
```

### Project Structure Notes

- **新建文件:** `backend/app/services/precool/deployment_phase.py` — 部署阶段服务
- **新建文件:** `backend/tests/services/precool/test_deployment_phase.py` — 测试
- **修改文件:** `backend/app/schemas/precool.py` — 追加 DeploymentPhase Schema
- **不新建表:** 使用现有 `system_configs` 表
- **不新建迁移:** 初始记录在服务层按需创建（首次查询时如无记录则默认阶段1）
- **不修改 API 路由:** 端点实现留给 Story 32.3

### 服务层 Session 管理模式

**采用 self-managing 模式**（与 Story 32.1 RCCalibrator 一致）：服务内部创建自己的 `async_session()`，不接受外部传入的 session。

```python
from app.core.database import async_session

class DeploymentPhaseService:
    async def get_current_phase(self) -> dict:
        async with async_session() as session:
            # 读取 system_configs
            ...

    async def update_phase(self, new_phase: int, force: bool, user_id: int, username: str) -> dict:
        async with async_session() as session:
            # 更新 + 审计日志 + commit
            ...
```

**API 层调用方式**（Story 32.3 实现端点时参考）：
```python
from app.services.precool.deployment_phase import deployment_phase_service

@router.get("/deployment-phase")
async def get_deployment_phase(_=Depends(require_role(["admin", "operator", "viewer"]))):
    return await deployment_phase_service.get_current_phase()
```

### 关键约束

- **R² 阈值区分:** 校准写入阈值 `MIN_R_SQUARED=0.7`（Story 32.1），上线阈值 `0.85`（本 Story）。两个阈值不同，不要混淆。
- **非 demo zone 过滤:** 与 Story 32.1 calibrator.py `run_monthly_calibration()` 相同的子查询模式
- **force 参数:** 仅 admin 可使用，且必须记录审计日志
- **向下切换:** 阶段可以降级（如从 3 回退到 2），降级不需要前置检查
- **事务安全:** 阶段更新 + 审计日志在同一事务中

### References

- [Source: _bmad-output/planning-artifacts/epics.md — Epic 32, Story 32.2, line 4136-4166]
- [Source: _bmad-output/planning-artifacts/architecture.md — Section 21.7 分阶段实施路径]
- [Source: backend/app/models/config.py — SystemConfig 模型定义]
- [Source: backend/app/models/thermal.py — ThermalParameter, PrecoolSchedule 模型]
- [Source: backend/app/api/v1/precool.py — 现有端点和 require_role 模式]
- [Source: backend/app/schemas/precool.py — 现有 Schema 模式]
- [Source: backend/app/services/precool/calibrator.py — 非 demo zone 过滤模式]
- [Source: _bmad-output/implementation-artifacts/stories/32-1-*.md — Story 32.1 经验和代码模式]

## Dev Agent Record

### Agent Model Used

Claude Opus 4.6

### Debug Log References

### Completion Notes List

- R1 审查发现 2P0+1P1: is_calibrated字段不存在→改用fitting_method/is_active，zone.name→zone.zone_name，session管理模式明确为self-managing
- R2 审查修复: username参数统一、commit异常处理、空zone处理
- 代码审查修复: 降级时不应触发前置检查(加is_upgrade条件)、config_value解析加错误处理
- 27个单元测试全部通过(6个测试类)

### File List

- `backend/app/services/precool/deployment_phase.py` — 分阶段部署控制服务（新建）
- `backend/tests/services/precool/test_deployment_phase.py` — 单元测试（新建）
- `backend/app/schemas/precool.py` — 追加 DeploymentPhase Schema
- `_bmad-output/implementation-artifacts/stories/32-2-phased-deployment-control.md` — Story 文档
