# Story 24.5 对抗性审查报告 - 第一轮

**审查日期**: 2026-03-06
**审查人**: Claude (对抗性审查模式)
**Story**: 24.5 L2 故障树推理引擎

---

## 审查发现问题

### P0 - 严重问题（必须修复）

#### P0-1: NetworkX 图方向错误
**问题**: 代码示例中使用 `graph.successors(node_id)` 获取子节点，但这要求边的方向是 parent → child。然而在拓扑排序中，`nx.topological_sort(graph)` 返回的顺序是从"入度为0的节点"开始，这意味着如果边是 parent → child，拓扑序应该是 root → ... → leaf（正向），而不是反向。

**影响**: 概率传播逻辑会完全错误，导致推理失败。

**修复建议**:
1. 明确边的方向约定：parent → child（正向）或 child → parent（反向）
2. 如果使用 parent → child，则拓扑序应该是 `list(nx.topological_sort(graph))`（不反转），然后从后往前遍历（`reversed(...)`）
3. 或者使用 child → parent 边，则拓扑序直接是 `list(nx.topological_sort(graph))`，从前往后遍历

**推荐方案**: 使用 child → parent 边（叶 → 根），这样拓扑序自然是从叶到根，无需反转。

```python
# 推荐：child → parent 边
graph.add_edge(child_id, parent_id)

# 拓扑序自然是从叶到根
for node_id in nx.topological_sort(graph):
    if node_id in node_probs:
        continue  # 叶节点已有概率

    # 获取子节点（predecessors，因为边是 child → parent）
    children = list(graph.predecessors(node_id))
    child_probs = [node_probs[child] for child in children]
    # ...
```

---

#### P0-2: 根因路径提取逻辑错误
**问题**: `extract_root_cause_path()` 使用 `graph.successors(current)` 获取子节点，但如果边是 child → parent，successors 返回的是父节点，不是子节点。

**影响**: 根因路径提取会失败或返回错误路径。

**修复建议**: 根据边方向使用正确的 API：
- 如果边是 parent → child，使用 `graph.successors(node)`
- 如果边是 child → parent，使用 `graph.predecessors(node)`

---

#### P0-3: 故障树缓存并发安全问题
**问题**: Task 5.1 提到"版本切换时热替换"，但没有说明如何保证并发安全。如果在推理过程中切换版本，可能导致：
1. 推理使用的图被替换，引用失效
2. 多个推理任务同时访问正在替换的图

**影响**: 并发推理时版本切换可能导致崩溃或数据不一致。

**修复建议**:
1. 使用读写锁（`asyncio.Lock` 或 `threading.RLock`）保护缓存访问
2. 版本切换时采用"写时复制"策略：创建新图，原子替换引用，旧图等待所有推理任务完成后再释放
3. 或者使用引用计数：每个推理任务持有图的引用，版本切换时标记旧图为"待删除"，引用计数归零时删除

```python
class FaultTreeCache:
    def __init__(self):
        self._cache: Dict[int, nx.DiGraph] = {}
        self._lock = asyncio.Lock()
        self._ref_counts: Dict[int, int] = {}

    async def get_tree(self, tree_id: int) -> nx.DiGraph:
        async with self._lock:
            if tree_id not in self._cache:
                self._cache[tree_id] = await self._load_tree(tree_id)
            self._ref_counts[tree_id] = self._ref_counts.get(tree_id, 0) + 1
            return self._cache[tree_id]

    async def release_tree(self, tree_id: int):
        async with self._lock:
            self._ref_counts[tree_id] -= 1
            if self._ref_counts[tree_id] == 0 and tree_id in self._pending_delete:
                del self._cache[tree_id]
                del self._ref_counts[tree_id]
```

---

#### P0-4: 证据查询超时粒度不合理
**问题**: Task 4.1 提到"单个证据超时 3 秒"，但如果一个故障树有 100 个叶节点，即使并发查询，也可能需要 3 秒 × 100 / 并发数。如果并发数是 10，总耗时就是 30 秒，远超 5 秒目标。

**影响**: 性能目标无法达成。

**修复建议**:
1. 单个证据查询超时应该更短（0.5-1 秒）
2. 使用 `asyncio.gather(..., return_exceptions=True)` 并发查询所有证据，整体超时 3 秒
3. 超时的证据标记为"不可用"，使用先验概率

```python
async def collect_evidence(self, leaf_nodes: List[str]) -> Dict[str, EvidenceItem]:
    tasks = [self._query_single_evidence(node) for node in leaf_nodes]
    try:
        results = await asyncio.wait_for(
            asyncio.gather(*tasks, return_exceptions=True),
            timeout=3.0
        )
    except asyncio.TimeoutError:
        # 整体超时，使用已完成的结果
        results = [task.result() if task.done() else None for task in tasks]

    evidence = {}
    for node, result in zip(leaf_nodes, results):
        if isinstance(result, Exception) or result is None:
            evidence[node] = EvidenceItem(status='unavailable')
        else:
            evidence[node] = result
    return evidence
```

---

### P1 - 重要问题（强烈建议修复）

