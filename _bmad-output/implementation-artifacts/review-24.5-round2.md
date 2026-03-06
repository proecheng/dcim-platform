# Story 24.5 对抗性审查报告 - 第二轮

**审查日期**: 2026-03-06
**审查人**: Claude (对抗性审查模式 - 第二轮)
**Story**: 24.5 L2 故障树推理引擎（修订版）

---

## 审查发现问题

### P0 - 严重问题（必须修复）

#### P0-1: 故障树边方向与数据库表结构不一致
**问题**: Story 修改后使用 child → parent 边方向，但 `fault_tree_edge` 表的字段是 `parent_node_id` 和 `child_node_id`，这意味着数据库存储的是 parent → child 关系。加载时需要反转边方向，但代码中没有说明。

**影响**: 从数据库加载故障树时边方向错误，导致推理失败。

**修复建议**: 在 `load_fault_tree_to_networkx()` 方法中明确边方向转换逻辑：

```python
async def load_fault_tree_to_networkx(tree_id: int) -> nx.DiGraph:
    """从数据库加载故障树并构建 NetworkX 图"""
    graph = nx.DiGraph()

    # 加载节点
    nodes = await session.execute(
        select(FaultTreeNode).where(FaultTreeNode.tree_id == tree_id)
    )
    for node in nodes.scalars():
        graph.add_node(node.id, **node_attributes)

    # 加载边（数据库存储 parent → child，需反转为 child → parent）
    edges = await session.execute(
        select(FaultTreeEdge).where(FaultTreeEdge.tree_id == tree_id)
    )
    for edge in edges.scalars():
        # 反转边方向: child → parent
        graph.add_edge(edge.child_node_id, edge.parent_node_id)

    return graph
```

---

### P1 - 重要问题（强烈建议修复）

#### P1-1: 证据收集并发策略中的任务引用错误
**问题**: `collect_evidence()` 方法中，`asyncio.TimeoutError` 异常处理块尝试访问 `task.result()`，但 `tasks` 是协程列表，不是 Task 对象列表。

**影响**: 超时时会抛出 `AttributeError: 'coroutine' object has no attribute 'result'`。

**修复建议**: 使用 `asyncio.create_task()` 创建 Task 对象，或者简化超时处理：

```python
async def collect_evidence(self, leaf_nodes: List[str]) -> Dict[str, EvidenceItem]:
    """并发收集所有叶节点证据"""
    tasks = [self._query_single_evidence(node) for node in leaf_nodes]
    try:
        results = await asyncio.wait_for(
            asyncio.gather(*tasks, return_exceptions=True),
            timeout=3.0
        )
    except asyncio.TimeoutError:
        # 整体超时，所有证据标记为不可用
        logger.warning(f"证据收集整体超时（3秒），{len(leaf_nodes)} 个证据全部标记为不可用")
        results = [None] * len(leaf_nodes)

    evidence = {}
    for node, result in zip(leaf_nodes, results):
        if isinstance(result, Exception) or result is None:
            evidence[node] = EvidenceItem(status='unavailable')
        else:
            evidence[node] = result
    return evidence
```

---

#### P1-2: 时间窗口聚合策略缺少点位类型映射
**问题**: Dev Notes 第 8 节定义了聚合策略表，但没有说明如何从点位数据中获取点位类型（温度/电压/开关量等）。

**影响**: 实现时需要猜测点位类型的来源（从 `DataSourcePoint` 表？从点位名称？）。

**修复建议**: 在 `DataSourcePoint` 表中添加 `point_category` 字段（或使用现有的 `point_type` 字段），并在 Dev Notes 中说明：

```python
# DataSourcePoint 表已有 point_type 字段（AI/DI/AO/DO）
# 需要扩展为更细粒度的分类，或者在 fault_tree_node 表中存储聚合策略

async def query_historical_data(
    point_id: int,
    time_window_seconds: int
) -> float:
    """查询历史数据并聚合"""
    # 从点位配置中获取聚合策略
    point = await session.get(DataSourcePoint, point_id)
    aggregation = point.aggregation_strategy or 'avg'  # 默认平均值

    # 或者根据 point_type 推断
    if point.point_type == 'DI':
        aggregation = 'any'
    elif point.name.lower().startswith('voltage') or point.name.lower().startswith('current'):
        aggregation = 'max'
    else:
        aggregation = 'avg'

    # 执行查询...
```

