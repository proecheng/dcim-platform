# 模拟系统解耦重构代码审查报告

## 审查信息
- 审查对象：
  - `backend/app/services/ingest_pipeline.py`
  - `backend/app/demo/engine.py`
  - `backend/app/demo/service.py`
  - `backend/app/demo/lifecycle.py`
  - `backend/app/demo/seeds/*.py`
  - `backend/tests/demo/*.py`
- 审查维度：代码质量、性能、安全、可维护性、测试覆盖
- 审查结论：存在 **3 个 HIGH / 5 个 MEDIUM / 3 个 LOW** 问题，建议先修复 HIGH 再进入下一轮回归。

---

## HIGH

### H1. SQL 拼接存在注入风险（`status` 字段）
- **位置**：`backend/app/services/ingest_pipeline.py:226`, `backend/app/services/ingest_pipeline.py:229`, `backend/app/services/ingest_pipeline.py:236`
- **问题描述**：`_batch_upsert_realtime()` 通过 f-string 拼接 `status_cases` 与 `IN (...)` SQL。`status` 来自外部载荷，若包含引号或恶意片段，存在 SQL 注入与语句破坏风险。
- **影响**：安全风险高，且在异常输入下可能导致批量更新失败。
- **建议修复**：改为参数化更新（`bindparam`）或使用 SQLAlchemy Core 批量更新；至少对 `status` 做白名单（`normal/offline/alarm/...`）校验。
- **示例修复**：
```python
# 方案一：先白名单校验
ALLOWED_STATUS = {"normal", "offline", "alarm", "unknown"}
for pt in batch:
    if pt.status not in ALLOWED_STATUS:
        raise ValueError(f"非法状态值: {pt.status}")

# 方案二：改 executemany 参数化（示意）
await session.execute(
    update(PointRealtime)
    .where(PointRealtime.point_id == bindparam("point_id"))
    .values(
        value=bindparam("value"),
        raw_value=bindparam("value"),
        quality=bindparam("quality"),
        status=bindparam("status"),
        updated_at=bindparam("updated_at"),
    ),
    [
        {
            "point_id": pt.point_id,
            "value": pt.value,
            "quality": pt.quality,
            "status": pt.status,
            "updated_at": now,
        }
        for pt in batch
    ],
)
```

### H2. 配电回路引用了未创建的配电柜，可能写入无效拓扑或触发 FK 错误
- **位置**：
  - 引用端：`backend/app/demo/service.py:437`, `backend/app/demo/service.py:446`, `backend/app/demo/service.py:464`, `backend/app/demo/service.py:473`, `backend/app/demo/service.py:483`, `backend/app/demo/service.py:491`, `backend/app/demo/service.py:500`, `backend/app/demo/service.py:510`, `backend/app/demo/service.py:519`, `backend/app/demo/service.py:529`, `backend/app/demo/service.py:539`
  - 赋值端：`backend/app/demo/service.py:1443`, `backend/app/demo/service.py:1444`
- **问题描述**：`DISTRIBUTION_CIRCUITS` 中多个 `panel_code` 在 `DISTRIBUTION_PANELS` 未定义；创建回路时直接 `panel_map.get(panel_code)`，缺失时会得到 `None`。
- **影响**：
  - 若 `panel_id` 非空约束：加载流程直接失败。
  - 若可空：形成“悬空回路”，拓扑图、统计与联动规则出现错误结果。
- **建议修复**：创建前做一致性校验，发现缺失即 fail-fast；或先补全缺失 panel 定义。
- **示例修复**：
```python
panel_id = panel_map.get(panel_code)
if panel_id is None:
    raise ValueError(f"配电回路 {data['circuit_code']} 引用了不存在的 panel_code={panel_code}")
data["panel_id"] = panel_id
```

### H3. 卸载流程吞异常后继续提交，可能“假成功”
- **位置**：`backend/app/demo/service.py:1246`, `backend/app/demo/service.py:1263`, `backend/app/demo/service.py:1272`, `backend/app/demo/service.py:1280`, `backend/app/demo/service.py:1294`, `backend/app/demo/service.py:1302`, `backend/app/demo/service.py:1314`, `backend/app/demo/service.py:1332`, `backend/app/demo/service.py:1335`
- **问题描述**：`_clear_demo_data()` 多段 `except Exception: pass`，最终统一 `commit`；上层 `unload_demo_data()` 仍返回成功。
- **影响**：出现部分数据残留时很难被发现，后续 load/status/测试将随机失败，运维排障困难。
- **建议修复**：
  1) 仅对“可选模块不存在”做有界处理；
  2) 删除失败应记录并汇总，必要时 rollback 并返回失败；
  3) 返回 `warnings/errors` 明细。
- **示例修复**：
```python
errors = []
try:
    await session.execute(delete(LinkagePolicy))
except Exception as e:
    errors.append(f"清理 LinkagePolicy 失败: {e}")

if errors:
    await session.rollback()
    raise RuntimeError("; ".join(errors))
```

---

## MEDIUM

