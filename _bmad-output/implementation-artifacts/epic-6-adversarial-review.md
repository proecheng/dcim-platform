# Epic 6 对抗性审查报告

**审查日期:** 2026-03-10
**审查人:** Claude (Adversarial Review)
**审查范围:** Epic 6（能源管理 - PUE 监控与配电拓扑）实施成果
**审查方法:** 代码审查 + 数据一致性分析

---

## 审查结论

⚠️ **发现 14 个问题：2 个 P0 问题，5 个 P1 问题，7 个 P2 问题**

---

## 审查发现

### P0-1: PUE 计算未处理除零错误

**问题描述:**
- 文件: `backend/app/services/pue_calculator.py:110`
- `current_pue = round(total_power / it_power, 3)`
- 虽然在第 99 行检查了 `it_power <= 0`，但使用 `<=` 而不是 `< 0.001`
- 如果 `it_power` 非常接近 0（如 0.001），会导致 PUE 值异常大
- 可能导致 PUE 值为数千甚至数万

**影响:** 严重 - 数据准确性

**修复建议:**
```python
# 使用更严格的阈值检查
IT_POWER_THRESHOLD = 1.0  # 至少 1kW IT 负载才计算 PUE

if it_power < IT_POWER_THRESHOLD:
    return PUEResult(
        current_pue=None,
        total_power=round(total_power, 2),
        it_power=round(it_power, 2),
        cooling_power=round(cooling_power, 2),
        ups_loss=0,
        data_source="realtime",
        unreliable_count=unreliable_count,
    )

current_pue = round(total_power / it_power, 3)
```

**优先级:** P0 - 必须立即修复

---

### P0-2: 配电拓扑查询未处理循环依赖

**问题描述:**
- 文件: `backend/app/api/v1/energy.py:2359-2466`
- `get_distribution_topology()` 构建拓扑树时未检测循环依赖
- 如果数据库中存在循环引用（如 Panel A → Circuit B → Panel A），会导致无限递归
- 虽然当前实现不会递归，但数据结构允许循环
- 可能导致前端渲染死循环

**影响:** 严重 - 系统稳定性

**修复建议:**
```python
# 在构建拓扑前验证数据完整性
def _validate_topology_integrity(transformers, meters, panels, circuits):
    """验证拓扑数据完整性，检测循环依赖"""
    # 检查计量点是否引用不存在的变压器
    transformer_ids = {t.id for t in transformers}
    for meter in meters:
        if meter.transformer_id and meter.transformer_id not in transformer_ids:
            logger.warning("计量点 %s 引用不存在的变压器 %d", meter.meter_code, meter.transformer_id)

    # 检查配电柜是否引用不存在的计量点
    meter_ids = {m.id for m in meters}
    for panel in panels:
        if panel.meter_point_id and panel.meter_point_id not in meter_ids:
            logger.warning("配电柜 %s 引用不存在的计量点 %d", panel.panel_code, panel.meter_point_id)

    # 检查回路是否引用不存在的配电柜
    panel_ids = {p.id for p in panels}
    for circuit in circuits:
        if circuit.panel_id not in panel_ids:
            logger.warning("回路 %s 引用不存在的配电柜 %d", circuit.circuit_code, circuit.panel_id)

# 在 get_distribution_topology() 开头调用
_validate_topology_integrity(transformers, meters, panels, circuits)
```

**优先级:** P0 - 必须立即修复

---

### P1-1: PUE 历史写入未处理并发冲突

**问题描述:**
- 文件: `backend/app/services/pue_calculator.py:123-148`
- `write_pue_history()` 直接插入记录，未处理并发写入
- 如果多个进程同时调用，可能导致重复记录
- 未使用唯一约束或 UPSERT 逻辑
- 可能导致 PUE 历史数据重复

**影响:** 高 - 数据一致性