---

#### P1-3: 故障树验证逻辑中的入度/出度判断错误
**问题**: `validate_fault_tree()` 中，注释说"入度为 0"是根节点，但如果边是 child → parent，根节点应该是"出度为 0"（没有父节点）。

**影响**: 验证逻辑错误，无法正确识别根节点和叶节点。

**修复建议**: 修正入度/出度判断：

```python
def validate_fault_tree(graph: nx.DiGraph) -> List[str]:
    """验证故障树完整性，返回错误列表"""
    errors = []

    # 检查是否有环
    if not nx.is_directed_acyclic_graph(graph):
        errors.append("故障树包含环")

    # 检查根节点数量（出度为 0，因为边是 child → parent，根节点没有父节点）
    root_nodes = [n for n in graph.nodes() if graph.out_degree(n) == 0]
    if len(root_nodes) == 0:
        errors.append("故障树没有根节点")
    elif len(root_nodes) > 1:
        errors.append(f"故障树有多个根节点: {root_nodes}")

    # 检查孤立节点
    isolated = list(nx.isolates(graph))
    if isolated:
        errors.append(f"故障树有孤立节点: {isolated}")

    # 检查叶节点是否有证据（入度为 0，因为边是 child → parent，叶节点没有子节点）
    leaf_nodes = [n for n in graph.nodes() if graph.in_degree(n) == 0]
    for leaf in leaf_nodes:
        if graph.nodes[leaf].get('evidence_point_id') is None:
            errors.append(f"叶节点 {leaf} 没有关联证据点位")

    return errors
```

---

#### P1-4: 缺少 DiagnosisContext 的 from dataclasses import field
**问题**: `DiagnosisContext` 数据类使用了 `field(default_factory=list)`，但没有导入 `field`。

**影响**: 代码无法运行。

**修复建议**: 添加导入：

```python
from dataclasses import dataclass, field
from typing import Dict, List
import networkx as nx
```

---

### P2 - 次要问题（建议修复）

#### P2-1: 故障树缓存引用计数实现不完整
**问题**: `FaultTreeCache` 类的 `get_tree()` 和 `release_tree()` 方法需要成对调用，但代码中没有说明如何保证调用配对（如异常时是否自动释放）。

**影响**: 引用计数泄漏，旧版本故障树无法删除。

**修复建议**: 使用上下文管理器（context manager）自动管理引用计数：

```python
from contextlib import asynccontextmanager

class FaultTreeCache:
    # ... 现有代码 ...

    @asynccontextmanager
    async def use_tree(self, tree_id: int):
        """上下文管理器：自动管理引用计数"""
        tree = await self.get_tree(tree_id)
        try:
            yield tree
        finally:
            await self.release_tree(tree_id)

# 使用示例
async def diagnose_l2(alarm_event: AlarmEvent) -> DiagnosisContext:
    tree_id = await self.select_fault_tree(...)
    async with self.cache.use_tree(tree_id) as graph:
        # 推理逻辑...
        pass
```

---

#### P2-2: 日志记录中的时间测量代码重复
**问题**: Dev Notes 第 11 节的日志记录示例中，多次使用 `start_time = time.time()` 和 `(time.time() - start_time) * 1000` 计算耗时，代码重复。

**影响**: 代码可读性差，容易出错。

**修复建议**: 使用装饰器或上下文管理器简化时间测量：

```python
from contextlib import contextmanager
import time

@contextmanager
def measure_time(name: str):
    """测量代码块耗时"""
    start = time.time()
    yield
    elapsed_ms = (time.time() - start) * 1000
    logger.info(f"{name} 耗时: {elapsed_ms:.2f}ms")

# 使用示例
async def diagnose_l2(alarm_event: AlarmEvent) -> DiagnosisContext:
    with measure_time("证据收集"):
        evidence = await self.collect_evidence(leaf_nodes)

    with measure_time("概率传播"):
        node_probs = self.propagate_probabilities(graph, leaf_probs)

    with measure_time("根因提取"):
        root_cause_path = self.extract_root_cause_path(graph, node_probs, root_node)
```

