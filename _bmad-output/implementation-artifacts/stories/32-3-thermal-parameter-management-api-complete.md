# Story 32.3: 热参数管理 API 完整实现

Status: done

## Story

As a 系统管理员,
I want 通过 API 管理所有热参数和校准任务,
So that 我能灵活控制热模型的运行。

## 依赖

- Story 32.1（校准服务 calibrator.py, `rc_calibrator.calibrate(zone_id)`）— done
- Story 32.2（分阶段部署 deployment_phase.py, `deployment_phase_service`）— done

## Acceptance Criteria

1. Given 校准服务已实现
   When 调用 `POST /api/v1/precool/zones/{zone_id}/calibrate`
   Then 触发手动 RC 校准（调用 `rc_calibrator.calibrate(zone_id)`）
   And 返回校准结果（R, C, r_squared, sample_count）或错误信息
   And 权限: admin + operator

2. Given 校准历史存储在 ThermalParameter 表
   When 调用 `GET /api/v1/precool/zones/{zone_id}/calibration-history`
   Then 返回分页校准历史（使用现有 ThermalParameterOut schema）
   And 权限: admin + operator + viewer

3. Given 部署阶段服务已实现
   When 调用 `GET /api/v1/precool/deployment-phase`
   Then 返回当前部署阶段（phase, phase_name, description, updated_at）
   And 权限: admin + operator + viewer

4. Given 部署阶段服务已实现
   When 调用 `PUT /api/v1/precool/deployment-phase`
   Then 切换部署阶段（含前置检查和 force 参数）
   And 权限: 仅 admin
   And 返回新阶段或前置检查失败详情

5. Given 所有端点
   When 校验 zone 不存在
   Then 返回 `{"code": 404, "message": "..."}`
   And 遵循现有 precool.py 的统一响应格式 `{"code": N, "message": "...", "data": ...}`

## Tasks / Subtasks