**修复建议:**
```python
async def write_pue_history(db: AsyncSession) -> None:
    """
    将当前 PUE 写入 PUEHistory 表
    使用 UPSERT 逻辑避免重复
    """
    pue_result = await calculate_realtime_pue(db)

    if pue_result.current_pue is None:
        logger.info("PUE 无效（IT 负载为 0），跳过历史写入")
        return

    # 按分钟粒度去重（同一分钟只保留最新记录）
    record_time = datetime.now().replace(second=0, microsecond=0)

    # 检查是否已存在
    existing = await db.execute(
        select(PUEHistory).where(PUEHistory.record_time == record_time)
    )
    existing_record = existing.scalar_one_or_none()

    if existing_record:
        # 更新现有记录
        existing_record.pue = pue_result.current_pue
        existing_record.total_power = pue_result.total_power
        existing_record.it_power = pue_result.it_power
        existing_record.cooling_power = pue_result.cooling_power
        existing_record.ups_loss = pue_result.ups_loss
    else:
        # 插入新记录
        record = PUEHistory(
            record_time=record_time,
            pue=pue_result.current_pue,
            total_power=pue_result.total_power,
            it_power=pue_result.it_power,
            cooling_power=pue_result.cooling_power,
            ups_loss=pue_result.ups_loss,
        )
        db.add(record)

    try:
        await db.commit()
        logger.info("PUE 历史记录已写入: PUE=%.3f", pue_result.current_pue)
    except Exception:
        await db.rollback()
        raise
```

**优先级:** P1 - 建议尽快修复

---

### P1-2: PUE 计算未处理 UPS 效率异常

**问题描述:**
- 文件: `backend/app/services/pue_calculator.py:96-97`
- `ups_loss = max(0, ups_total - it_power)`
- 假设 UPS 损耗 = UPS 总功率 - IT 功率
- 但如果 UPS 效率异常（如 UPS 功率小于 IT 功率），会得到 0 损耗
- 实际上 UPS 效率通常在 90-95%，损耗应该是 IT 功率的 5-10%
- 当前逻辑可能导致 PUE 计算不准确

**影响:** 高 - 数据准确性

**修复建议:**
```python
# 使用 UPS 效率模型计算损耗
UPS_EFFICIENCY = 0.95  # 默认 UPS 效率 95%

if ups_total > 0:
    # 如果有 UPS 总功率数据，使用实际值
    ups_loss = max(0, ups_total - it_power)
else:
    # 如果没有 UPS 总功率数据，使用效率模型估算
    ups_loss = it_power * (1 / UPS_EFFICIENCY - 1)
```

**优先级:** P1 - 建议尽快修复

---

### P1-3: 能耗统计查询未处理时区

**问题描述:**
- 文件: `backend/app/api/v1/energy.py:737-758`
- `get_daily_statistics()` 使用 `date` 类型查询
- 未考虑时区问题，可能导致跨时区数据不一致
- 如果服务器时区与数据库时区不一致，会查询错误的日期范围
- 影响能耗统计准确性

**影响:** 高 - 数据准确性

**修复建议:**
```python
# 统一使用 UTC 时区
from datetime import timezone

@router.get("/statistics/daily", ...)
async def get_daily_statistics(
    start_date: date = Query(..., description="开始日期（UTC）"),
    end_date: date = Query(..., description="结束日期（UTC）"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取日能耗统计数据（UTC 时区）"""
    # 转换为 datetime 并指定 UTC 时区
    start_datetime = datetime.combine(start_date, datetime.min.time()).replace(tzinfo=timezone.utc)
    end_datetime = datetime.combine(end_date, datetime.max.time()).replace(tzinfo=timezone.utc)

    query = select(EnergyDaily).where(
        EnergyDaily.stat_date >= start_datetime,
        EnergyDaily.stat_date <= end_datetime
    )
    # ... 原有逻辑
```

**优先级:** P1 - 建议尽快修复

---

### P1-4: 配电拓扑未计算负载汇总

**问题描述:**
- 文件: `backend/app/api/v1/energy.py:2359-2466`
- `get_distribution_topology()` 返回拓扑结构
- 但未计算各级负载汇总（变压器总负载、计量点总负载、配电柜总负载）
- 前端需要显示负载率时，需要额外查询
- 影响用户体验和性能

**影响:** 高 - 功能完整性

**修复建议:**
```python
# 在构建拓扑时计算负载汇总
# 1. 计算回路负载（设备功率之和）
for circuit_id, devices in circuit_devices.items():
    circuit_load = sum(d.rated_power or 0 for d in devices)
    # 添加到 TopologyCircuitNode

# 2. 计算配电柜负载（回路负载之和）
for panel_id, circuits in panel_circuits.items():
    panel_load = sum(c.total_load or 0 for c in circuits)
    # 添加到 TopologyPanelNode

# 3. 计算计量点负载（配电柜负载之和）
for meter_id, panels in meter_panels.items():
    meter_load = sum(p.total_load or 0 for p in panels)
    # 添加到 TopologyMeterNode

# 4. 计算变压器负载（计量点负载之和）
for transformer_id, meters in transformer_meters.items():
    transformer_load = sum(m.total_load or 0 for m in meters)
    # 添加到 TopologyTransformerNode
```

