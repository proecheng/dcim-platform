# Story 24.3: 故障树数据模型与 CRUD

**Epic**: 24 - 智能诊断核心引擎
**Story ID**: 24.3
**创建日期**: 2026-03-06
**状态**: ready-for-dev

---

## User Story

As a 管理员,
I want 创建和管理故障树（节点、边、设备映射），并确保故障树结构为有效的 DAG,
So that L2 推理引擎可以基于故障树进行因果推理分析。

---

## 验收标准（Acceptance Criteria）

### 1. 数据模型创建

- **Given** 系统需要存储故障树结构
- **When** 执行数据库迁移
- **Then** 创建以下表：
  - `fault_trees`: 故障树元数据（id, name, description, status, created_at, updated_at, created_by）
  - `fault_tree_nodes`: 故障树节点（id, tree_id, node_type, gate_type, name, description, prior_probability, evidence_point_id, config）
  - `fault_tree_edges`: 故障树边（id, tree_id, parent_node_id, child_node_id）
  - `fault_tree_device_mapping`: 故障树与设备类型映射（id, tree_id, device_type, alarm_type, priority）
- **And** 所有表使用 Alembic 迁移脚本创建
- **And** 外键约束正确设置（tree_id → fault_trees.id, parent_node_id/child_node_id → fault_tree_nodes.id）
- **And** 索引正确创建（tree_id, device_type, alarm_type）

### 2. DAG 验证器

- **Given** 管理员创建或更新故障树
- **When** 提交故障树结构（节点 + 边）
- **Then** 系统使用 NetworkX 验证 DAG 有效性：
  - 检查是否存在环（`nx.is_directed_acyclic_graph()`）
  - 检查节点连通性：根节点无入边有出边，叶节点有入边无出边，中间节点既有入边又有出边
  - 检查是否存在多个根节点（只允许一个根节点）
  - 检查边的端点是否都存在于节点集合中
  - 检查是否存在自环（节点指向自己）
  - 检查从根节点能否到达所有节点（连通性）
- **And** 验证失败时返回明确的错误信息（如"检测到环: A → B → C → A"）
- **And** 验证成功时返回 `{"valid": true, "node_count": N, "edge_count": M}`

### 3. 故障树 CRUD API

- **Given** 管理员需要管理故障树
- **When** 调用 RESTful API
- **Then** 支持以下操作：
  - `POST /api/v1/fault-trees`: 创建故障树（仅元数据，status=draft）
  - `GET /api/v1/fault-trees`: 列表查询（支持分页、按 status 过滤）
  - `GET /api/v1/fault-trees/{id}`: 获取故障树详情（含节点和边）
  - `PUT /api/v1/fault-trees/{id}`: 更新故障树元数据
  - `DELETE /api/v1/fault-trees/{id}`: 删除故障树（仅允许 draft 状态）
- **And** 所有 API 需要 admin 角色权限（RBAC）
- **And** 返回标准 JSON 格式（含 id, name, status, created_at 等）

### 4. 节点 CRUD API

- **Given** 管理员需要管理故障树节点
- **When** 调用节点 API
- **Then** 支持以下操作：
  - `POST /api/v1/fault-trees/{tree_id}/nodes`: 创建节点
  - `GET /api/v1/fault-trees/{tree_id}/nodes`: 列表查询
  - `GET /api/v1/fault-trees/{tree_id}/nodes/{node_id}`: 获取节点详情
  - `PUT /api/v1/fault-trees/{tree_id}/nodes/{node_id}`: 更新节点
  - `DELETE /api/v1/fault-trees/{tree_id}/nodes/{node_id}`: 删除节点（自动级联删除相关的边）
- **And** 节点类型（node_type）限制为: root, intermediate, leaf
- **And** 门类型（gate_type）限制为: AND, OR, NULL（叶节点和根节点为 NULL）
- **And** 叶节点必须关联 evidence_point_id（外键到 points 表，ON DELETE RESTRICT 阻止删除被引用的点位）
- **And** prior_probability 范围为 [0.0, 1.0]，叶节点必填（NOT NULL），默认值 0.5

### 5. 边 CRUD API

