# Story 33.2: VPP 调控指令接收与执行

Status: done

## Story

As a VPP 平台运营人员,
I want 向数据中心下发负荷调控指令并获取执行反馈,
So that 我能通过虚拟电厂协调数据中心参与电网需求响应。

## 依赖

- Story 33.1（VPP 可调容量上报）— done
- Story 31.1（调度算法）— done
- Story 31.2（执行引擎）— done

## Acceptance Criteria

1. Given 部署阶段为 4（VPP 接入）
   When VPP 平台调用 `POST /api/v1/precool/vpp/dispatch`
   Then 接收调控指令，包含 command_type（down_adjust/up_adjust）、target_power_kw、duration_minutes、priority
   And 返回统一格式 `{"code": N, "message": "...", "data": {...}}`

2. Given 部署阶段不是 4
   When 调用调控指令接口
   Then 返回 code=403，message="VPP 接口仅在部署阶段 4 可用"

3. Given VPP 独立认证
   When 请求缺少 `X-VPP-API-Key` header 或 API Key 无效
   Then 返回 code=401，message="VPP 认证失败"
   And 此认证与系统内部 JWT 认证分离

4. Given 速率限制
   When 同一小时内调控指令超过 12 条
   Then 返回 code=429，message="超出速率限制（每小时最多 12 条）"
   And 使用 Redis 计数器实现（key=vpp:dispatch:rate:{hour}，TTL=3600s）

5. Given 安全约束校验
   When 请求的 target_power_kw 超过当前可调容量
   Then 拒绝指令，status=rejected
   And 返回 reject_reason 和 max_adjustable_kw（当前最大可调容量）
   And 向下可调容量从 vpp_capacity_service 获取

6. Given 冲突检测（down_adjust 指令）
   When VPP 要求削减制冷（down_adjust）且当前存在执行中的预冷计划
   Then 中止预冷计划（调用 executor.abort_plan_by_api），abort_reason='vpp_override'
   And 在 VppDispatch 记录中关联被中止的 schedule_id

7. Given 约束校验通过
   When 指令被接受
   Then 创建 VppDispatch 记录（status=accepted），持久化到 vpp_dispatches 表
   And 返回 dispatch_id、status=accepted、accepted_power_kw

8. Given 所有新增代码
   When 运行测试
   Then 单元测试全部通过，无 Python 错误

## Tasks / Subtasks