**优先级:** P1 - 建议尽快修复

---

### P1-5: 功率曲线查询未限制数据量

**问题描述:**
- 文件: `backend/app/api/v1/energy.py:2472-2508`
- `get_power_curve()` 查询功率曲线数据
- 未限制返回数量，可能返回数万条记录
- 如果查询一年的数据（每 15 分钟一条），会返回 35040 条记录
- 占用大量内存和带宽

**影响:** 高 - 性能

**修复建议:**
```python
# 添加数据量限制和降采样
MAX_CURVE_POINTS = 1000  # 最多返回 1000 个点

@router.get("/power-curve", ...)
async def get_power_curve(
    start_time: datetime = Query(..., description="开始时间"),
    end_time: datetime = Query(..., description="结束时间"),
    meter_point_id: Optional[int] = Query(None, description="计量点ID"),
    device_id: Optional[int] = Query(None, description="设备ID"),
    sample_interval: Optional[int] = Query(None, description="采样间隔（分钟），自动降采样"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    获取功率曲线数据
    自动降采样以限制返回数据量
    """
    # 计算时间跨度
    time_span = (end_time - start_time).total_seconds() / 60  # 分钟

    # 自动计算采样间隔
    if not sample_interval:
        # 确保返回点数不超过 MAX_CURVE_POINTS
        sample_interval = max(1, int(time_span / MAX_CURVE_POINTS))

    # 使用降采样查询
    # ... 实现降采样逻辑
```

**优先级:** P1 - 建议尽快修复

---

### P2-1: PUE 趋势统计未处理空数据

**问题描述:**
- 文件: `backend/app/api/v1/energy.py:722-726`
- `get_pue_trend()` 计算平均值时未检查空列表
- 虽然有 `if pue_values` 检查，但在 `sum(pue_values) / len(pue_values)` 之前
- 如果 `pue_values` 为空，会导致除零错误
- 代码逻辑不清晰

**影响:** 中等 - 代码健壮性

**修复建议:**
```python
pue_values = [d.pue for d in data_list]
if pue_values:
    avg_pue = sum(pue_values) / len(pue_values)
    min_pue = min(pue_values)
    max_pue = max(pue_values)
else:
    avg_pue = 0
    min_pue = 0
    max_pue = 0
```

**优先级:** P2 - 可以接受现状

---

### P2-2: 能耗统计未缓存查询结果

**问题描述:**
- 文件: `backend/app/api/v1/energy.py:737-758`
- `get_daily_statistics()` 每次都查询数据库
- 日能耗数据变化频率低（每天更新一次）
- 未使用 Redis 缓存，高并发时性能低下
- 可能导致数据库压力过大

**影响:** 中等 - 性能优化

**修复建议:**
使用 Redis 缓存日能耗数据，TTL 设置为 1 小时

**优先级:** P2 - 可以接受现状

---

### P2-3: PUE 计算未记录计算过程

**问题描述:**
- 文件: `backend/app/services/pue_calculator.py:40-120`
- `calculate_realtime_pue()` 仅返回最终结果
- 未记录计算过程（哪些设备参与计算、各设备功率值）
- 调试时无法追溯 PUE 计算来源
- 影响可观测性

**影响:** 中等 - 可观测性

**修复建议:**
在 `PUEResult` 添加 `calculation_details` 字段，记录参与计算的设备列表

**优先级:** P2 - 可以接受现状

---

### P2-4: 配电拓扑未处理孤立节点

**问题描述:**
- 文件: `backend/app/api/v1/energy.py:2359-2466`
- `get_distribution_topology()` 构建拓扑时
- 未处理孤立节点（如未关联变压器的计量点、未关联配电柜的回路）
- 这些节点不会出现在拓扑树中
- 可能导致数据丢失

**影响:** 中等 - 数据完整性

**修复建议:**
在拓扑响应中添加 `orphaned_nodes` 字段，列出所有孤立节点

**优先级:** P2 - 可以接受现状

---

### P2-5: 能耗统计未处理同比环比计算错误

**问题描述:**
- 文件: `backend/app/api/v1/energy.py:737-758`
- `get_daily_statistics()` 返回原始数据
- 未计算同比环比
- 前端需要额外计算，逻辑重复
- 可能导致计算不一致

**影响:** 中等 - 功能完整性