- **Given** 管理员需要管理故障树边
- **When** 调用边 API
- **Then** 支持以下操作：
  - `POST /api/v1/fault-trees/{tree_id}/edges`: 创建边
  - `GET /api/v1/fault-trees/{tree_id}/edges`: 列表查询
  - `PUT /api/v1/fault-trees/{tree_id}/edges/{edge_id}`: 更新边（修改端点）
  - `DELETE /api/v1/fault-trees/{tree_id}/edges/{edge_id}`: 删除边
- **And** 创建或更新边时延迟 DAG 验证（不在每次操作时验证，而是在批量操作完成或故障树状态变更时验证）
- **And** 验证失败时拒绝创建并返回错误信息

### 6. 设备映射 CRUD API

- **Given** 管理员需要配置故障树与设备类型的映射关系
- **When** 调用映射 API
- **Then** 支持以下操作：
  - `POST /api/v1/fault-trees/{tree_id}/device-mappings`: 创建映射
  - `GET /api/v1/fault-trees/{tree_id}/device-mappings`: 列表查询
  - `PUT /api/v1/fault-trees/{tree_id}/device-mappings/{mapping_id}`: 更新映射（修改 priority 或 alarm_type）
  - `DELETE /api/v1/fault-trees/{tree_id}/device-mappings/{mapping_id}`: 删除映射
- **And** device_type 必须是有效的设备类型（如 UPS, PDU, AC 等）
- **And** alarm_type 必须是有效的告警类型（如 voltage_low, temperature_high 等）
- **And** priority 用于多个故障树匹配同一设备类型时的优先级排序

### 7. 批量操作支持

- **Given** 管理员需要一次性创建完整的故障树
- **When** 调用批量创建 API `POST /api/v1/fault-trees/batch`
- **Then** 接收包含故障树元数据、节点列表、边列表、映射列表的 JSON
- **And** 在单个事务中创建所有数据
- **And** 创建后自动执行 DAG 验证
- **And** 验证失败时回滚整个事务（全部失败策略，确保故障树结构完整性）
- **And** 数据格式错误（如 prior_probability 超出范围）时立即返回 400 错误并回滚

---

## 技术实现要点

### 1. 数据库表结构

```sql
-- 故障树元数据表
CREATE TABLE fault_trees (
    id SERIAL PRIMARY KEY,
    name VARCHAR(200) NOT NULL UNIQUE,  -- 添加唯一性约束
    description TEXT,
    status VARCHAR(20) NOT NULL DEFAULT 'draft',  -- draft, active, archived
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    created_by INTEGER REFERENCES users(id),
    updated_by INTEGER REFERENCES users(id)  -- 添加 updated_by 字段
);

-- 故障树节点表
CREATE TABLE fault_tree_nodes (
    id SERIAL PRIMARY KEY,
    tree_id INTEGER NOT NULL REFERENCES fault_trees(id) ON DELETE CASCADE,
    node_type VARCHAR(20) NOT NULL,  -- root, intermediate, leaf
    gate_type VARCHAR(10),  -- AND, OR, NULL
    name VARCHAR(200) NOT NULL,
    description TEXT,
    prior_probability FLOAT NOT NULL DEFAULT 0.5 CHECK (prior_probability >= 0.0 AND prior_probability <= 1.0),  -- 添加 NOT NULL 和默认值
    evidence_point_id INTEGER REFERENCES points(id) ON DELETE RESTRICT,  -- 阻止删除被引用的点位
    config TEXT,  -- SQLite 兼容：使用 TEXT 存储 JSON
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- 故障树边表
CREATE TABLE fault_tree_edges (
    id SERIAL PRIMARY KEY,
    tree_id INTEGER NOT NULL REFERENCES fault_trees(id) ON DELETE CASCADE,
    parent_node_id INTEGER NOT NULL REFERENCES fault_tree_nodes(id) ON DELETE CASCADE,
    child_node_id INTEGER NOT NULL REFERENCES fault_tree_nodes(id) ON DELETE CASCADE,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(tree_id, parent_node_id, child_node_id),
    CHECK(parent_node_id != child_node_id)  -- 防止自环
);

-- 故障树设备映射表
CREATE TABLE fault_tree_device_mapping (
    id SERIAL PRIMARY KEY,
    tree_id INTEGER NOT NULL REFERENCES fault_trees(id) ON DELETE CASCADE,
    device_type VARCHAR(50) NOT NULL,
    alarm_type VARCHAR(100),
    priority INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(tree_id, device_type, alarm_type)
);

-- 索引
CREATE INDEX idx_fault_tree_nodes_tree_id ON fault_tree_nodes(tree_id);
CREATE INDEX idx_fault_tree_edges_tree_id ON fault_tree_edges(tree_id);
CREATE INDEX idx_fault_tree_device_mapping_device_type ON fault_tree_device_mapping(device_type, alarm_type);
```