- [x] Task 1: VppDispatch 数据模型 (AC: #7)
  - [x] 1.1 在 `backend/app/models/thermal.py` 追加 VppDispatch 模型
  - [x] 1.2 在 `backend/app/models/__init__.py` 注册导出
  - [ ] 1.3 Alembic 迁移脚本生成（推迟到部署时统一执行）

- [x] Task 2: VPP 调控服务 (AC: #1, #5, #6, #7)
  - [x] 2.1 新建 `backend/app/services/precool/vpp_dispatch.py`
  - [x] 2.2 实现 VppDispatchService 类：validate_and_execute()
  - [x] 2.3 实现安全约束校验（复用 vpp_capacity_service.calculate_capacity()）
  - [x] 2.4 实现冲突检测与预冷计划中止（复用 executor.abort_plan_by_api()）

- [x] Task 3: API 端点与认证 (AC: #1, #2, #3, #4)
  - [x] 3.1 在 precool.py 追加 `POST /vpp/dispatch` 端点
  - [x] 3.2 实现 VPP API Key 认证依赖（verify_vpp_api_key）
  - [x] 3.3 实现速率限制依赖（check_vpp_rate_limit）
  - [x] 3.4 在 config.py 追加 VPP_API_KEY 配置项

- [x] Task 4: Schema 定义 (AC: #1)
  - [x] 4.1 在 precool.py Schema 中追加 VppDispatchRequest、VppDispatchResponse

- [x] Task 5: 单元测试 (AC: #8)
  - [x] 5.1 新建 `backend/tests/services/precool/test_vpp_dispatch.py`
  - [x] 5.2 新建 `backend/tests/api/test_vpp_dispatch.py`

## Dev Notes

### VppDispatch 数据模型

在 `backend/app/models/thermal.py` 追加（与 PrecoolSchedule 同文件）：

```python
class VppDispatch(Base):
    """VPP 调控指令记录"""
    __tablename__ = "vpp_dispatches"

    id = Column(Integer, primary_key=True, index=True)
    dispatch_id = Column(String(64), unique=True, nullable=False)  # UUID 外部标识
    command_type = Column(String(20), nullable=False)  # down_adjust / up_adjust
    target_power_kw = Column(Float, nullable=False)    # 请求调控功率 (kW_e)
    duration_minutes = Column(Integer, nullable=False)  # 持续时间（分钟）
    priority = Column(Integer, default=1)              # 优先级（1=普通, 2=紧急）

    status = Column(String(20), nullable=False, default="received")
    # status 值: received → accepted/rejected; accepted → executing → completed/failed

    reject_reason = Column(Text, nullable=True)        # 拒绝原因
    max_adjustable_kw = Column(Float, nullable=True)   # 拒绝时返回的最大可调容量
    accepted_power_kw = Column(Float, nullable=True)   # 实际接受的调控功率

    aborted_schedule_id = Column(Integer, nullable=True)  # 被中止的预冷计划 ID

    created_at = Column(DateTime, default=func.now())
    completed_at = Column(DateTime, nullable=True)
```

**⚠️ 导入约束：** 模型文件已有 `from sqlalchemy import Column, Integer, String, Float, Text, DateTime, ForeignKey, Boolean, JSON` 和 `from sqlalchemy.sql import func`，直接使用即可。

### VPP API Key 认证

在 `backend/app/core/config.py` 的 Settings 类追加：

```python
# VPP 对外接口认证 (Story 33.2)
VPP_API_KEY: str = Field(default="dcim-vpp-default-key-change-me", description="VPP 平台 API Key")
```

在 `backend/app/api/v1/precool.py` 实现认证依赖：

```python
from fastapi import Header  # 需追加到 precool.py 现有 fastapi import 行

async def verify_vpp_api_key(x_vpp_api_key: str = Header(None)):
    """VPP 独立 API Key 认证（与 JWT 分离）"""
    from ...core.config import get_settings  # lazy import，与 precool.py 模式一致
    settings = get_settings()
    if not x_vpp_api_key or x_vpp_api_key != settings.VPP_API_KEY:
        return None  # 认证失败，由端点处理
    return x_vpp_api_key
```

**⚠️ import 修改：** 需将 `from fastapi import APIRouter, Depends, Query` 改为 `from fastapi import APIRouter, Depends, Query, Header`。

**⚠️ 不要使用 HTTPException：** 与 precool.py 现有模式一致，返回 dict `{"code": 401, ...}`。因此认证函数返回 None 表示失败，由端点自行判断并返回错误响应。

### 速率限制

使用 Redis `get_json`/`set_json` 模拟计数器（RedisService 没有 `increment`/`expire` 方法）：

```python
from app.core.redis import redis_service
from datetime import datetime

async def check_vpp_rate_limit() -> bool:
    """检查 VPP 调控指令速率限制（每小时 ≤ 12 条）"""
    hour_key = f"vpp:dispatch:rate:{datetime.now().strftime('%Y%m%d%H')}"
    try:
        count_data = await redis_service.get_json(hour_key)
        current = count_data if isinstance(count_data, int) else 0
        if current >= 12:
            return False  # 超限
        await redis_service.set_json(hour_key, current + 1, ttl=3600)
        return True
    except Exception:
        # Redis 不可用时放行（降级策略）
        return True
```

**⚠️ Redis API:** RedisService 只有 `get`/`set`/`get_json`/`set_json`/`delete`/`mget`/`sismember`/`sadd_with_ttl` 方法。没有 `increment`/`expire`。

### VPP 调控服务核心逻辑

新建 `backend/app/services/precool/vpp_dispatch.py`：

```python
class VppDispatchService:
    MAX_RATE_PER_HOUR = 12

    async def validate_and_execute(self, request: dict) -> dict:
        """验证并处理 VPP 调控指令"""
        async with async_session() as session:
            # 1. 创建 VppDispatch 记录（status=received）
            dispatch = VppDispatch(
                dispatch_id=str(uuid.uuid4()),
                command_type=request["command_type"],
                target_power_kw=request["target_power_kw"],
                duration_minutes=request["duration_minutes"],
                priority=request.get("priority", 1),
                status="received",
            )
            session.add(dispatch)

            # 2. 获取当前可调容量
            from .vpp_capacity import vpp_capacity_service
            capacity = await vpp_capacity_service.calculate_capacity()

            # 3. 确定可调容量上限
            if request["command_type"] == "down_adjust":
                max_kw = capacity["down_adjustable_kw"]
            else:  # up_adjust
                max_kw = capacity["up_adjustable_kw"]

            # 4. 安全约束校验
            if request["target_power_kw"] > max_kw:
                dispatch.status = "rejected"
                dispatch.reject_reason = f"请求功率 {request['target_power_kw']:.1f} kW 超过可调容量 {max_kw:.1f} kW"
                dispatch.max_adjustable_kw = max_kw
                await session.commit()
                return self._build_response(dispatch)

            # 5. 冲突检测（仅 down_adjust 需要检查预冷计划冲突）
            if request["command_type"] == "down_adjust":
                aborted_id = await self._check_and_abort_conflicts(session)
                if aborted_id:
                    dispatch.aborted_schedule_id = aborted_id

            # 6. 接受指令
            dispatch.status = "accepted"
            dispatch.accepted_power_kw = min(request["target_power_kw"], max_kw)
            await session.commit()

            return self._build_response(dispatch)
```

### 冲突检测实现

```python
async def _check_and_abort_conflicts(self, session) -> Optional[int]:
    """检查并中止与 VPP down_adjust 冲突的执行中预冷计划"""
    from datetime import datetime
    now = datetime.now()

    # 查找执行中的预冷计划（status='executing' 且处于预冷时段）
    # ⚠️ precool_start_time/precool_end_time 是 Time 类型（非 DateTime），需分别比较 date 和 time
    today = now.date()
    current_time = now.time()
    result = await session.execute(
        select(PrecoolSchedule).where(
            PrecoolSchedule.status == "executing",
            PrecoolSchedule.schedule_date == today,
            PrecoolSchedule.precool_start_time <= current_time,
            PrecoolSchedule.precool_end_time > current_time,
        )
    )
    active_plans = result.scalars().all()

    if not active_plans:
        return None

    # 中止第一个冲突计划（VPP 优先级 > 预冷计划）
    plan = active_plans[0]
    from .executor import precool_executor
    await precool_executor.abort_plan_by_api(
        plan, "vpp_override", session
    )

    logger.info(
        "VPP 指令中止预冷计划: schedule_id=%d, zone_id=%d",
        plan.id, plan.cooling_zone_id,
    )
    return plan.id
```

**⚠️ executor 导入：** `precool_executor_service` 是 executor.py 的全局单例。确认导入路径: `from .executor import precool_executor_service`。

### API 端点设计

在 `precool.py` 追加：

```python
@router.post("/vpp/dispatch", summary="接收 VPP 调控指令")
async def receive_vpp_dispatch(
    request: VppDispatchRequest,
    api_key: str = Depends(verify_vpp_api_key),
):
    # 1. API Key 认证
    if api_key is None:
        return {"code": 401, "message": "VPP 认证失败", "data": None}

    # 2. 部署阶段检查
    try:
        from ...services.precool.deployment_phase import deployment_phase_service
        phase_info = await deployment_phase_service.get_current_phase()
        if phase_info["current_phase"] != 4:
            return {"code": 403, "message": "VPP 接口仅在部署阶段 4 可用", "data": None}
    except Exception as e:
        logger.error(f"VPP 调控 - 部署阶段检查失败: {e}", exc_info=True)
        return {"code": 500, "message": f"部署阶段检查失败: {e}", "data": None}

    # 3. 速率限制
    rate_ok = await check_vpp_rate_limit()
    if not rate_ok:
        return {"code": 429, "message": "超出速率限制（每小时最多 12 条）", "data": None}

    # 4. 调用 dispatch 服务
    try:
        from ...services.precool.vpp_dispatch import vpp_dispatch_service
        result = await vpp_dispatch_service.validate_and_execute(request.model_dump())
        code = 200 if result["status"] == "accepted" else 200  # rejected 也是 200，通过 status 区分
        return {"code": code, "message": "success", "data": result}
    except Exception as e:
        logger.error(f"VPP 调控指令处理失败: {e}", exc_info=True)
        return {"code": 500, "message": f"VPP 调控指令处理失败: {e}", "data": None}
```

### Schema 追加（precool.py）

```python
from typing import Literal

class VppDispatchRequest(BaseModel):
    command_type: Literal["down_adjust", "up_adjust"]  # 调控方向
    target_power_kw: float  # 目标调控功率 (kW_e), 必须 > 0
    duration_minutes: int  # 持续时间（分钟），必须 > 0
    priority: int = 1  # 优先级（1=普通, 2=紧急）

class VppDispatchResponse(BaseModel):
    dispatch_id: str
    command_type: str
    target_power_kw: float
    duration_minutes: int
    status: str  # accepted / rejected
    reject_reason: Optional[str] = None
    max_adjustable_kw: Optional[float] = None
    accepted_power_kw: Optional[float] = None
    aborted_schedule_id: Optional[int] = None
```

### 关键约束

- **部署阶段门控:** phase != 4 → `{"code": 403, ...}`
- **独立认证:** X-VPP-API-Key header，不使用 JWT Depends(require_role)
- **dict 返回模式:** 与 precool.py 现有端点一致，不用 HTTPException
- **两层 try/except:** 部署阶段检查和服务调用分开
- **自管理 Session:** vpp_dispatch_service 使用自己的 async_session()
- **executor 单例名:** `precool_executor`（非 `precool_executor_service`），导入 `from .executor import precool_executor`
- **executor 调用:** 使用 `precool_executor.abort_plan_by_api(plan, reason, session)` 中止预冷计划
- **PrecoolSchedule 时间字段:** precool_start_time/precool_end_time 是 **Time 类型**（非 DateTime），查询时需 `now.date()` 比 schedule_date、`now.time()` 比 Time 字段
- **Redis 降级:** 速率限制 Redis 不可用时放行
- **command_type 枚举:** 仅 "down_adjust" 和 "up_adjust"
- **冲突检测范围:** 仅 down_adjust 需要检查（削减制冷与预冷冲突），up_adjust 不冲突
- **VppDispatch 表名:** vpp_dispatches（复数，符合项目约定）
- **Alembic 迁移:** 需要生成迁移脚本（`alembic revision --autogenerate`）

### Project Structure Notes

- **新建文件:** `backend/app/services/precool/vpp_dispatch.py` — VPP 调控指令处理服务
- **修改文件:** `backend/app/models/thermal.py` — 追加 VppDispatch 模型
- **修改文件:** `backend/app/models/__init__.py` — 注册 VppDispatch 导出
- **修改文件:** `backend/app/api/v1/precool.py` — 追加 POST /vpp/dispatch 端点
- **修改文件:** `backend/app/schemas/precool.py` — 追加 VPP dispatch 相关类型
- **修改文件:** `backend/app/core/config.py` — 追加 VPP_API_KEY 配置
- **新建文件:** `backend/tests/services/precool/test_vpp_dispatch.py` — 服务测试
- **新建文件:** `backend/tests/api/test_vpp_dispatch.py` — API 测试

### References

- [Source: _bmad-output/planning-artifacts/epics.md — Story 33.2]
- [Source: _bmad-output/planning-artifacts/architecture.md — Section 21.4.3 VPPCapacityReporter]
- [Source: _bmad-output/planning-artifacts/architecture.md — Section 21.5 API 设计: POST /vpp/dispatch]
- [Source: backend/app/services/precool/executor.py — abort_plan_by_api() 方法]
- [Source: backend/app/services/precool/vpp_capacity.py — calculate_capacity() 方法]
- [Source: backend/app/core/redis.py — Redis 缓存服务]
- [Source: backend/app/models/thermal.py — PrecoolSchedule 模型]
- [Source: _bmad-output/implementation-artifacts/stories/33-1-vpp-adjustable-capacity-reporting-interface.md — Story 33.1 实现]
