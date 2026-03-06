# Story 24.5: L2 故障树推理引擎

Status: ready-for-dev

## Story

As a 运维工程师,
I want 系统基于故障树进行因果推理分析中等复杂度故障,
So that 我可以在5秒内获得包含根因路径和置信度的诊断结果。

## Acceptance Criteria (验收标准)

1. **AC-1: 故障树选择与证据收集** — 通过 `fault_tree_device_mapping` 表（tree_id, device_type, alarm_type）匹配告警事件的 device_type + alarm_type 选择适用的故障树（可能匹配多棵，按优先级取第一棵），然后收集所有叶节点证据
   - 从 Redis 读取叶节点关联点位的最新值
   - 从 TimescaleDB 查询时间窗口内（按设备类型差异化：电气5min/温度30min/湿度60min，配置存储在 `system_configs` 表）的历史数据
   - 将点位值与叶节点阈值对比，通过 sigmoid 映射计算叶节点实际概率: `P = prior + (1.0 - prior) × sigmoid(k × (value - threshold))`（k 为斜率参数，默认 2.0，存储在节点配置中），使概率随偏离阈值的程度平滑变化而非二值跳变

2. **AC-2: 正向概率传播** — 从叶节点向根节点传播
   - OR 门: P = 1 - ∏(1 - P(child_i))
   - AND 门: P = ∏ P(child_i)
   - 使用 NetworkX 图遍历: `reversed(list(nx.topological_sort(graph)))` 反转拓扑序（原始拓扑序从 root 开始，反转后从叶节点开始），保证从叶到根的传播顺序

3. **AC-3: 根因路径提取** — 在传播过程中记录每个节点的"贡献度"（子节点概率对父节点概率的偏导），从根节点沿贡献度最大的子节点回溯（OR门→选概率最大的子节点，AND门→选偏离先验最大的子节点），生成根因路径

4. **AC-4: 结果输出** — 根因节点、置信度（根节点概率）、推理路径（节点链）、证据列表

5. **AC-5: 性能与覆盖率** — 全部过程 < 5 秒完成，累计覆盖 Top 20 高频故障中 ≥18 类（90%，L1 12类 + L2 额外6类）

6. **AC-6: 异常容错** — 推理过程中任何步骤异常（如点位查询超时）不中断推理，该证据标记为"不可用"使用先验概率替代

7. **AC-7: 返回完整上下文** — L2 推理函数返回 `DiagnosisContext` 数据类（包含: 完整节点概率映射 dict[str,float]、NetworkX DiGraph 引用、叶节点概率向量、证据收集结果列表），供 Story 26.2 L3 引擎复用（不仅返回最终结论）

## Tasks / Subtasks (任务分解)