### 2. DAG 验证器实现

```python
# backend/app/services/diagnosis/dag_validator.py
import networkx as nx
from typing import List, Dict, Tuple

class DAGValidator:
    """故障树 DAG 验证器"""

    @staticmethod
    def validate(nodes: List[Dict], edges: List[Dict]) -> Tuple[bool, str]:
        """
        验证故障树是否为有效的 DAG

        Args:
            nodes: 节点列表 [{"id": 1, "node_type": "root", ...}, ...]
            edges: 边列表 [{"parent_node_id": 1, "child_node_id": 2}, ...]

        Returns:
            (is_valid, error_message)
        """
        if not nodes:
            return False, "故障树至少需要一个节点"

        # 构建 NetworkX 有向图
        G = nx.DiGraph()

        # 添加节点
        node_ids = set()
        root_nodes = []
        leaf_nodes = []
        intermediate_nodes = []

        for node in nodes:
            node_id = node["id"]
            node_ids.add(node_id)
            G.add_node(node_id, **node)

            node_type = node.get("node_type")
            if node_type == "root":
                root_nodes.append(node_id)
            elif node_type == "leaf":
                leaf_nodes.append(node_id)
            elif node_type == "intermediate":
                intermediate_nodes.append(node_id)

        # 检查根节点数量
        if len(root_nodes) == 0:
            return False, "故障树必须有一个根节点"
        if len(root_nodes) > 1:
            return False, f"故障树只能有一个根节点，当前有 {len(root_nodes)} 个"

        # 添加边
        for edge in edges:
            parent_id = edge["parent_node_id"]
            child_id = edge["child_node_id"]

            # 检查端点是否存在
            if parent_id not in node_ids:
                return False, f"边的父节点 {parent_id} 不存在"
            if child_id not in node_ids:
                return False, f"边的子节点 {child_id} 不存在"

            # 检查自环
            if parent_id == child_id:
                return False, f"检测到自环: 节点 {parent_id} 指向自己"

            G.add_edge(parent_id, child_id)

        # 检查是否为 DAG（无环）
        if not nx.is_directed_acyclic_graph(G):
            # 找出环
            try:
                cycle = nx.find_cycle(G)
                cycle_str = " → ".join([str(u) for u, v in cycle] + [str(cycle[0][0])])
                return False, f"检测到环: {cycle_str}"
            except nx.NetworkXNoCycle:
                # 理论上不应该到这里，但如果到了说明 is_directed_acyclic_graph 有误判
                return False, "检测到环，但无法定位具体环路"

        # 检查节点连通性
        root_id = root_nodes[0]

        # 根节点：无入边，有出边
        if G.in_degree(root_id) > 0:
            return False, f"根节点 {root_id} 不应有入边"
        if G.out_degree(root_id) == 0:
            return False, f"根节点 {root_id} 必须有出边"

        # 叶节点：有入边，无出边
        for leaf_id in leaf_nodes:
            if G.in_degree(leaf_id) == 0:
                return False, f"叶节点 {leaf_id} 必须有入边"
            if G.out_degree(leaf_id) > 0:
                return False, f"叶节点 {leaf_id} 不应有出边"

        # 中间节点：既有入边又有出边
        for inter_id in intermediate_nodes:
            if G.in_degree(inter_id) == 0:
                return False, f"中间节点 {inter_id} 必须有入边"
            if G.out_degree(inter_id) == 0:
                return False, f"中间节点 {inter_id} 必须有出边"

        # 检查连通性（从根节点能到达所有节点）
        reachable = nx.descendants(G, root_id)
        reachable.add(root_id)
        if len(reachable) != len(node_ids):
            unreachable = node_ids - reachable
            return False, f"以下节点从根节点不可达: {unreachable}"

        return True, ""

    @staticmethod
    def build_graph(nodes: List[Dict], edges: List[Dict]) -> nx.DiGraph:
        """构建 NetworkX 图（用于推理引擎）"""
        G = nx.DiGraph()
        for node in nodes:
            G.add_node(node["id"], **node)
        for edge in edges:
            G.add_edge(edge["parent_node_id"], edge["child_node_id"])
        return G
```