---

#### P2-3: 测试数据中的边方向不一致
**问题**: Dev Notes 第 12 节测试数据中，边定义为 `('leaf1', 'root')`（child → parent），但注释说"Root(OR) → [Leaf1, Leaf2]"，箭头方向是 parent → child。

**影响**: 注释与代码不一致，容易混淆。

**修复建议**: 统一注释和代码：

```python
# 简单故障树: Root(OR) ← [Leaf1, Leaf2]（边方向: child → parent）
test_tree = {
    'nodes': [
        {'id': 'root', 'type': 'root', 'gate': 'OR', 'prior': 0.1},
        {'id': 'leaf1', 'type': 'leaf', 'prior': 0.2, 'threshold': 50, 'k': 2.0},
        {'id': 'leaf2', 'type': 'leaf', 'prior': 0.3, 'threshold': 60, 'k': 2.0},
    ],
    'edges': [
        ('leaf1', 'root'),  # child → parent
        ('leaf2', 'root'),
    ]
}
```

---

#### P2-4: 缺少 EvidenceItem 的 timestamp 字段默认值
**问题**: `EvidenceItem` 数据类的 `timestamp` 字段类型是 `str`，但没有默认值。当证据不可用时，创建 `EvidenceItem(status='unavailable')` 会缺少 `timestamp` 字段。

**影响**: 代码运行时会抛出 `TypeError: missing 1 required positional argument: 'timestamp'`。

**修复建议**: 为所有字段添加默认值或使用 `Optional`：

```python
from typing import Optional

@dataclass
class EvidenceItem:
    """证据项"""
    point_id: Optional[int] = None
    point_name: Optional[str] = None
    value: Optional[float] = None
    threshold: Optional[float] = None
    timestamp: Optional[str] = None
    status: str = 'available'  # 'available' | 'unavailable' | 'timeout'
```

---

## 审查总结

### 严重程度统计
- P0（严重）: 1 个
- P1（重要）: 4 个
- P2（次要）: 4 个
- 总计: 9 个

### 关键风险
1. **边方向与数据库不一致**（P0-1）: 核心数据加载逻辑错误
2. **证据收集超时处理错误**（P1-1）: 运行时异常
3. **故障树验证逻辑错误**（P1-3）: 无法正确验证故障树

### 修复优先级
1. 立即修复 P0-1（边方向转换）
2. 修复 P1 问题（特别是 P1-1 和 P1-3）
3. P2 问题可以在实现过程中逐步完善

### 整体评价
第一轮修改解决了大部分关键问题（NetworkX 图方向、数值稳定性、并发安全、DiagnosisContext 扩展等），但仍存在一些实现细节问题。修复 P0 和 P1 问题后，该 Story 可以进入实施阶段。

### 相比第一轮的改进
- ✅ 修复了 NetworkX 图方向问题（使用 child → parent）
- ✅ 修复了 Sigmoid 数值稳定性问题
- ✅ 添加了故障树缓存并发安全机制
- ✅ 扩展了 DiagnosisContext 数据类（性能指标、错误信息）
- ✅ 添加了时间窗口聚合策略说明
- ✅ 添加了故障树选择优先级规则
- ✅ 添加了故障树验证逻辑
- ✅ 添加了日志记录策略
- ✅ 修复了测试数据计算错误

### 剩余问题
- ⚠️ 边方向与数据库表结构的转换逻辑需要明确
- ⚠️ 证据收集超时处理需要修复
- ⚠️ 故障树验证逻辑的入度/出度判断需要修正
- ⚠️ 一些小的代码细节问题（导入、默认值等）

---

**审查完成时间**: 2026-03-06
**下一步**: 根据第二轮审查意见修改 Story 24.5，然后可以开始实施