- [ ] Task 1: 手动校准端点 (AC: #1)
  - [ ] 1.1 在 precool.py 追加 `POST /zones/{zone_id}/calibrate`
  - [ ] 1.2 校验 zone 存在，调用 `rc_calibrator.calibrate(zone_id)`
  - [ ] 1.3 scipy 未安装时返回 503

- [ ] Task 2: 校准历史端点 (AC: #2)
  - [ ] 2.1 追加 `GET /zones/{zone_id}/calibration-history`
  - [ ] 2.2 分页查询 ThermalParameter（is_demo=False），按 created_at desc 排序

- [ ] Task 3: 部署阶段端点 (AC: #3, #4)
  - [ ] 3.1 追加 `GET /deployment-phase`
  - [ ] 3.2 追加 `PUT /deployment-phase`（admin only + 审计日志）

- [ ] Task 4: API 测试 (AC: #1-5)
  - [ ] 4.1 新建 `backend/tests/api/test_precool_management.py`
  - [ ] 4.2 测试手动校准（成功/zone不存在/scipy缺失）
  - [ ] 4.3 测试校准历史（正常/空历史/分页）
  - [ ] 4.4 测试部署阶段查询和切换

## Dev Notes

### 现有端点模式参考

precool.py 统一响应格式：
```python
# 成功
return {"code": 200, "message": "success", "data": {...}}
# 失败
return {"code": 404, "message": "制冷区域 X 不存在", "data": None}
return {"code": 500, "message": "内部错误", "data": None}
```

### 手动校准端点实现

```python
# ==================== Story 32.3: 热参数管理 API ====================

@router.post("/zones/{zone_id}/calibrate", summary="触发手动 RC 校准")
async def trigger_calibration(
    zone_id: int,
    db: AsyncSession = Depends(get_db),
    _=Depends(require_role(["admin", "operator"])),
):
    """手动触发指定区域的 RC 参数校准"""
    try:
        from ...models.topology_config import CoolingZone

        # 校验 zone 存在
        zone = (await db.execute(
            select(CoolingZone).where(CoolingZone.id == zone_id)
        )).scalar_one_or_none()
        if zone is None:
            return {"code": 404, "message": f"制冷区域 {zone_id} 不存在", "data": None}

        # 调用校准服务（self-managing session）
        from ...services.precool.calibrator import rc_calibrator
        result = await rc_calibrator.calibrate(zone_id)

        if "error" in result:
            error = result["error"]
            if error == "scipy_not_installed":
                return {"code": 503, "message": "scipy 未安装，校准功能不可用", "data": None}
            return {"code": 422, "message": f"校准失败: {error}", "data": result}

        return {"code": 200, "message": "success", "data": result}

    except Exception as e:
        logger.error(f"手动校准异常: zone_id={zone_id}, error={e}")
        return {"code": 500, "message": "内部错误", "data": None}
```

**⚠️ 关键注意:** `rc_calibrator.calibrate()` 使用 self-managing session（内部创建自己的 async_session），不要传入 API 层的 db session。直接调用即可。

### 校准历史端点

```python
@router.get("/zones/{zone_id}/calibration-history", summary="查询校准历史")
async def get_calibration_history(
    zone_id: int,
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    _=Depends(require_role(["admin", "operator", "viewer"])),
):
    """返回指定区域的校准历史记录"""
```

**注意：** 与现有 `/zones/{zone_id}/parameters` 端点（Story 29.4, line 150）**不是重复**：
- `/parameters`：返回所有 ThermalParameter（含 demo），用于调试和完整参数历史
- `/calibration-history`：仅返回非 demo 记录（`is_demo=False`），面向管理员查看真实校准历史
- 新端点必须加 `.where(ThermalParameter.is_demo == False)` 过滤

### 部署阶段端点

```python
@router.get("/deployment-phase", summary="查询当前部署阶段")
async def get_deployment_phase(
    _=Depends(require_role(["admin", "operator", "viewer"])),
):
    """返回当前预冷功能部署阶段"""
    # deployment_phase_service 使用 self-managing session
    from ...services.precool.deployment_phase import deployment_phase_service
    result = await deployment_phase_service.get_current_phase()
    return {"code": 200, "message": "success", "data": result}


@router.put("/deployment-phase", summary="切换部署阶段")
async def update_deployment_phase(
    request: DeploymentPhaseUpdate,
    current_user=Depends(require_role(["admin"])),
):
    """切换预冷功能部署阶段（仅 admin）"""
    from ...services.precool.deployment_phase import deployment_phase_service
    result = await deployment_phase_service.update_phase(
        new_phase=request.phase,
        force=request.force,
        user_id=current_user.id,
        username=current_user.username,
    )
    if "error" in result:
        if result["error"] == "precondition_failed":
            return {"code": 422, "message": "前置条件不满足", "data": result}
        return {"code": 400, "message": result.get("details", result["error"]), "data": result}
    return {"code": 200, "message": "success", "data": result}
```

### import 追加

在 precool.py 顶部的 import 列表追加（必须，否则 PUT 端点会报 NameError）：
```python
from ...schemas.precool import (
    ...,
    DeploymentPhaseUpdate,
)
```
**注意:** `DeploymentPhaseOut` 不需要导入 — GET 端点直接返回 service 的 dict 结果，不经过 Pydantic 序列化。

### 不需要新建 Schema

Story 32.2 已追加 `DeploymentPhaseOut`, `DeploymentPhaseUpdate`, `PreconditionCheckResult`。
校准历史使用现有 `ThermalParameterOut`。
手动校准结果直接返回 dict（与 calibrator.calibrate() 返回值一致）。

### Project Structure Notes

- **修改文件:** `backend/app/api/v1/precool.py` — 追加 4 个端点
- **新建文件:** `backend/tests/api/test_precool_management.py` — API 测试
- **不修改 Schema:** 已有全部所需 Schema
- **不修改服务层:** calibrator + deployment_phase_service 已完整实现

### 关键约束

- **Self-managing session 服务调用:** `rc_calibrator` 和 `deployment_phase_service` 都使用内部 session，API 层不传 db
- **zone 存在性校验:** 校准端点需先查 CoolingZone，与其他端点模式一致
- **部署阶段切换权限:** PUT 仅 admin（`require_role(["admin"])`），GET 允许 viewer
- **统一响应格式:** `{"code": N, "message": "...", "data": ...}`

### References

- [Source: _bmad-output/planning-artifacts/epics.md — Story 32.3, line 4168-4190]
- [Source: backend/app/api/v1/precool.py — 现有端点模式]
- [Source: backend/app/services/precool/calibrator.py — rc_calibrator.calibrate() 接口]
- [Source: backend/app/services/precool/deployment_phase.py — deployment_phase_service 接口]
- [Source: backend/app/schemas/precool.py — 已有全部 Schema]
- [Source: _bmad-output/implementation-artifacts/stories/32-2-*.md — Story 32.2 服务层设计]

## Dev Agent Record

### Agent Model Used

Claude Opus 4.6

### Debug Log References

### Completion Notes List

- R1 审查: 明确 /calibration-history 与 /parameters 区别（is_demo=False 过滤），DeploymentPhaseOut 不需导入
- R2 审查: 无新增问题
- 代码审查修复: GET/PUT deployment-phase 端点补充 try/except 统一异常处理
- 16 个 API 测试全部通过（4 个测试类）

### File List

- `backend/app/api/v1/precool.py` — 追加 4 个端点（手动校准、校准历史、部署阶段查询/切换）
- `backend/tests/api/test_precool_management.py` — API 测试（新建）
- `_bmad-output/implementation-artifacts/stories/32-3-thermal-parameter-management-api-complete.md` — Story 文档