### 3. API 路由结构

```python
# backend/app/api/v1/fault_trees.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.core.security import get_current_user, require_role
from app.models.user import User
from app.services.diagnosis.dag_validator import DAGValidator

router = APIRouter(prefix="/fault-trees", tags=["fault-trees"])

@router.post("/", dependencies=[Depends(require_role("admin"))])
async def create_fault_tree(...):
    """创建故障树"""
    pass

@router.get("/")
async def list_fault_trees(...):
    """列表查询"""
    pass

@router.get("/{tree_id}")
async def get_fault_tree(...):
    """获取详情"""
    pass

@router.put("/{tree_id}", dependencies=[Depends(require_role("admin"))])
async def update_fault_tree(...):
    """更新故障树"""
    pass

@router.delete("/{tree_id}", dependencies=[Depends(require_role("admin"))])
async def delete_fault_tree(...):
    """删除故障树（仅 draft 状态）"""
    pass

@router.post("/{tree_id}/nodes", dependencies=[Depends(require_role("admin"))])
async def create_node(...):
    """创建节点"""
    pass

@router.post("/{tree_id}/edges", dependencies=[Depends(require_role("admin"))])
async def create_edge(...):
    """创建边（自动触发 DAG 验证）"""
    pass

@router.post("/batch", dependencies=[Depends(require_role("admin"))])
async def batch_create_fault_tree(...):
    """批量创建故障树"""
    pass
```

### 4. ORM 模型

