# Story 33.1: VPP 可调容量上报接口

Status: done

## Story

As a VPP 平台运营人员,
I want 数据中心每 5 分钟上报可调容量,
So that 我能将数据中心纳入虚拟电厂调度资源池。

## 依赖

- Story 29.2（RC 热模型核心算法）— done
- Story 32.2（部署阶段控制，VPP 在阶段 4）— done

## Acceptance Criteria

1. Given 部署阶段为 4（VPP 接入）
   When VPP 平台调用 `GET /api/v1/precool/vpp/capacity`
   Then 返回各区域聚合的分向可调容量：
   - down_adjustable_kw: 向下可调电功率（kW_e，削峰，减少制冷）
   - up_adjustable_kw: 向上可调电功率（kW_e，填谷，增加制冷）
   - down_adjustable_thermal_kw: 向下可调热功率（kW_th）
   - up_adjustable_thermal_kw: 向上可调热功率（kW_th）
   - T_current: 当前代表温度（各区域进风最高值）
   - headroom_up/headroom_down: 温度裕度
   - response_window_hours: 响应窗口（默认 1.0h）
   - zones: 各区域明细列表

2. Given 部署阶段不是 4
   When 调用容量查询接口
   Then 返回 code=403，message="VPP 接口仅在部署阶段 4 可用"

3. Given 容量计算逻辑
   When 计算向下可调容量（削峰）
   Then 温度裕度 ≤ 1°C 时返回 0
   And 否则 down_thermal = min(Q_current - Q_min, C × (headroom - 1.0) / response_window)
   And down_kw = down_thermal / COP

4. Given 容量计算逻辑
   When 计算向上可调容量（填谷）
   Then 温度裕度 ≤ 0.5°C 时返回 0
   And 否则 up_thermal = min(Q_max - Q_current, C × (headroom - 0.5) / response_window)
   And up_kw = up_thermal / COP

5. Given APScheduler 定时任务
   When 系统运行中
   Then 每 5 分钟自动计算并缓存各区域容量到 Redis（key=vpp:capacity，TTL=10min）
   And GET 接口优先返回缓存数据，缓存未命中时实时计算

6. Given 所有新增代码
   When 运行测试
   Then 单元测试全部通过，无 TypeScript/Python 错误

## Tasks / Subtasks