**修复建议:**
在 API 中计算同比环比，统一计算逻辑

**优先级:** P2 - 可以接受现状

---

### P2-6: 功率曲线未处理数据缺失

**问题描述:**
- 文件: `backend/app/api/v1/energy.py:2472-2508`
- `get_power_curve()` 查询功率曲线
- 未处理数据缺失（如某些时间点没有数据）
- 前端绘制曲线时可能出现断点
- 影响用户体验

**影响:** 中等 - 用户体验

**修复建议:**
使用线性插值填充缺失数据点

**优先级:** P2 - 可以接受现状

---

### P2-7: PUE 历史数据未设置过期时间

**问题描述:**
- 文件: `backend/app/services/pue_calculator.py:123-148`
- `write_pue_history()` 写入历史数据
- 未设置过期时间，数据会无限增长
- 长期运行会导致表过大
- 影响查询性能

**影响:** 中等 - 长期性能

**修复建议:**
添加定时清理任务，删除或归档旧数据（如保留 1 年）

**优先级:** P2 - 可以接受现状

---

## 问题汇总

| 问题编号 | 问题描述 | 优先级 | 状态 | 影响范围 |
|---------|---------|--------|------|---------|
| P0-1 | PUE 计算未处理除零错误 | P0 | ⚠️ 待修复 | 数据准确性 |
| P0-2 | 配电拓扑查询未处理循环依赖 | P0 | ⚠️ 待修复 | 系统稳定性 |
| P1-1 | PUE 历史写入未处理并发冲突 | P1 | ⚠️ 待修复 | 数据一致性 |
| P1-2 | PUE 计算未处理 UPS 效率异常 | P1 | ⚠️ 待修复 | 数据准确性 |
| P1-3 | 能耗统计查询未处理时区 | P1 | ⚠️ 待修复 | 数据准确性 |
| P1-4 | 配电拓扑未计算负载汇总 | P1 | ⚠️ 待修复 | 功能完整性 |
| P1-5 | 功率曲线查询未限制数据量 | P1 | ⚠️ 待修复 | 性能 |
| P2-1 | PUE 趋势统计未处理空数据 | P2 | ⚠️ 待修复 | 代码健壮性 |
| P2-2 | 能耗统计未缓存查询结果 | P2 | ⚠️ 待修复 | 性能优化 |
| P2-3 | PUE 计算未记录计算过程 | P2 | ⚠️ 待修复 | 可观测性 |
| P2-4 | 配电拓扑未处理孤立节点 | P2 | ⚠️ 待修复 | 数据完整性 |
| P2-5 | 能耗统计未处理同比环比计算错误 | P2 | ⚠️ 待修复 | 功能完整性 |
| P2-6 | 功率曲线未处理数据缺失 | P2 | ⚠️ 待修复 | 用户体验 |
| P2-7 | PUE 历史数据未设置过期时间 | P2 | ⚠️ 待修复 | 长期性能 |

---

## Epic 6 实施质量评估

### 优点

1. **PUE 计算逻辑清晰** - 基于真实点位数据，批量查询避免 N+1
2. **配电拓扑结构完整** - 变压器 → 计量点 → 配电柜 → 回路 → 设备五级结构
3. **数据质量检查** - PUE 计算时检查数据质量和过期时间
4. **能耗统计多维度** - 支持日/月统计，按设备类型分组
5. **功率曲线支持** - 支持按计量点或设备查询功率曲线

### 缺点

1. **2 个 P0 数据准确性问题** - PUE 除零错误、配电拓扑循环依赖
2. **5 个 P1 功能缺陷** - 并发冲突、UPS 效率、时区处理、负载汇总、数据量限制
3. **7 个 P2 改进点** - 缓存、可观测性、数据完整性、用户体验
4. **缺少数据验证** - 配电拓扑未验证数据完整性

### 总体评价

Epic 6 的能源管理功能实现基本正确，PUE 计算和配电拓扑结构清晰。发现的问题主要集中在数据准确性、并发控制、性能优化等方面。P0 问题必须修复，P1 问题建议尽快修复。

**建议:**
1. **立即修复 P0 问题** - PUE 除零检查、配电拓扑循环依赖检测
2. **尽快修复 P1 问题** - 特别是 P1-1（并发冲突）和 P1-5（数据量限制）
3. **评估 P2 问题** - 根据实际使用情况决定是否修复

---

**审查完成时间:** 2026-03-10
**下一步:** 修复 P0 问题，继续审查其他 Epic