```python
# backend/app/models/fault_tree.py
from sqlalchemy import Column, Integer, String, Text, Float, ForeignKey, TIMESTAMP, CheckConstraint, func
from sqlalchemy.orm import relationship
from app.core.database import Base

class FaultTree(Base):
    __tablename__ = "fault_trees"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(200), nullable=False, unique=True)
    description = Column(Text)
    status = Column(String(20), nullable=False, default="draft")
    created_at = Column(TIMESTAMP, nullable=False, server_default=func.now())
    updated_at = Column(TIMESTAMP, nullable=False, server_default=func.now(), onupdate=func.now())
    created_by = Column(Integer, ForeignKey("users.id"))
    updated_by = Column(Integer, ForeignKey("users.id"))

    nodes = relationship("FaultTreeNode", back_populates="tree", cascade="all, delete-orphan")
    edges = relationship("FaultTreeEdge", back_populates="tree", cascade="all, delete-orphan")
    device_mappings = relationship("FaultTreeDeviceMapping", back_populates="tree", cascade="all, delete-orphan")

class FaultTreeNode(Base):
    __tablename__ = "fault_tree_nodes"

    id = Column(Integer, primary_key=True, index=True)
    tree_id = Column(Integer, ForeignKey("fault_trees.id", ondelete="CASCADE"), nullable=False, index=True)
    node_type = Column(String(20), nullable=False)
    gate_type = Column(String(10))
    name = Column(String(200), nullable=False)
    description = Column(Text)
    prior_probability = Column(Float, nullable=False, default=0.5, server_default="0.5")
    evidence_point_id = Column(Integer, ForeignKey("points.id", ondelete="RESTRICT"))
    config = Column(Text)  # SQLite 兼容：使用 Text 存储 JSON
    created_at = Column(TIMESTAMP, nullable=False, server_default=func.now())

    __table_args__ = (
        CheckConstraint("prior_probability >= 0.0 AND prior_probability <= 1.0", name="check_prior_probability"),
    )

    tree = relationship("FaultTree", back_populates="nodes")
    parent_edges = relationship("FaultTreeEdge", foreign_keys="FaultTreeEdge.child_node_id", back_populates="child_node")
    child_edges = relationship("FaultTreeEdge", foreign_keys="FaultTreeEdge.parent_node_id", back_populates="parent_node")

class FaultTreeEdge(Base):
    __tablename__ = "fault_tree_edges"

    id = Column(Integer, primary_key=True, index=True)
    tree_id = Column(Integer, ForeignKey("fault_trees.id", ondelete="CASCADE"), nullable=False, index=True)
    parent_node_id = Column(Integer, ForeignKey("fault_tree_nodes.id", ondelete="CASCADE"), nullable=False)
    child_node_id = Column(Integer, ForeignKey("fault_tree_nodes.id", ondelete="CASCADE"), nullable=False)
    created_at = Column(TIMESTAMP, nullable=False, server_default=func.now())

    __table_args__ = (
        CheckConstraint("parent_node_id != child_node_id", name="check_no_self_loop"),
    )

    tree = relationship("FaultTree", back_populates="edges")
    parent_node = relationship("FaultTreeNode", foreign_keys=[parent_node_id], back_populates="child_edges")
    child_node = relationship("FaultTreeNode", foreign_keys=[child_node_id], back_populates="parent_edges")

class FaultTreeDeviceMapping(Base):
    __tablename__ = "fault_tree_device_mapping"

    id = Column(Integer, primary_key=True, index=True)
    tree_id = Column(Integer, ForeignKey("fault_trees.id", ondelete="CASCADE"), nullable=False)
    device_type = Column(String(50), nullable=False, index=True)
    alarm_type = Column(String(100), index=True)
    priority = Column(Integer, nullable=False, default=0)
    created_at = Column(TIMESTAMP, nullable=False, server_default=func.now())

    tree = relationship("FaultTree", back_populates="device_mappings")
```

---

## 测试策略

### 1. 单元测试

**文件**: `backend/tests/services/test_dag_validator.py`

**测试用例**:
- `test_empty_graph`: 空图验证失败
- `test_single_node`: 单节点图验证成功
- `test_valid_dag`: 合法 DAG 验证成功
- `test_cycle_detection`: 含环图验证失败
- `test_multiple_roots`: 多根节点验证失败
- `test_isolated_node`: 孤立节点验证失败
- `test_disconnected_subgraph`: 断开子图验证失败
- `test_invalid_edge_endpoint`: 边端点不存在验证失败
- `test_self_loop`: 自环验证失败
- `test_duplicate_edge`: 重复边验证（应允许，由数据库 UNIQUE 约束处理）
- `test_leaf_with_outgoing_edge`: 叶节点有出边验证失败
- `test_root_with_incoming_edge`: 根节点有入边验证失败
- `test_intermediate_without_gate_type`: 中间节点 gate_type 为 NULL 验证（应允许，由业务逻辑处理）

### 2. API 集成测试

**文件**: `backend/tests/api/test_fault_trees.py`

**测试用例**:
- `test_create_fault_tree`: 创建故障树
- `test_list_fault_trees`: 列表查询
- `test_get_fault_tree`: 获取详情
- `test_update_fault_tree`: 更新故障树
- `test_delete_fault_tree_draft`: 删除 draft 状态故障树
- `test_delete_fault_tree_active_forbidden`: 删除 active 状态故障树失败
- `test_create_node`: 创建节点
- `test_create_edge_with_validation`: 创建边并触发 DAG 验证
- `test_batch_create_fault_tree`: 批量创建故障树
- `test_rbac_admin_only`: 非 admin 角色无法创建故障树
- `test_concurrent_edge_creation`: 并发创建边测试（使用 asyncio.gather 模拟并发请求）
- `test_update_edge`: 更新边端点
- `test_update_device_mapping`: 更新设备映射

### 3. 性能测试

**测试环境**:
- 开发环境: SQLite, Intel i5-8250U, 8GB RAM
- 生产环境: PostgreSQL 14, 4 vCPU, 16GB RAM