### M1. `run_collection_cycle()` 存在 N+1 查询（AO/DO 点位）
- **位置**：`backend/app/demo/engine.py:122`, `backend/app/demo/engine.py:131`
- **问题描述**：遍历点位时，对每个 AO/DO 再查一次 `PointRealtime`。
- **影响**：点位规模增大时采集周期耗时线性恶化，增加数据库压力。
- **建议修复**：一次性预取所需 realtime（`IN` 查询）后字典映射读取。
- **示例修复**：
```python
ao_do_ids = [p.id for p in points if p.point_type in {"AO", "DO"}]
rt_rows = await session.execute(select(PointRealtime).where(PointRealtime.point_id.in_(ao_do_ids)))
rt_map = {r.point_id: r for r in rt_rows.scalars().all()}
```

### M2. `PointDataLatest` upsert 为逐条 UPDATE，批量性能较差
- **位置**：`backend/app/services/ingest_pipeline.py:280`, `backend/app/services/ingest_pipeline.py:282`
- **问题描述**：已存在记录逐条执行 `update(...)`，批量载荷下 SQL 次数过多。
- **影响**：吞吐下降，事务时间变长。
- **建议修复**：使用数据库原生 upsert（如 PostgreSQL `ON CONFLICT`）或 executemany。

### M3. 历史入库未使用采集时间，回放/补数场景会丢时序精度
- **位置**：`backend/app/services/ingest_pipeline.py:315`
- **问题描述**：`PointHistory` 仅写 `point_id/value`，未显式写 `recorded_at=pt.timestamp`。
- **影响**：历史重放、离线补传时，时间轴可能被写成“当前时间”。
- **建议修复**：写入 `recorded_at=pt.timestamp or now`。
- **示例修复**：
```python
session.add(
    PointHistory(
        point_id=pt.point_id,
        value=pt.value,
        recorded_at=pt.timestamp or now,
    )
)
```

### M4. 种子点位 `area_code` 被硬编码为 `A1`，跨区域数据失真
- **位置**：`backend/app/demo/seeds/cooling_seed.py:358`, `backend/app/demo/seeds/power_seed.py:398`
- **问题描述**：`_create_point()` 固定 `area_code="A1"`，与设备真实区域（F1/F2/F3/B1）不一致。
- **影响**：区域统计、筛选、告警分区、拓扑关联会出现偏差。
- **建议修复**：从设备对象或调用参数传递真实 `area_code`。

### M5. `service.py` 存在未使用的旧匹配逻辑，增加维护成本
- **位置**：定义 `backend/app/demo/service.py:1525`，实际使用 `backend/app/demo/service.py:1464`
- **问题描述**：`_find_matching_points()` 仍保留，但已切换到 `PointDeviceMatcher.find_matching_points()`。
- **影响**：双实现易漂移，阅读者难判断真实生效路径。
- **建议修复**：删除死代码或改为统一委托，并补充迁移说明注释。

---

## LOW

### L1. 重复导入，代码整洁性问题
- **位置**：`backend/app/demo/engine.py:14`, `backend/app/demo/engine.py:22`
- **问题描述**：`capacity` 模型导入块重复一份。
- **建议修复**：删除重复导入，避免误导和 lint 噪音。

### L2. 生命周期启动间隔硬编码，配置一致性不足
- **位置**：`backend/app/demo/lifecycle.py:57`, `backend/app/demo/lifecycle.py:58`
- **问题描述**：`startup()` 固定 `interval=5`，与配置中心可能不一致。
- **建议修复**：读取 `settings.simulation_interval` 并统一来源。

### L3. 测试对关键分支覆盖不足（大量 mock 掉核心副作用）
- **位置**：
  - `backend/tests/demo/test_ingest_pipeline.py:35`, `backend/tests/demo/test_ingest_pipeline.py:36`, `backend/tests/demo/test_ingest_pipeline.py:37`
  - `backend/tests/demo/test_integration_flow.py:89`, `backend/tests/demo/test_integration_flow.py:90`, `backend/tests/demo/test_integration_flow.py:91`
- **问题描述**：告警评估、WS 广播、Redis 缓存在核心流程里被完全 stub，缺少真实分支验证。
- **建议修复**：新增“最小集成”测试覆盖：
  1) 告警触发/恢复路径；
  2) panel_code 不存在时 fail-fast；
  3) 恶意 `status` 输入防注入。

---

## 测试覆盖评估（针对本次重构）
- **已有优点**：
  - 覆盖了加载-生成-卸载主流程（`test_integration_flow.py`）。
  - 覆盖了批量入库边界（300 点）与空载荷场景（`test_ingest_pipeline.py`）。
- **主要缺口**：
  - 缺少安全测试（SQL 注入、非法状态值）。
  - 缺少配置一致性测试（回路引用缺失 panel）。
  - 缺少失败分支测试（卸载部分失败时应返回失败/告警）。

---

## 整体质量评分
- **综合评分：7.1 / 10**
- 评分拆分：
  - 代码质量：7.0
  - 性能：6.8
  - 安全：6.5
  - 可维护性：7.2
  - 测试覆盖：7.8

> 建议修复顺序：**H1 → H2 → H3 → M1/M2**，完成后执行一次端到端回归（load → collect cycle → unload）与性能复测。