- [ ] Task 1: 创建 L2 推理引擎核心模块 (AC: #1, #2, #3, #4, #7)
  - [ ] 1.1 创建 `backend/app/services/diagnosis/fault_tree.py` — FaultTreeInferenceEngine 类
  - [ ] 1.2 实现 `DiagnosisContext` 数据类（完整节点概率映射、DiGraph 引用、叶节点概率向量、证据列表）
  - [ ] 1.3 实现 `select_fault_tree()` 方法 — 通过 device_type + alarm_type 从 `fault_tree_device_mapping` 表查询匹配的故障树，按优先级排序取第一棵
  - [ ] 1.4 实现 `load_fault_tree_to_networkx()` 方法 — 从 PostgreSQL 加载故障树（fault_tree_node + fault_tree_edge）构建 NetworkX DiGraph，**注意：数据库存储 parent → child，需反转为 child → parent**，缓存到内存
  - [ ] 1.5 实现 `collect_evidence()` 方法 — 并发查询 Redis（最新值）+ TimescaleDB（时间窗口历史），时间窗口配置从 `system_configs` 表读取 `diagnosis_time_windows` JSON

- [ ] Task 2: 实现概率计算与传播 (AC: #1, #2)
  - [ ] 2.1 实现 `compute_leaf_probability()` 方法 — sigmoid 映射: `P = prior + (1.0 - prior) × sigmoid(k × (value - threshold))`，k 默认 2.0，从节点配置读取
  - [ ] 2.2 实现 `propagate_probabilities()` 方法 — 反转拓扑序遍历，OR 门: P = 1 - ∏(1 - P(child_i))，AND 门: P = ∏ P(child_i)
  - [ ] 2.3 实现贡献度计算 — 记录每个节点的子节点贡献度（概率偏导）

- [ ] Task 3: 实现根因路径提取 (AC: #3, #4)
  - [ ] 3.1 实现 `extract_root_cause_path()` 方法 — 从根节点沿贡献度最大的子节点回溯
  - [ ] 3.2 OR 门选择策略 — 选概率最大的子节点
  - [ ] 3.3 AND 门选择策略 — 选偏离先验最大的子节点
  - [ ] 3.4 生成根因路径（节点链）和证据列表

- [ ] Task 4: 异常处理与容错 (AC: #6)
  - [ ] 4.1 证据查询超时保护 — `asyncio.wait_for(collect_evidence(), timeout=3)` 单个证据超时不中断整体推理
  - [ ] 4.2 证据不可用标记 — 超时或查询失败的证据标记为"不可用"，使用先验概率替代
  - [ ] 4.3 整体推理超时保护 — `asyncio.wait_for(inference(), timeout=10)` 整体超时返回部分结果或降级到 L1

- [ ] Task 5: 性能优化 (AC: #5)
  - [ ] 5.1 故障树内存缓存 — 启动时预加载活跃版本故障树到内存，版本切换时热替换
  - [ ] 5.2 证据收集并发 — `asyncio.gather` 并行查询 Redis 和 TimescaleDB
  - [ ] 5.3 时间窗口配置缓存 — 从 `system_configs` 表读取 `diagnosis_time_windows` JSON 并缓存到内存
  - [ ] 5.4 性能测试 — 1000 节点故障树推理 < 5 秒

- [ ] Task 6: 集成到诊断调度器 (AC: #4, #5)
  - [ ] 6.1 在 `backend/app/services/diagnosis/engine.py` 中注册 L2 引擎
  - [ ] 6.2 实现级别路由逻辑 — 告警事件根据复杂度路由到 L1/L2/L3
  - [ ] 6.3 L2 引擎调用接口 — `async def diagnose_l2(alarm_event: AlarmEvent) -> DiagnosisContext`
  - [ ] 6.4 结果写入 `diagnosis_session` + `diagnosis_result` 表

- [ ] Task 7: 单元测试与集成测试 (AC: 全部)
  - [ ] 7.1 测试概率传播边缘情况 — 全零先验、全一先验、单子节点门、深层树 ≥10 层
  - [ ] 7.2 测试 sigmoid 映射极端输入 — value=threshold±1000
  - [ ] 7.3 测试已知故障树+已知输入→已知输出 — 集成测试
  - [ ] 7.4 测试证据查询超时容错 — 模拟 Redis/TimescaleDB 超时
  - [ ] 7.5 测试故障树选择逻辑 — 多棵匹配树按优先级排序
  - [ ] 7.6 测试根因路径提取 — OR 门和 AND 门的不同选择策略
  - [ ] 7.7 测试性能 — 1000 节点故障树推理 < 5 秒

## Dev Notes (开发指南)

### 1. 故障树数据模型

故障树存储在 PostgreSQL，运行时加载到 NetworkX DiGraph 内存缓存。

**数据库表结构**（已在 Story 24.3 创建）:
```sql
-- 故障树主表
fault_tree:
  id, name, version, status(draft/active/archived), hmac_signature, created_at

-- 故障树节点
fault_tree_node:
  id, tree_id, node_type(root/intermediate/leaf), gate_type(AND/OR/NULL),
  name, description, prior_probability, evidence_point_id, threshold, sigmoid_k

-- 故障树边
fault_tree_edge:
  id, tree_id, parent_node_id, child_node_id

-- 故障树设备映射
fault_tree_device_mapping:
  id, tree_id, device_type, alarm_type, priority
```

**NetworkX 图结构**:
```python
import networkx as nx

# 节点属性
graph.nodes[node_id] = {
    'node_type': 'root' | 'intermediate' | 'leaf',
    'gate_type': 'AND' | 'OR' | None,
    'name': str,
    'description': str,
    'prior_probability': float,  # 先验概率 [0, 1]
    'evidence_point_id': int | None,  # 叶节点关联的点位 ID
    'threshold': float | None,  # 叶节点阈值
    'sigmoid_k': float,  # sigmoid 斜率参数，默认 2.0
}

# 边方向: child → parent（叶 → 根）
# 这样拓扑序自然是从叶到根，无需反转
# 注意：数据库 fault_tree_edge 表存储的是 parent_node_id → child_node_id
# 加载时需要反转边方向
graph.add_edge(child_id, parent_id)
```

**从数据库加载故障树**:
```python
async def load_fault_tree_to_networkx(tree_id: int) -> nx.DiGraph:
    """从数据库加载故障树并构建 NetworkX 图"""
    graph = nx.DiGraph()

    # 加载节点
    nodes = await session.execute(
        select(FaultTreeNode).where(FaultTreeNode.tree_id == tree_id)
    )
    for node in nodes.scalars():
        graph.add_node(
            node.id,
            node_type=node.node_type,
            gate_type=node.gate_type,
            name=node.name,
            description=node.description,
            prior_probability=node.prior_probability,
            evidence_point_id=node.evidence_point_id,
            threshold=node.threshold,
            sigmoid_k=node.sigmoid_k or 2.0
        )

    # 加载边（数据库存储 parent → child，需反转为 child → parent）
    edges = await session.execute(
        select(FaultTreeEdge).where(FaultTreeEdge.tree_id == tree_id)
    )
    for edge in edges.scalars():
        # 反转边方向: child → parent
        graph.add_edge(edge.child_node_id, edge.parent_node_id)

    return graph
```

### 2. 证据收集时间窗口配置

时间窗口配置存储在 `system_configs` 表，key 为 `diagnosis_time_windows`，value 为 JSON:

```json
{
  "electrical": 300,    // 电气设备 5 分钟（秒）
  "temperature": 1800,  // 温度传感器 30 分钟
  "humidity": 3600,     // 湿度传感器 60 分钟
  "default": 600        // 默认 10 分钟
}
```

**查询逻辑**:
```python
async def get_time_window(device_type: str) -> int:
    config = await get_system_config("diagnosis_time_windows")
    windows = json.loads(config.value)
    return windows.get(device_type, windows.get("default", 600))
```

### 3. Sigmoid 概率映射

叶节点概率不是二值（0/1），而是通过 sigmoid 函数平滑映射:

```python
import math

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
    """
    计算叶节点概率

    Args:
        value: 点位实际值
        threshold: 阈值
        prior: 先验概率
        k: sigmoid 斜率参数，默认 2.0

    Returns:
        概率 [0, 1]
    """
    deviation = value - threshold
    sigmoid_value = sigmoid_stable(k * deviation)
    return prior + (1.0 - prior) * sigmoid_value
```

**示例**:
- prior = 0.1, threshold = 50, k = 2.0
- value = 50 → P = 0.1 + 0.9 × 0.5 = 0.55
- value = 55 → P = 0.1 + 0.9 × 0.88 = 0.89
- value = 45 → P = 0.1 + 0.9 × 0.12 = 0.21

### 4. 概率传播算法

**OR 门**（任一子节点异常即异常）:
```python
def or_gate(child_probs: list[float]) -> float:
    """P = 1 - ∏(1 - P(child_i))"""
    product = 1.0
    for p in child_probs:
        product *= (1.0 - p)
    return 1.0 - product
```

**AND 门**（所有子节点异常才异常）:
```python
def and_gate(child_probs: list[float]) -> float:
    """P = ∏ P(child_i)"""
    product = 1.0
    for p in child_probs:
        product *= p
    return product
```

**拓扑排序遍历**:
```python
import networkx as nx

def propagate_probabilities(graph: nx.DiGraph, leaf_probs: dict[str, float]) -> dict[str, float]:
    """
    从叶节点向根节点传播概率

    Args:
        graph: NetworkX DiGraph（边方向: child → parent）
        leaf_probs: 叶节点概率字典 {node_id: probability}

    Returns:
        所有节点概率字典 {node_id: probability}
    """
    node_probs = leaf_probs.copy()

    # 拓扑序（从叶到根，因为边是 child → parent）
    topo_order = list(nx.topological_sort(graph))

    for node_id in topo_order:
        if node_id in node_probs:
            continue  # 叶节点已有概率

        # 获取子节点（predecessors，因为边是 child → parent）
        children = list(graph.predecessors(node_id))
        child_probs = [node_probs[child] for child in children]

        # 根据门类型计算概率
        gate_type = graph.nodes[node_id]['gate_type']
        if gate_type == 'OR':
            node_probs[node_id] = or_gate(child_probs)
        elif gate_type == 'AND':
            node_probs[node_id] = and_gate(child_probs)
        else:
            # 中间节点无门类型，使用 OR 门（保守策略）
            node_probs[node_id] = or_gate(child_probs)

    return node_probs
```

### 5. 根因路径提取

从根节点沿贡献度最大的子节点回溯:

```python
def extract_root_cause_path(
    graph: nx.DiGraph,
    node_probs: dict[str, float],
    root_node: str
) -> list[str]:
    """
    提取根因路径

    Args:
        graph: NetworkX DiGraph（边方向: child → parent）
        node_probs: 所有节点概率字典
        root_node: 根节点 ID

    Returns:
        根因路径（节点 ID 列表，从根到叶）
    """
    path = [root_node]
    current = root_node

    while True:
        # 获取子节点（predecessors，因为边是 child → parent）
        children = list(graph.predecessors(current))
        if not children:
            break  # 到达叶节点

        gate_type = graph.nodes[current]['gate_type']

        if gate_type == 'OR':
            # OR 门：选概率最大的子节点
            next_node = max(children, key=lambda c: node_probs[c])
        elif gate_type == 'AND':
            # AND 门：选概率最大的子节点（与 OR 门一致）
            # 因为 AND 门所有子节点都异常，选概率最大的更可能是主要根因
            next_node = max(children, key=lambda c: node_probs[c])
        else:
            # 默认选概率最大
            next_node = max(children, key=lambda c: node_probs[c])

        path.append(next_node)
        current = next_node

    return path
```

### 6. DiagnosisContext 数据类

L2 引擎返回完整上下文，供 L3 引擎复用:

```python
from dataclasses import dataclass, field
from typing import Dict, List, Optional
import networkx as nx

@dataclass
class EvidenceItem:
    """证据项"""
    point_id: Optional[int] = None
    point_name: Optional[str] = None
    value: Optional[float] = None
    threshold: Optional[float] = None
    timestamp: Optional[str] = None
    status: str = 'available'  # 'available' | 'unavailable' | 'timeout'

@dataclass
class DiagnosisContext:
    """诊断上下文（L2 引擎输出，L3 引擎输入）"""
    # 基础信息
    alarm_event_id: int
    device_id: int
    device_type: str
    alarm_type: str

    # 故障树信息
    tree_id: int
    tree_name: str
    graph: nx.DiGraph  # NetworkX 图引用

    # 推理结果
    node_probabilities: Dict[str, float]  # 所有节点概率
    leaf_probabilities: Dict[str, float]  # 叶节点概率
    root_probability: float  # 根节点概率（置信度）
    root_cause_path: List[str]  # 根因路径（节点 ID 列表）

    # 证据列表
    evidence: List[EvidenceItem]

    # 性能指标
    inference_time_ms: float  # 总耗时（毫秒）
    evidence_collection_time_ms: float  # 证据收集耗时
    propagation_time_ms: float  # 概率传播耗时
    path_extraction_time_ms: float  # 根因提取耗时

    # 错误和警告
    warnings: List[str] = field(default_factory=list)  # 警告信息（如证据不可用）
    errors: List[str] = field(default_factory=list)    # 错误信息（如超时、降级）
    degraded: bool = False  # 是否降级到 L1
```

### 7. 性能优化要点

1. **故障树内存缓存**: 启动时预加载活跃版本故障树到内存，避免每次推理都查询数据库
2. **证据收集并发**: 使用 `asyncio.gather` 并行查询 Redis 和 TimescaleDB
3. **时间窗口配置缓存**: 从 `system_configs` 表读取一次后缓存到内存
4. **超时保护**: 整体推理 `asyncio.wait_for(inference(), timeout=10)`，单个证据查询 `timeout=1`

**故障树缓存并发安全**:
```python
class FaultTreeCache:
    """故障树内存缓存（线程安全）"""
    def __init__(self):
        self._cache: Dict[int, nx.DiGraph] = {}
        self._lock = asyncio.Lock()
        self._ref_counts: Dict[int, int] = {}
        self._pending_delete: Set[int] = set()

    async def get_tree(self, tree_id: int) -> nx.DiGraph:
        """获取故障树（增加引用计数）"""
        async with self._lock:
            if tree_id not in self._cache:
                self._cache[tree_id] = await self._load_tree(tree_id)
            self._ref_counts[tree_id] = self._ref_counts.get(tree_id, 0) + 1
            return self._cache[tree_id]

    async def release_tree(self, tree_id: int):
        """释放故障树（减少引用计数）"""
        async with self._lock:
            self._ref_counts[tree_id] -= 1
            if self._ref_counts[tree_id] == 0 and tree_id in self._pending_delete:
                del self._cache[tree_id]
                del self._ref_counts[tree_id]
                self._pending_delete.remove(tree_id)

    async def invalidate_tree(self, tree_id: int):
        """标记故障树为待删除（版本切换时调用）"""
        async with self._lock:
            if tree_id in self._cache:
                if self._ref_counts.get(tree_id, 0) == 0:
                    del self._cache[tree_id]
                else:
                    self._pending_delete.add(tree_id)
```

**证据收集并发策略**:
```python
async def collect_evidence(self, leaf_nodes: List[str]) -> Dict[str, EvidenceItem]:
    """并发收集所有叶节点证据"""
    tasks = [self._query_single_evidence(node) for node in leaf_nodes]
    try:
        results = await asyncio.wait_for(
            asyncio.gather(*tasks, return_exceptions=True),
            timeout=3.0  # 整体超时 3 秒
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

async def _query_single_evidence(self, node_id: str) -> EvidenceItem:
    """查询单个证据（超时 1 秒）"""
    try:
        return await asyncio.wait_for(
            self._do_query_evidence(node_id),
            timeout=1.0
        )
    except asyncio.TimeoutError:
        return EvidenceItem(status='timeout')
```

### 8. 时间窗口历史数据聚合策略

不同类型点位使用不同的聚合策略:

| 点位类型 | 聚合策略 | 说明 |
|---------|---------|------|
| 温度/湿度 | AVG（平均值） | 时间窗口内平均值 |
| 电压/电流 | MAX（最大值） | 时间窗口内峰值 |
| 功率 | AVG（平均值） | 时间窗口内平均功率 |
| 开关量 | ANY（任意触发） | 时间窗口内任意触发即为 True |
| 频率 | AVG（平均值） | 时间窗口内平均频率 |

```python
async def query_historical_data(
    point_id: int,
    time_window_seconds: int,
    aggregation: str = 'avg'  # 'avg' | 'max' | 'min' | 'any'
) -> float:
    """查询历史数据并聚合"""
    end_time = datetime.utcnow()
    start_time = end_time - timedelta(seconds=time_window_seconds)

    if aggregation == 'avg':
        query = select(func.avg(PointHistory.value)).where(
            PointHistory.point_id == point_id,
            PointHistory.timestamp >= start_time,
            PointHistory.timestamp <= end_time
        )
    elif aggregation == 'max':
        query = select(func.max(PointHistory.value)).where(...)
    elif aggregation == 'min':
        query = select(func.min(PointHistory.value)).where(...)
    elif aggregation == 'any':
        # 开关量：任意触发即为 True
        query = select(func.max(PointHistory.value)).where(...)
        # 返回 1.0 或 0.0

    result = await session.execute(query)
    return result.scalar_one_or_none() or 0.0
```

### 9. 故障树选择优先级规则

`fault_tree_device_mapping` 表的 `priority` 字段语义:
- priority 数值越小，优先级越高（1 > 2 > 3）
- 相同 priority 时，按 tree_id 降序（最新的树优先）

```python
async def select_fault_tree(
    device_type: str,
    alarm_type: str
) -> Optional[int]:
    """选择匹配的故障树"""
    query = (
        select(FaultTreeDeviceMapping.tree_id)
        .join(FaultTree, FaultTree.id == FaultTreeDeviceMapping.tree_id)
        .where(
            FaultTreeDeviceMapping.device_type == device_type,
            FaultTreeDeviceMapping.alarm_type == alarm_type,
            FaultTree.status == 'active'  # 只选择活跃版本
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

### 10. 故障树验证逻辑

从数据库加载故障树后，验证图的完整性:

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

### 11. 日志记录策略

推理过程中的关键步骤都应该记录日志:

```python
import logging

logger = logging.getLogger(__name__)

async def diagnose_l2(alarm_event: AlarmEvent) -> DiagnosisContext:
    """L2 故障树推理"""
    logger.info(f"L2 推理开始: alarm_id={alarm_event.id}, device={alarm_event.device_id}")

    # 故障树选择
    tree_id = await self.select_fault_tree(alarm_event.device_type, alarm_event.alarm_type)
    if tree_id is None:
        logger.warning(f"未找到匹配的故障树: device_type={alarm_event.device_type}, alarm_type={alarm_event.alarm_type}")
        # 降级到 L1
        return await self.diagnose_l1(alarm_event)

    logger.info(f"选择故障树: tree_id={tree_id}")

    # 证据收集
    start_time = time.time()
    evidence = await self.collect_evidence(leaf_nodes)
    evidence_time = (time.time() - start_time) * 1000
    unavailable_count = sum(1 for e in evidence.values() if e.status != 'available')
    if unavailable_count > 0:
        logger.warning(f"证据收集完成: 总数={len(evidence)}, 不可用={unavailable_count}")
    else:
        logger.info(f"证据收集完成: 总数={len(evidence)}, 耗时={evidence_time:.2f}ms")

    # 概率传播
    start_time = time.time()
    node_probs = self.propagate_probabilities(graph, leaf_probs)
    propagation_time = (time.time() - start_time) * 1000
    logger.info(f"概率传播完成: 根节点概率={node_probs[root_node]:.4f}, 耗时={propagation_time:.2f}ms")

    # 根因提取
    start_time = time.time()
    root_cause_path = self.extract_root_cause_path(graph, node_probs, root_node)
    path_time = (time.time() - start_time) * 1000
    logger.info(f"根因路径: {' → '.join(root_cause_path)}, 耗时={path_time:.2f}ms")

    return context
```

### 12. 测试策略

**单元测试必须覆盖**:
1. 概率传播边缘情况（全零先验、全一先验、单子节点门、深层树 ≥10 层）
2. Sigmoid 映射极端输入（value=threshold±1000）
3. 已知故障树+已知输入→已知输出的集成测试

**测试数据**:
```python
import math

def sigmoid_stable(x):
    if x >= 0:
        z = math.exp(-x)
        return 1.0 / (1.0 + z)
    else:
        z = math.exp(x)
        return z / (1.0 + z)

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

# 已知输入
evidence = {
    'leaf1': 55,  # 超过阈值 50
    'leaf2': 58,  # 接近阈值 60
}

# 预期输出（使用代码计算）
k = 2.0
# leaf1: value=55, threshold=50, deviation=5
expected_leaf1_prob = 0.2 + 0.8 * sigmoid_stable(k * 5)  # ≈ 0.9933
# leaf2: value=58, threshold=60, deviation=-2
expected_leaf2_prob = 0.3 + 0.7 * sigmoid_stable(k * -2)  # ≈ 0.3126
# root: OR 门
expected_root_prob = 1 - (1 - expected_leaf1_prob) * (1 - expected_leaf2_prob)  # ≈ 0.9979
```

### 13. 与其他 Story 的集成

- **Story 24.1 (L1 规则引擎)**: L2 引擎作为 L1 的升级，处理更复杂的故障场景
- **Story 24.2 (诊断调度器)**: L2 引擎注册到调度器，通过级别路由调用
- **Story 24.3 (故障树数据模型)**: L2 引擎从 PostgreSQL 加载故障树数据
- **Story 24.4 (故障树版本管理)**: L2 引擎加载活跃版本故障树，支持热替换
- **Story 26.2 (L3 贝叶斯引擎)**: L3 引擎复用 L2 的 `DiagnosisContext` 输出

### 14. 架构参考

详见 `_bmad-output/planning-artifacts/architecture.md` Section 18.2 "L2 故障树推理"。

---

**FR 追溯:** FR34-2, FR34-5~12, FR34-29
**Epic:** 24 (智能诊断核心引擎)
**Dependencies:** Story 24.1, 24.2, 24.3, 24.4
**Estimated Effort:** 3-4 天