**性能目标**:
- 1000 节点故障树加载时间 < 2 秒（开发环境）/ < 1 秒（生产环境）
- DAG 验证时间（1000 节点）< 500ms
- 批量创建故障树（100 节点 + 150 边）< 3 秒（开发环境）/ < 2 秒（生产环境）

---

## 依赖关系

### 前置依赖
- Story 24.1: L1 规则引擎（已完成）
- Story 24.2: 诊断调度器与并发控制（已完成）
- Epic 14: PostgreSQL 迁移完成
- NetworkX >= 3.0（需添加到 requirements.txt，注意 3.0 与 2.x 有 breaking changes）

### 后续依赖
- Story 24.4: 故障树版本管理与 HMAC 签名（需要 fault_trees 表）
- Story 24.5: L2 故障树推理引擎（需要 DAG 验证器和数据模型）

---

## 验收检查清单

- [ ] Alembic 迁移脚本创建并执行成功（空数据库和已有数据库两种场景）
- [ ] 四张表（fault_trees, fault_tree_nodes, fault_tree_edges, fault_tree_device_mapping）创建成功
- [ ] 外键约束和索引正确设置
- [ ] DAG 验证器单元测试全部通过（13 个测试用例）
- [ ] 故障树 CRUD API 实现并测试通过
- [ ] 节点 CRUD API 实现并测试通过（含级联删除）
- [ ] 边 CRUD API 实现并测试通过（含更新操作和延迟验证）
- [ ] 设备映射 CRUD API 实现并测试通过（含更新操作）
- [ ] 批量创建 API 实现并测试通过
- [ ] RBAC 权限控制测试通过（admin 角色）
- [ ] API 文档（Swagger）更新，包含 Pydantic Schema 定义
- [ ] 性能测试通过（1000 节点加载 < 2s 开发环境）
- [ ] 并发测试通过（并发创建边无竞态条件）

---

## 工作量估算

- 数据库迁移脚本: 1 小时
- ORM 模型: 1 小时
- DAG 验证器: 2 小时
- CRUD API 实现: 4 小时
- 单元测试: 2 小时
- API 集成测试: 2 小时
- 文档更新: 0.5 小时

**总计**: 约 12.5 小时（1.5 个工作日）

---

## FR 追溯

- FR34-5: 故障树建模
- FR34-7: 故障树 CRUD 管理

---

## 备注

1. **SQLite 兼容性**: 开发环境使用 SQLite，生产环境使用 PostgreSQL。迁移脚本和 ORM 模型已统一使用 `Text` 类型存储 JSON（SQLite 兼容），避免使用 PostgreSQL 特有的 `JSONB` 类型。在应用层使用 `json.loads/dumps` 处理 JSON 数据。

2. **NetworkX 依赖**: 需要在 `requirements.txt` 中添加 `networkx>=3.0`。注意 NetworkX 3.0 与 2.x 有 breaking changes（如 `nx.find_cycle` 返回值格式不同），确保使用 3.0+ 版本。

3. **扩展性**: `config` 字段（Text）预留用于存储节点的扩展配置（如 sigmoid 参数、阈值等），供 Story 24.5 使用。

4. **事务一致性**: 批量创建 API 必须在单个事务中执行，确保原子性。数据格式错误时立即返回 400 错误并回滚。

5. **级联删除**: 删除故障树时自动级联删除所有节点、边和映射（`ON DELETE CASCADE`）。删除节点时自动级联删除相关的边。删除点位时阻止删除（`ON DELETE RESTRICT`），需先解除叶节点关联。

6. **DAG 验证优化**: 为避免性能问题，边的创建和更新操作不立即触发 DAG 验证，而是延迟到批量操作完成或故障树状态变更时统一验证。单次验证时间复杂度 O(V+E)，避免 O(E×(V+E)) 的重复验证。

7. **Pydantic Schema**: 实施时需要定义完整的请求和响应 Schema（如 `FaultTreeCreate`, `FaultTreeResponse`, `NodeCreate`, `EdgeCreate` 等），确保 FastAPI 自动生成 Swagger 文档和请求参数验证。