- [x] Task 1: VPP 容量计算服务 (AC: #1, #3, #4)
  - [x] 1.1 新建 `backend/app/services/precool/vpp_capacity.py`
  - [x] 1.2 实现 VppCapacityService 类，包含容量计算核心逻辑
  - [x] 1.3 实现各区域容量聚合（遍历所有 CoolingZone，跳过 thermal_R/C 为 None 的区域）
  - [x] 1.4 实现温度/功率/COP 数据获取（复用 scheduler.py 查询模式）

- [x] Task 2: Redis 缓存与定时任务 (AC: #5)
  - [x] 2.1 实现 Redis 缓存读写（key=vpp:capacity，TTL=10min）
  - [x] 2.2 在 main.py 注册 APScheduler 5 分钟定时任务
  - [x] 2.3 Redis 不可用时降级为实时计算

- [x] Task 3: API 端点与 Schema (AC: #1, #2)
  - [x] 3.1 在 precool.py 追加 `GET /vpp/capacity` 端点
  - [x] 3.2 在 precool.py Schema 中追加 VPP 相关类型
  - [x] 3.3 部署阶段检查（phase != 4 → 403）

- [x] Task 4: 单元测试 (AC: #6)
  - [x] 4.1 新建 `backend/tests/services/precool/test_vpp_capacity.py`
  - [x] 4.2 新建 `backend/tests/api/test_vpp_capacity.py`

## Dev Notes

### VPP 容量计算服务设计

新建 `backend/app/services/precool/vpp_capacity.py`，实现 `VppCapacityService` 类。

**核心计算逻辑：**

```python
class VppCapacityService:
    DEFAULT_RESPONSE_WINDOW = 1.0  # 小时
    HEADROOM_DOWN_THRESHOLD = 1.0  # °C，向下可调最小裕度
    HEADROOM_UP_THRESHOLD = 0.5    # °C，向上可调最小裕度

    async def calculate_capacity(self) -> dict:
        """计算所有区域的聚合可调容量"""
        # 1. 遍历所有 CoolingZone（CoolingZone 无 is_demo 字段，通过 thermal_R/C 是否为 None 过滤未标定区域）
        # 2. 每个区域计算: T_current, headroom, Q_cool_est, Q_min, Q_max, COP, R, C
        # 3. 计算分向可调容量
        # 4. 聚合所有区域结果

    async def _calculate_zone_capacity(self, zone, session) -> dict:
        """单区域容量计算"""
        # 获取当前温度（进风最高值）— 使用 PointRealtime（最新值，适合实时容量上报）
        # 导入路径: from app.models.topology_config import CabinetTemperatureSensor, CoolingZoneCabinet
        # 获取 COP — 季节修正（复用 thermal_model._get_seasonal_cop 逻辑）
        # 获取 R, C — 从 zone.thermal_R, zone.thermal_C
        # 获取 Q_total — sum(CoolingUnit.cooling_capacity_kw)
        # Q_cool_est = Q_total * 0.7  # 稳态近似：制冷功率 ≈ IT 热负荷（70% 负载率）
        # Q_max = Q_total
        # Q_min = Q_total * 0.3  # 最低保留 30% 制冷（安全下限，不能完全关闭）

        # 计算向下裕度（减少制冷→温度上升→需要到 TEMP_MAX 的空间）
        headroom_down = TEMP_MAX - T_current  # 温度上升空间
        if headroom_down <= HEADROOM_DOWN_THRESHOLD:
            down_thermal = 0
        else:
            down_thermal = min(Q_cool_est - Q_min, C * (headroom_down - 1.0) / response_window)
            down_thermal = max(0, down_thermal)

        # 计算向上裕度（增加制冷→温度下降→需要到 TEMP_MIN 的空间）
        headroom_up = T_current - TEMP_MIN  # 温度下降空间
        if headroom_up <= HEADROOM_UP_THRESHOLD:
            up_thermal = 0
        else:
            up_thermal = min(Q_max - Q_cool_est, C * (headroom_up - 0.5) / response_window)
            up_thermal = max(0, up_thermal)

        # 转换为电功率（热功率 / COP = 电功率）
        down_kw = down_thermal / COP
        up_kw = up_thermal / COP
```

**⚠️ 关键理解：headroom 方向**
- `headroom_down`（向下可调=削峰=减少制冷=温度会上升）：需要**温度上升空间** = `TEMP_MAX - T_current`
- `headroom_up`（向上可调=填谷=增加制冷=温度会下降）：需要**温度下降空间** = `T_current - TEMP_MIN`
- 两个方向的裕度阈值不同：向下 1.0°C（更保守），向上 0.5°C

### 数据获取方式

**当前温度（T_current）— 复用 scheduler.py 查询模式：**
```python
# CoolingZoneCabinet → CabinetTemperatureSensor(sensor_location='inlet') → Point → PointRealtime
select(func.max(PointRealtime.value))
.join(Point, PointRealtime.point_id == Point.id)
.join(CabinetTemperatureSensor, CabinetTemperatureSensor.point_id == Point.id)
.join(CoolingZoneCabinet, CoolingZoneCabinet.cabinet_id == CabinetTemperatureSensor.cabinet_id)
.where(CoolingZoneCabinet.zone_id == zone_id, CabinetTemperatureSensor.sensor_location == 'inlet')
```

**制冷功率估算（Q_cool_est）— 稳态近似：**
```python
# 从 CoolingUnit 额定容量 × 负载率估算（与 scheduler.py _get_it_load 一致）
# 稳态假设: Q_cool ≈ Q_IT（制冷输出 ≈ IT 热负荷），误差在预冷/削峰期间较大
Q_total = sum(CoolingUnit.cooling_capacity_kw)  # 通过 CoolingZoneUnit 关联查询
Q_cool_est = Q_total * 0.7  # 70% 负载率估算，稳态下近似当前制冷功率
Q_max = Q_total
Q_min = Q_total * 0.3  # 安全下限: 保留 30% 制冷，不能完全关闭
# 注意：Q_min 不能为 0，数据中心有 IT 设备运行时必须保留最低制冷
```

**COP — 复用季节修正逻辑：**
```python
# 从环境温度获取季节 COP
# T_outdoor >= 30 → 2.8; 15-30 → 3.5; < 15 → 4.0
# 查询路径: CoolingZoneUnit → CoolingUnit → Device → Point(point_code like '%_ambient_temp')
```

**R, C 参数 — 直接从 CoolingZone 读取：**
```python
zone.thermal_R  # 如果为 None/0 则跳过该区域
zone.thermal_C
```

### Redis 缓存策略

使用项目现有的 `app.core.redis.RedisService`：
```python
from app.core.redis import redis_service

# 写入缓存
await redis_service.set_json("vpp:capacity", result, ttl=600)  # TTL=10min

# 读取缓存（返回 dict 或 None）
cached = await redis_service.get_json("vpp:capacity")
if cached:
    return cached
```

Redis 不可用时（`_enabled=False`），set/get 静默返回 None，降级为每次实时计算。

### APScheduler 定时任务

在 `main.py` 追加 VPP 容量刷新任务：
```python
from app.services.precool.vpp_capacity import vpp_capacity_service

async def _refresh_vpp_capacity():
    try:
        await vpp_capacity_service.refresh_capacity_cache()
    except Exception as e:
        logger.error(f"VPP 容量刷新失败: {e}", exc_info=True)

scheduler.add_job(
    _refresh_vpp_capacity,
    'interval', minutes=5,
    id='vpp_capacity_refresh',
    max_instances=1,
    replace_existing=True,
    name='VPP可调容量刷新',
)
```

### API 端点设计

在 `precool.py` 追加：
```python
@router.get("/vpp/capacity", summary="查询 VPP 可调容量")
async def get_vpp_capacity(
    _=Depends(require_role(["admin", "operator", "viewer"]))
):
    try:
        # 1. 检查部署阶段（使用 dict 返回与 precool.py 现有模式一致）
        phase_info = await deployment_phase_service.get_current_phase()
        if phase_info["current_phase"] != 4:
            return {"code": 403, "message": "VPP 接口仅在部署阶段 4 可用", "data": None}
        # 2. 尝试读取 Redis 缓存
        # 3. 缓存未命中则实时计算
        # 4. 返回统一格式 {"code": 200, "message": "ok", "data": VppCapacityResponse}
    except Exception as e:
        logger.error(f"VPP 容量查询失败: {e}", exc_info=True)
        return {"code": 500, "message": f"VPP 容量查询失败: {e}", "data": None}
```

### Schema 追加（precool.py）

```python
class VppZoneCapacity(BaseModel):
    zone_id: int
    zone_name: str
    T_current: float | None
    headroom_down: float  # TEMP_MAX - T_current（温度上升空间，用于向下可调）
    headroom_up: float    # T_current - TEMP_MIN（温度下降空间，用于向上可调）
    down_adjustable_thermal_kw: float
    up_adjustable_thermal_kw: float
    down_adjustable_kw: float
    up_adjustable_kw: float
    cop: float
    model_config = ConfigDict(from_attributes=True)

class VppCapacityResponse(BaseModel):
    down_adjustable_kw: float       # 聚合向下可调电功率
    up_adjustable_kw: float         # 聚合向上可调电功率
    down_adjustable_thermal_kw: float
    up_adjustable_thermal_kw: float
    T_current: float | None         # 代表温度（所有区域最高）
    headroom_down: float            # 各区域最小向下裕度（TEMP_MAX - T_current）
    headroom_up: float              # 各区域最小向上裕度（T_current - TEMP_MIN）
    response_window_hours: float
    zones: list[VppZoneCapacity]
    cached_at: str | None           # 缓存时间（None=实时计算）
```

### 基线功率简化说明

Epic AC 要求基线功率使用"近 10 个同类型工作日平均制冷功率"。本 Story 中简化为：
- 当前制冷功率直接从 CoolingUnit 额定容量 × 0.7 估算（与 scheduler.py 一致）
- 基线功率的完整实现（工作日筛选、极端天气排除、IT 负载异常排除）推迟到 Story 33.2 或独立技术债务 Story
- 原因：基线功率主要用于 VPP 上报格式中的"调控前基准"，容量计算本身不依赖基线

### Project Structure Notes

- **新建文件:** `backend/app/services/precool/vpp_capacity.py` — VPP 容量计算服务
- **修改文件:** `backend/app/api/v1/precool.py` — 追加 GET /vpp/capacity 端点
- **修改文件:** `backend/app/schemas/precool.py` — 追加 VPP Schema
- **修改文件:** `backend/app/main.py` — 追加 APScheduler 定时任务
- **新建文件:** `backend/tests/services/precool/test_vpp_capacity.py` — 服务测试
- **新建文件:** `backend/tests/api/test_vpp_capacity.py` — API 测试

### 关键约束

- **部署阶段门控:** phase != 4 → `{"code": 403, "message": "...", "data": None}`（使用 dict 返回与 precool.py 现有模式一致，不用 HTTPException）
- **异常保护:** deployment_phase_service 和 vpp_capacity_service 调用均需 try/except 包裹（与现有 GET/PUT deployment-phase 端点模式一致）
- **T_current 为 None 处理:** 温度传感器离线时跳过该区域，不计入聚合结果（与 thermal_R/C IS NULL 同逻辑）
- **COP 安全:** COP 取值必须 > 0，为 0 时使用 fallback 3.5
- **自管理 Session 模式:** vpp_capacity_service 使用自己的 async_session()（定时任务调用）
- **Redis 优雅降级:** Redis 不可用时每次实时计算（性能可接受，区域数通常 < 10）
- **Redis API:** 使用 `redis_service.set_json(key, data, ttl=N)` / `redis_service.get_json(key)`，参数名是 `ttl`（不是 `ex`）
- **无外部推送:** 本 Story 不实现向外部 VPP 平台推送数据，仅提供查询接口 + 缓存刷新
- **COP 一致性:** 使用与 scheduler.py/thermal_model.py 相同的季节修正逻辑
- **CoolingZone 过滤:** CoolingZone 模型没有 `is_demo` 字段，通过 `thermal_R IS NOT NULL AND thermal_C IS NOT NULL` 筛选已标定区域
- **导入路径:** `CabinetTemperatureSensor` 在 `app.models.topology_config` 中（不是 `app.models.cabinet`）
- **Q_min 安全下限:** Q_min = Q_total × 0.3（保留 30% 制冷），不能为 0
- **response_window_hours:** 当前硬编码 1.0h，未来可从 SystemConfig 读取或接受 query parameter 覆盖
- **温度数据源:** 使用 `PointRealtime`（实时值），与 scheduler.py 一致（constraints.py 用 PointHistory 是不同场景）
- **T_current 聚合:** 聚合层 T_current = 所有区域 T_current 中的最大值

### References

- [Source: _bmad-output/planning-artifacts/epics.md — Story 33.1]
- [Source: _bmad-output/planning-artifacts/architecture.md — Section 21.6 VPP 对外接口]
- [Source: backend/app/services/precool/scheduler.py — 温度/功率查询模式]
- [Source: backend/app/services/precool/constraints.py — ASHRAE 温度常量]
- [Source: backend/app/core/redis.py — Redis 缓存服务]
- [Source: backend/app/main.py — APScheduler 任务注册模式]