#### P1-1: Sigmoid 映射数值稳定性问题
**问题**: 当 `k * deviation` 很大时（如 k=2.0, deviation=1000），`math.exp(-k * deviation)` 会溢出（返回 inf 或 0），导致 sigmoid 计算错误。

**影响**: 极端输入时概率计算错误。

**修复建议**: 使用数值稳定的 sigmoid 实现：

```python
def sigmoid_stable(x: float) -> float:
    """数值稳定的 sigmoid 函数"""
    if x >= 0:
        z = math.exp(-x)
        return 1.0 / (1.0 + z)
    else:
        z = math.exp(x)
        return z / (1.0 + z)

def compute_leaf_probability(
    value: float,
    threshold: float,
    prior: float,
    k: float = 2.0
) -> float:
    deviation = value - threshold
    sigmoid_value = sigmoid_stable(k * deviation)
    return prior + (1.0 - prior) * sigmoid_value
```

---

#### P1-2: 时间窗口历史数据聚合策略缺失
**问题**: AC-1 提到"从 TimescaleDB 查询时间窗口内历史数据"，但没有说明如何聚合这些数据（平均值？最大值？最小值？趋势？）。

**影响**: 实现时需要猜测聚合策略，可能不符合预期。

**修复建议**: 在 Dev Notes 中明确聚合策略：
- 温度/湿度：时间窗口内平均值
- 电压/电流：时间窗口内最大值（峰值）
- 开关量：时间窗口内任意触发即为 True
- 趋势分析：线性回归斜率（可选，L3 引擎使用）

```python
async def query_historical_data(
    point_id: int,
    time_window_seconds: int,
    aggregation: str = 'avg'  # 'avg' | 'max' | 'min' | 'any'
) -> float:
    end_time = datetime.utcnow()
    start_time = end_time - timedelta(seconds=time_window_seconds)

    if aggregation == 'avg':
        query = select(func.avg(PointHistory.value)).where(...)
    elif aggregation == 'max':
        query = select(func.max(PointHistory.value)).where(...)
    # ...
```

---

#### P1-3: 故障树选择优先级规则不明确
**问题**: AC-1 提到"可能匹配多棵，按优先级取第一棵"，但 `fault_tree_device_mapping` 表的 `priority` 字段语义不明确（数值越大优先级越高？还是越小？）。

**影响**: 实现时可能选择错误的故障树。

**修复建议**: 在 Dev Notes 中明确优先级规则：
- priority 数值越小，优先级越高（1 > 2 > 3）
- 相同 priority 时，按 tree_id 降序（最新的树优先）

```python
async def select_fault_tree(
    device_type: str,
    alarm_type: str
) -> Optional[int]:
    query = (
        select(FaultTreeDeviceMapping.tree_id)
        .where(
            FaultTreeDeviceMapping.device_type == device_type,
            FaultTreeDeviceMapping.alarm_type == alarm_type
        )
        .order_by(
            FaultTreeDeviceMapping.priority.asc(),  # 数值越小优先级越高
            FaultTreeDeviceMapping.tree_id.desc()   # 相同优先级选最新
        )
        .limit(1)
    )
    result = await session.execute(query)
    return result.scalar_one_or_none()
```

---

#### P1-4: DiagnosisContext 缺少错误信息字段
**问题**: `DiagnosisContext` 数据类没有字段记录推理过程中的错误或警告（如证据不可用、超时、降级等）。

**影响**: L3 引擎或前端无法知道推理过程中发生了什么问题，难以调试和向用户解释。

**修复建议**: 添加 `warnings` 和 `errors` 字段：

```python
@dataclass
class DiagnosisContext:
    # ... 现有字段 ...

    # 错误和警告
    warnings: List[str] = field(default_factory=list)  # 警告信息（如证据不可用）
    errors: List[str] = field(default_factory=list)    # 错误信息（如超时、降级）
    degraded: bool = False  # 是否降级到 L1
```

---

#### P1-5: 根因路径提取的 AND 门策略不合理
**问题**: AND 门选择"偏离先验最大的子节点"，但这可能选择概率很低的子节点。例如：
- 子节点 A: prior=0.1, actual=0.2（偏离 0.1）
- 子节点 B: prior=0.5, actual=0.9（偏离 0.4）

按偏离最大选 B，但 B 的概率 0.9 更高，更可能是根因。

**影响**: AND 门的根因路径可能不准确。

**修复建议**: AND 门也选择概率最大的子节点，或者选择"概率 × 偏离"的加权值最大的子节点：

```python
if gate_type == 'AND':
    # 方案1: 选概率最大（与 OR 门一致）
    next_node = max(children, key=lambda c: node_probs[c])

    # 方案2: 选概率 × 偏离的加权值最大
    def weighted_score(c):
        prior = graph.nodes[c]['prior_probability']
        prob = node_probs[c]
        deviation = abs(prob - prior)
        return prob * deviation
    next_node = max(children, key=weighted_score)
```

---

### P2 - 次要问题（建议修复）

#### P2-1: 测试数据计算错误
**问题**: Dev Notes 第 8 节测试数据中，`expected_leaf2_prob` 计算错误：
- value=58, threshold=60, deviation=-2
- sigmoid(2.0 * -2) = sigmoid(-4) ≈ 0.018
- P = 0.3 + 0.7 × 0.018 ≈ 0.31（不是 0.35）

**影响**: 测试用例会失败。

**修复建议**: 重新计算或使用代码生成预期值：

```python
import math

def sigmoid(x):
    return 1.0 / (1.0 + math.exp(-x))

prior = 0.3
k = 2.0
deviation = 58 - 60  # -2
expected = prior + (1.0 - prior) * sigmoid(k * deviation)
print(f"expected_leaf2_prob = {expected:.4f}")  # 0.3126
```

---

#### P2-2: 缺少日志记录指导
**问题**: Dev Notes 没有提到日志记录策略，但推理过程中的关键步骤（故障树选择、证据收集、概率传播、根因提取）都应该记录日志。

**影响**: 生产环境调试困难。

**修复建议**: 在 Dev Notes 中添加日志记录指导：

```python
import logging

logger = logging.getLogger(__name__)

async def diagnose_l2(alarm_event: AlarmEvent) -> DiagnosisContext:
    logger.info(f"L2 推理开始: alarm_id={alarm_event.id}, device={alarm_event.device_id}")

    # 故障树选择
    tree_id = await self.select_fault_tree(alarm_event.device_type, alarm_event.alarm_type)
    logger.info(f"选择故障树: tree_id={tree_id}")

    # 证据收集
    evidence = await self.collect_evidence(leaf_nodes)
    unavailable_count = sum(1 for e in evidence.values() if e.status != 'available')
    logger.warning(f"证据收集完成: 总数={len(evidence)}, 不可用={unavailable_count}")

    # 概率传播
    node_probs = self.propagate_probabilities(graph, leaf_probs)
    logger.info(f"概率传播完成: 根节点概率={node_probs[root_node]:.4f}")

    # 根因提取
    root_cause_path = self.extract_root_cause_path(graph, node_probs, root_node)
    logger.info(f"根因路径: {' → '.join(root_cause_path)}")

    return context
```

---

#### P2-3: 缺少性能监控指标
**问题**: `DiagnosisContext` 只有 `inference_time_ms` 一个性能指标，缺少细分指标（证据收集耗时、概率传播耗时、根因提取耗时）。

**影响**: 性能瓶颈难以定位。

**修复建议**: 添加细分性能指标：

```python
@dataclass
class DiagnosisContext:
    # ... 现有字段 ...

    # 性能指标
    inference_time_ms: float  # 总耗时
    evidence_collection_time_ms: float  # 证据收集耗时
    propagation_time_ms: float  # 概率传播耗时
    path_extraction_time_ms: float  # 根因提取耗时
```

---

#### P2-4: 缺少故障树验证逻辑
**问题**: 从数据库加载故障树后，没有验证图的完整性（如是否有环、是否有孤立节点、根节点是否唯一）。

**影响**: 错误的故障树数据可能导致推理失败。

**修复建议**: 在 `load_fault_tree_to_networkx()` 后添加验证：

```python
def validate_fault_tree(graph: nx.DiGraph) -> List[str]:
    """验证故障树完整性，返回错误列表"""
    errors = []

    # 检查是否有环
    if not nx.is_directed_acyclic_graph(graph):
        errors.append("故障树包含环")

    # 检查根节点数量
    root_nodes = [n for n in graph.nodes() if graph.in_degree(n) == 0]
    if len(root_nodes) == 0:
        errors.append("故障树没有根节点")
    elif len(root_nodes) > 1:
        errors.append(f"故障树有多个根节点: {root_nodes}")

    # 检查孤立节点
    isolated = list(nx.isolates(graph))
    if isolated:
        errors.append(f"故障树有孤立节点: {isolated}")

    # 检查叶节点是否有证据
    leaf_nodes = [n for n in graph.nodes() if graph.out_degree(n) == 0]
    for leaf in leaf_nodes:
        if graph.nodes[leaf].get('evidence_point_id') is None:
            errors.append(f"叶节点 {leaf} 没有关联证据点位")

    return errors
```

---

## 审查总结

### 严重程度统计
- P0（严重）: 4 个
- P1（重要）: 5 个
- P2（次要）: 4 个
- 总计: 13 个

### 关键风险
1. **NetworkX 图方向错误**（P0-1）: 核心算法错误，必须修复
2. **并发安全问题**（P0-3）: 生产环境可能崩溃
3. **性能目标无法达成**（P0-4）: 证据查询超时设计不合理

### 修复优先级
1. 立即修复 P0 问题（特别是 P0-1 和 P0-3）
2. 修复 P1 问题（特别是 P1-1 数值稳定性和 P1-4 错误信息）
3. P2 问题可以在实现过程中逐步完善

### 整体评价
Story 24.5 的设计思路清晰，技术方案合理，但存在一些关键的实现细节问题。修复 P0 和 P1 问题后，该 Story 可以进入实施阶段。

---

**审查完成时间**: 2026-03-06
**下一步**: 根据审查意见修改 Story 24.5，然后进行第二轮审查
