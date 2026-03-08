# Story 25.2: 电气参数节点集成

Status: done

## Story

As a 运维工程师,
I want 故障树能利用三相不平衡度、THD、功率因数等电气参数作为诊断证据,
So that 诊断引擎能识别电气专业问题（如谐波过高导致UPS异常）。

## Acceptance Criteria

1. **Given** 管理员在故障树中创建叶节点，关联了电气参数类型的点位
   **When** 诊断引擎收集证据时
   **Then** 支持以下电气参数类型作为故障树叶节点输入:
   - 三相不平衡度: 点位值 > 10% 时作为异常证据（概率→0.9）
   - 谐波畸变率 THD: 点位值 > 5% 时作为异常证据
   - 功率因数: 点位值 < 0.9 时作为异常证据
   **And** 阈值可在故障树节点配置中自定义（非硬编码）
   **And** 电气参数概率计算复用 Story 24.5 的 sigmoid 连续映射方式（不再二值化），阈值和斜率参数可在节点配置中自定义

## Tasks / Subtasks

- [ ] Task 1: 扩展故障树节点数据模型 (AC: #1)
  - [ ] 1.1 在 `FaultTreeNode` 模型中添加 `threshold_type` 字段 (ABOVE/BELOW)
  - [ ] 1.2 添加 `threshold_value` 字段（Float，可为 null）
  - [ ] 1.3 添加 `sigmoid_k` 字段（Float，默认 2.0，斜率参数）
  - [ ] 1.4 创建 Alembic 迁移脚本添加这 3 个字段
  - [ ] 1.5 更新 `FaultTreeNodeSchema` Pydantic 模型

- [ ] Task 2: 实现电气参数证据收集逻辑 (AC: #1)
  - [ ] 2.1 验证 Story 24.5 的 sigmoid 实现是否存在于 `backend/app/services/diagnosis/evidence_calculator.py`
  - [ ] 2.2 如不存在，创建 `evidence_calculator.py` 并实现 `calc_evidence_probability()` 函数
  - [ ] 2.3 在 L2 引擎中识别电气参数类型点位（从 Point.point_type 字段读取）
  - [ ] 2.4 实现 `get_point_latest_value(point_id, time_window)` 辅助函数（从 Redis 或 point_history 表查询）
  - [ ] 2.5 实现 `get_point_by_id(point_id)` 辅助函数（查询 Point 模型）
  - [ ] 2.6 根据 `threshold_type` (ABOVE/BELOW) 和 `threshold_value` 计算证据概率
  - [ ] 2.7 使用 `sigmoid_k` 参数控制映射曲线斜率
  - [ ] 2.8 处理阈值为 null 的情况（使用默认阈值）
  - [ ] 2.9 添加 point_value 边界检查（负数、NaN、Infinity）
  - [ ] 2.10 添加 Prometheus 监控指标（electrical_param_evidence_duration_seconds, electrical_param_evidence_total）

- [ ] Task 3: 集成到诊断引擎 (AC: #1)
  - [ ] 3.1 在 L2 引擎的证据收集阶段调用电气参数处理逻辑
  - [ ] 3.2 确保电气参数证据与其他证据类型统一处理
  - [ ] 3.3 在诊断日志中记录电气参数证据收集详情

- [ ] Task 4: 更新故障树管理 API (AC: #1)
  - [ ] 4.1 在故障树节点 CRUD API 中支持新增的 3 个字段
  - [ ] 4.2 添加字段验证逻辑（threshold_type 枚举、sigmoid_k > 0、threshold_value 范围验证）
  - [ ] 4.3 更新 API 文档和示例（OpenAPI schema）
  - [ ] 4.4 添加 API 端点示例：POST /api/v1/fault-tree/nodes 创建电气参数节点
  - [ ] 4.5 添加 API 响应示例：包含新增字段的完整响应

- [ ] Task 5: 编写单元测试
  - [ ] 5.1 测试 sigmoid 映射函数（不同阈值、斜率参数）
  - [ ] 5.2 测试 ABOVE 类型阈值判定（三相不平衡度、THD）
  - [ ] 5.3 测试 BELOW 类型阈值判定（功率因数）
  - [ ] 5.4 测试默认阈值处理
  - [ ] 5.5 测试 point_value 边界情况（负数、NaN、Infinity、None）
  - [ ] 5.6 测试电气参数证据集成到 L2 推理流程（完整 mock 实现）
  - [ ] 5.7 测试 Prometheus 指标记录

- [ ] Task 6: 数据迁移和回滚策略 (AC: #1)
  - [ ] 6.1 在 Alembic 迁移脚本中添加时间戳格式的 revision ID
  - [ ] 6.2 添加表存在性检查（处理表不存在的情况）
  - [ ] 6.3 实现安全的 downgrade() 逻辑（备份数据后再删除列）
  - [ ] 6.4 编写迁移测试脚本验证 upgrade/downgrade 流程

## Dev Notes

### 架构约束

**数据库模型（棕地扩展）:**
- 表名: `fault_tree_nodes`（已存在，需扩展字段）
- 新增字段:
  - `threshold_type`: VARCHAR(10), nullable, 枚举值 'ABOVE'/'BELOW'
  - `threshold_value`: FLOAT, nullable（null 时使用默认阈值，范围验证: 0 < value < 1000）
  - `sigmoid_k`: FLOAT, nullable, default 2.0（斜率参数，范围验证: 0.1 <= k <= 10.0）
- 索引建议: 如果查询频繁按 threshold_type 过滤，考虑添加索引（可选，视性能测试结果）
- ORM 模型路径: `from app.models.diagnosis import FaultTreeNode`

**Point 模型字段（棕地已有）:**
- 表名: `points`（复数形式）
- 关键字段:
  - `point_type`: VARCHAR(50), 存储点位类型如 'PHASE_IMBALANCE', 'THD', 'POWER_FACTOR'
  - `point_name`: VARCHAR(100), 点位名称
  - `unit`: VARCHAR(20), 单位
  - `site_id`: INTEGER, 站点 ID
- ORM 模型路径: `from app.models import Point`

**PointHistory 模型字段（棕地已有）:**
- 表名: `point_history`（单数形式，棕地约定）
- 关键字段:
  - `point_id`: INTEGER, 外键关联 points.id
  - `value`: FLOAT, 点位值
  - `timestamp`: TIMESTAMP, 时间戳（存储格式: UTC）
- ORM 模型路径: `from app.models import PointHistory`
- 时区约定: 数据库存储 UTC 时间，查询时使用 `datetime.now(timezone.utc)` 而非已弃用的 `datetime.utcnow()`

**已有辅助函数（需验证或实现）:**
- `get_point_latest_value(point_id: int, time_window: int) -> Optional[float]`
  - 位置: `backend/app/services/diagnosis/l2_inference_engine.py` 或需新建
  - 功能: 从 Redis 或 point_history 表查询点位最新值
  - 返回: 点位值（float）或 None（无数据）
  - 错误处理: 数据库/Redis 异常时返回 None 并记录日志

- `get_point_by_id(point_id: int) -> Optional[Point]`
  - 位置: `backend/app/services/diagnosis/l2_inference_engine.py` 或需新建
  - 功能: 查询 Point 模型获取点位元数据
  - 返回: Point 对象或 None（点位不存在）
  - 字段: point_type, point_name, unit, site_id 等

**技术栈:**
- SQLAlchemy 2.0 异步模式
- Alembic 数据库迁移
- Pydantic Schema 验证
- Prometheus Client: 性能监控指标（需在 requirements.txt 中已声明 `prometheus-client>=0.16.0`）
- Sigmoid 映射函数（需验证 Story 24.5 是否已实现，否则新建 evidence_calculator.py）

**Prometheus 监控指标:**
- `electrical_param_evidence_duration_seconds`: 电气参数证据计算耗时（Histogram）
- `electrical_param_evidence_total`: 电气参数证据计算次数（Counter，按 point_type 标签分组）
- `electrical_param_evidence_errors_total`: 电气参数证据计算错误次数（Counter）
- 注意: 指标需在模块级别定义并自动注册到默认 Prometheus registry，多 worker 环境下使用 `multiprocess_mode='livesum'` 避免重复注册错误

**电气参数类型映射:**
```python
ELECTRICAL_PARAM_DEFAULTS = {
    "PHASE_IMBALANCE": {"threshold": 10.0, "threshold_type": "ABOVE", "sigmoid_k": 2.0},
    "THD": {"threshold": 5.0, "threshold_type": "ABOVE", "sigmoid_k": 2.0},
    "POWER_FACTOR": {"threshold": 0.9, "threshold_type": "BELOW", "sigmoid_k": 2.0},
}
```

**Sigmoid 映射公式（复用 Story 24.5）:**
```python
def calc_evidence_probability(
    value: float,
    threshold: float,
    threshold_type: str,  # 'ABOVE' or 'BELOW'
    sigmoid_k: float = 2.0,
    prior: float = 0.5
) -> float:
    """
    使用 sigmoid 函数将连续值映射到概率 [0, 1]

    Args:
        value: 实际测量值
        threshold: 阈值
        threshold_type: 'ABOVE' 表示超过阈值异常，'BELOW' 表示低于阈值异常
        sigmoid_k: 斜率参数，越大曲线越陡峭（默认 2.0）
        prior: 先验概率（默认 0.5）

    Returns:
        证据概率 [0, 1]
    """
    import math

    # 计算偏离度（归一化）
    if threshold_type == "ABOVE":
        deviation = (value - threshold) / threshold  # 超过阈值为正
    else:  # BELOW
        deviation = (threshold - value) / threshold  # 低于阈值为正

    # Sigmoid 映射: P = 1 / (1 + exp(-k * deviation))
    # deviation > 0 → P > 0.5 (异常)
    # deviation < 0 → P < 0.5 (正常)
    probability = 1.0 / (1.0 + math.exp(-sigmoid_k * deviation))

    return max(0.0, min(1.0, probability))
```

### 技术实现要点

**1. 数据库迁移 (Alembic)**

```python
# backend/alembic/versions/20260307_1430_add_electrical_param_fields.py
"""add electrical parameter fields to fault_tree_nodes

Revision ID: 20260307_1430
Revises: <previous_revision_id>
Create Date: 2026-03-07 14:30:00

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.engine.reflection import Inspector

# revision identifiers, used by Alembic.
revision = '20260307_1430'
down_revision = '<previous_revision_id>'  # 需要替换为实际的上一个 revision ID
branch_labels = None
depends_on = None

def upgrade():
    # 检查表是否存在
    conn = op.get_bind()
    inspector = Inspector.from_engine(conn)
    tables = inspector.get_table_names()

    if 'fault_tree_nodes' not in tables:
        raise RuntimeError(
            "表 fault_tree_nodes 不存在，无法执行迁移。"
            "请先运行创建故障树表的迁移脚本。"
        )

    # 检查列是否已存在（防止重复迁移）
    columns = [col['name'] for col in inspector.get_columns('fault_tree_nodes')]

    if 'threshold_type' not in columns:
        op.add_column('fault_tree_nodes',
            sa.Column('threshold_type', sa.String(10), nullable=True))

    if 'threshold_value' not in columns:
        op.add_column('fault_tree_nodes',
            sa.Column('threshold_value', sa.Float(), nullable=True))

    if 'sigmoid_k' not in columns:
        op.add_column('fault_tree_nodes',
            sa.Column('sigmoid_k', sa.Float(), nullable=True, server_default=sa.text('2.0')))

    # 索引建议：如果需要按 threshold_type 或 point_id 查询，可添加索引
    # op.create_index('ix_fault_tree_nodes_threshold_type', 'fault_tree_nodes', ['threshold_type'])
    # op.create_index('ix_fault_tree_nodes_point_id', 'fault_tree_nodes', ['point_id'])

def downgrade():
    """
    安全回滚策略：
    1. 检查表是否存在
    2. 备份数据（可选，生产环境建议手动备份）
    3. 删除列

    注意：downgrade 会丢失这些列的数据，生产环境执行前务必备份！
    """
    conn = op.get_bind()
    inspector = Inspector.from_engine(conn)
    tables = inspector.get_table_names()

    if 'fault_tree_nodes' not in tables:
        # 表不存在，无需回滚
        return

    columns = [col['name'] for col in inspector.get_columns('fault_tree_nodes')]

    # 按相反顺序删除列
    if 'sigmoid_k' in columns:
        op.drop_column('fault_tree_nodes', 'sigmoid_k')

    if 'threshold_value' in columns:
        op.drop_column('fault_tree_nodes', 'threshold_value')

    if 'threshold_type' in columns:
        op.drop_column('fault_tree_nodes', 'threshold_type')
```

**2. ORM 模型更新**

```python
# backend/app/models/diagnosis.py
from sqlalchemy import Column, Integer, String, Float, JSON, ForeignKey, DateTime, Text
from app.core.database import Base

class FaultTreeNode(Base):
    __tablename__ = "fault_tree_nodes"

    id = Column(Integer, primary_key=True, index=True)
    tree_id = Column(Integer, ForeignKey("fault_trees.id"), nullable=False)
    node_type = Column(String(20), nullable=False)  # 'AND', 'OR', 'LEAF'
    point_id = Column(Integer, ForeignKey("points.id"), nullable=True)

    # 新增：电气参数阈值配置
    threshold_type = Column(String(10), nullable=True)  # 'ABOVE' or 'BELOW'
    threshold_value = Column(Float, nullable=True)
    sigmoid_k = Column(Float, nullable=True, default=2.0)

    # 其他字段...
    prior_probability = Column(Float, nullable=True)
    description = Column(Text, nullable=True)
    created_at = Column(DateTime, nullable=False)
```

**3. Pydantic Schema 更新**

```python
# backend/app/schemas/diagnosis.py
from pydantic import BaseModel, Field, validator, root_validator
from typing import Optional
from enum import Enum
from datetime import datetime

class ThresholdType(str, Enum):
    ABOVE = "ABOVE"
    BELOW = "BELOW"

class FaultTreeNodeCreate(BaseModel):
    tree_id: int
    node_type: str  # 'AND', 'OR', 'LEAF'
    point_id: Optional[int] = None
    threshold_type: Optional[ThresholdType] = None
    threshold_value: Optional[float] = Field(default=None, gt=0, lt=1000)
    sigmoid_k: Optional[float] = Field(default=2.0, ge=0.1, le=10.0)
    prior_probability: Optional[float] = Field(default=0.5, ge=0, le=1)
    description: Optional[str] = None

    @validator('sigmoid_k')
    def validate_sigmoid_k(cls, v):
        if v is not None and (v < 0.1 or v > 10.0):
            raise ValueError('sigmoid_k must be between 0.1 and 10.0')
        return v

    @validator('threshold_value')
    def validate_threshold_value(cls, v):
        if v is not None and (v <= 0 or v >= 1000):
            raise ValueError('threshold_value must be between 0 and 1000')
        return v

    @root_validator
    def validate_threshold_consistency(cls, values):
        """验证 threshold_type 和 threshold_value 的一致性"""
        threshold_type = values.get('threshold_type')
        threshold_value = values.get('threshold_value')

        # 如果只设置了其中一个，给出警告（但不阻止，因为可以使用默认值）
        if (threshold_type is not None and threshold_value is None):
            # 允许：使用默认阈值
            pass
        elif (threshold_type is None and threshold_value is not None):
            # 允许：但会被忽略（因为没有 threshold_type）
            pass

        return values

class FaultTreeNodeResponse(FaultTreeNodeCreate):
    id: int
    created_at: datetime

    class Config:
        from_attributes = True
```

**4. 证据收集逻辑集成**

```python
# backend/app/services/diagnosis/l2_inference_engine.py
from app.services.diagnosis.evidence_calculator import (
    calc_evidence_probability,
    electrical_param_evidence_total
)
from app.models import Point
from app.core.database import async_session
from sqlalchemy import select
import redis.asyncio as redis
from app.core.config import get_settings
import logging

logger = logging.getLogger(__name__)
settings = get_settings()

ELECTRICAL_PARAM_DEFAULTS = {
    "PHASE_IMBALANCE": {"threshold": 10.0, "threshold_type": "ABOVE"},
    "THD": {"threshold": 5.0, "threshold_type": "ABOVE"},
    "POWER_FACTOR": {"threshold": 0.9, "threshold_type": "BELOW"},
}

async def get_point_latest_value(point_id: int, time_window: int) -> Optional[float]:
    """
    查询点位最新值（优先从 Redis，降级到数据库）

    Args:
        point_id: 点位 ID
        time_window: 时间窗口（秒），用于数据库查询

    Returns:
        点位值（float）或 None（无数据）
    """
    redis_client = None
    try:
        # 优先从 Redis 查询
        redis_client = redis.from_url(settings.REDIS_URL)
        value_str = await redis_client.get(f"point:value:{point_id}")
        if value_str:
            return float(value_str)
    except Exception as e:
        logger.warning(f"从 Redis 查询点位值失败: {e}")
    finally:
        if redis_client:
            try:
                await redis_client.close()
            except Exception as e:
                logger.warning(f"关闭 Redis 客户端失败: {e}")

    # 降级：从数据库查询
    try:
        async with async_session() as db:
            from app.models import PointHistory
            from sqlalchemy import desc
            from datetime import datetime, timedelta

            cutoff_time = datetime.now(timezone.utc) - timedelta(seconds=time_window)
            result = await db.execute(
                select(PointHistory.value)
                .where(PointHistory.point_id == point_id)
                .where(PointHistory.timestamp >= cutoff_time)
                .order_by(desc(PointHistory.timestamp))
                .limit(1)
            )
            row = result.scalar_one_or_none()
            return float(row) if row is not None else None
    except Exception as e:
        logger.error(f"从数据库查询点位值失败: {e}")
        return None

async def get_point_by_id(point_id: int) -> Optional[Point]:
    """
    查询 Point 模型获取点位元数据

    注意: 此函数使用 READ COMMITTED 隔离级别（SQLAlchemy 默认）
    如需更强的一致性保证，可在调用处使用事务包装

    Args:
        point_id: 点位 ID

    Returns:
        Point 对象或 None（点位不存在）
    """
    try:
        async with async_session() as db:
            result = await db.execute(
                select(Point).where(Point.id == point_id)
            )
            return result.scalar_one_or_none()
    except Exception as e:
        logger.error(f"查询点位元数据失败: {e}")
        return None

async def collect_leaf_evidence(node: FaultTreeNode, time_window: int) -> float:
    """收集叶节点证据（支持电气参数）"""
    if node.point_id is None:
        return node.prior_probability or 0.5

    # 查询点位最新值
    point_value = await get_point_latest_value(node.point_id, time_window)
    if point_value is None:
        logger.warning(f"点位 {node.point_id} 无数据，返回先验概率")
        return node.prior_probability or 0.5

    # 获取点位类型
    point = await get_point_by_id(node.point_id)
    if point is None:
        logger.error(f"点位 {node.point_id} 不存在，返回先验概率")
        return node.prior_probability or 0.5

    point_type = point.point_type  # e.g., 'PHASE_IMBALANCE', 'THD', 'POWER_FACTOR'

    # 检查是否为电气参数类型
    if point_type in ELECTRICAL_PARAM_DEFAULTS:
        # 使用节点配置的阈值，或使用默认值
        threshold = node.threshold_value
        threshold_type = node.threshold_type
        sigmoid_k = node.sigmoid_k or 2.0

        if threshold is None or threshold_type is None:
            # 使用默认配置
            defaults = ELECTRICAL_PARAM_DEFAULTS[point_type]
            threshold = defaults["threshold"]
            threshold_type = defaults["threshold_type"]

        # 计算证据概率（sigmoid 映射）
        probability = calc_evidence_probability(
            value=point_value,
            threshold=threshold,
            threshold_type=threshold_type,
            sigmoid_k=sigmoid_k,
            prior=node.prior_probability or 0.5
        )

        # 记录监控指标
        electrical_param_evidence_total.labels(point_type=point_type).inc()

        logger.info(
            f"电气参数证据: point_id={node.point_id}, type={point_type}, "
            f"value={point_value}, threshold={threshold}, "
            f"threshold_type={threshold_type}, probability={probability:.3f}"
        )

        return probability

    # 非电气参数类型，使用原有逻辑
    # 原有逻辑: 简单阈值判定（二值化）
    # 参考 Story 24.5 实现: backend/app/services/diagnosis/l2_inference_engine.py:collect_leaf_evidence()
    # 如果点位有配置的阈值，使用阈值判定
    if node.threshold_value is not None and node.threshold_type is not None:
        if node.threshold_type == "ABOVE":
            is_abnormal = point_value > node.threshold_value
        else:  # BELOW
            is_abnormal = point_value < node.threshold_value

        return 0.9 if is_abnormal else 0.1

    # 无阈值配置，返回先验概率
    return node.prior_probability or 0.5
```

**5. 证据计算函数（独立模块）**

```python
# backend/app/services/diagnosis/evidence_calculator.py
import math
import logging
from prometheus_client import Histogram, Counter

logger = logging.getLogger(__name__)

# Prometheus 监控指标
electrical_param_evidence_duration = Histogram(
    'electrical_param_evidence_duration_seconds',
    'Time spent calculating electrical parameter evidence'
)
electrical_param_evidence_total = Counter(
    'electrical_param_evidence_total',
    'Total electrical parameter evidence calculations',
    ['point_type']
)
electrical_param_evidence_errors = Counter(
    'electrical_param_evidence_errors_total',
    'Total electrical parameter evidence calculation errors'
)

def calc_evidence_probability(
    value: float,
    threshold: float,
    threshold_type: str,
    sigmoid_k: float = 2.0,
    prior: float = 0.5
) -> float:
    """
    使用 sigmoid 函数将连续值映射到概率 [0, 1]

    注意: 如果 Story 24.5 已实现此函数，应从该模块导入而非重复实现

    Args:
        value: 实际测量值
        threshold: 阈值
        threshold_type: 'ABOVE' 表示超过阈值异常，'BELOW' 表示低于阈值异常
        sigmoid_k: 斜率参数，越大曲线越陡峭（默认 2.0）
        prior: 先验概率（默认 0.5）

    Returns:
        证据概率 [0, 1]

    Examples:
        >>> # 三相不平衡度 12% (阈值 10%, ABOVE)
        >>> calc_evidence_probability(12.0, 10.0, "ABOVE", 2.0)
        0.731  # 超过阈值，概率 > 0.5

        >>> # 功率因数 0.85 (阈值 0.9, BELOW)
        >>> calc_evidence_probability(0.85, 0.9, "BELOW", 2.0)
        0.622  # 低于阈值，概率 > 0.5
    """
    with electrical_param_evidence_duration.time():
        # 边界检查：处理 NaN、Infinity、负数
        if not math.isfinite(value):
            logger.error(f"点位值非法: value={value}，返回先验概率 {prior}")
            electrical_param_evidence_errors.inc()
            return prior

        if value < 0:
            logger.warning(f"点位值为负数: value={value}，返回先验概率 {prior}")
            electrical_param_evidence_errors.inc()
            return prior

        if threshold == 0:
            logger.warning(f"阈值为 0，无法计算偏离度，返回先验概率 {prior}")
            electrical_param_evidence_errors.inc()
            return prior

        if not math.isfinite(threshold) or threshold < 0:
            logger.error(f"阈值非法: threshold={threshold}，返回先验概率 {prior}")
            electrical_param_evidence_errors.inc()
            return prior

        # 计算偏离度（归一化）
        if threshold_type == "ABOVE":
            deviation = (value - threshold) / threshold  # 超过阈值为正
        elif threshold_type == "BELOW":
            deviation = (threshold - value) / threshold  # 低于阈值为正
        else:
            logger.error(f"未知的 threshold_type: {threshold_type}，返回先验概率")
            electrical_param_evidence_errors.inc()
            return prior

        # Sigmoid 映射: P = 1 / (1 + exp(-k * deviation))
        try:
            probability = 1.0 / (1.0 + math.exp(-sigmoid_k * deviation))
        except OverflowError:
            # 处理极端情况（deviation 过大导致 exp 溢出）
            probability = 1.0 if deviation > 0 else 0.0
            logger.warning(f"Sigmoid 计算溢出: deviation={deviation}, 使用边界值 {probability}")

        # 限制在 [0, 1] 范围内
        return max(0.0, min(1.0, probability))
```

### 文件结构

```
backend/app/models/
└── diagnosis.py                          # 已有：扩展 FaultTreeNode 模型

backend/app/schemas/
└── diagnosis.py                          # 已有：扩展 FaultTreeNodeSchema

backend/app/services/diagnosis/
├── l2_inference_engine.py                # 已有：扩展证据收集逻辑
└── evidence_calculator.py                # 新建：证据概率计算函数

backend/app/api/v1/
└── fault_tree.py                         # 已有：扩展 CRUD API

backend/alembic/versions/
└── 20260307_1430_add_electrical_param_fields.py   # 新建：数据库迁移

backend/tests/services/
└── test_electrical_param_evidence.py     # 新建：单元测试
```

### API 端点示例

**认证与权限:**
- 所有 API 端点需要 JWT 认证（Header: `Authorization: Bearer <token>`）
- RBAC 权限要求: admin/operator 可创建/修改节点，viewer 仅可查询
- 速率限制: 100 req/min per user（由 FastAPI middleware 实现）

**创建电气参数故障树节点:**

```http
POST /api/v1/fault-tree/nodes
Content-Type: application/json
Authorization: Bearer <jwt_token>

{
  "tree_id": 1,
  "node_type": "LEAF",
  "point_id": 100,
  "threshold_type": "ABOVE",
  "threshold_value": 10.0,
  "sigmoid_k": 2.0,
  "prior_probability": 0.5,
  "description": "三相不平衡度检测节点"
}
```

**响应示例:**

```json
{
  "id": 123,
  "tree_id": 1,
  "node_type": "LEAF",
  "point_id": 100,
  "threshold_type": "ABOVE",
  "threshold_value": 10.0,
  "sigmoid_k": 2.0,
  "prior_probability": 0.5,
  "description": "三相不平衡度检测节点",
  "created_at": "2026-03-07T14:30:00Z"
}
```

**更新节点阈值:**

```http
PUT /api/v1/fault-tree/nodes/123
Content-Type: application/json
Authorization: Bearer <jwt_token>

{
  "threshold_value": 12.0,
  "sigmoid_k": 3.0
}
```

**验证错误示例:**

```http
POST /api/v1/fault-tree/nodes
Content-Type: application/json
Authorization: Bearer <jwt_token>

{
  "tree_id": 1,
  "node_type": "LEAF",
  "point_id": 100,
  "threshold_type": "ABOVE",
  "threshold_value": -5.0,  # 非法：负数
  "sigmoid_k": 0.0          # 非法：必须 > 0
}
```

**错误响应:**

```json
{
  "detail": [
    {
      "loc": ["body", "threshold_value"],
      "msg": "threshold_value must be between 0 and 1000",
      "type": "value_error"
    },
    {
      "loc": ["body", "sigmoid_k"],
      "msg": "sigmoid_k must be between 0.1 and 10.0",
      "type": "value_error"
    }
  ]
}
```

**权限错误示例 (viewer 尝试创建节点):**

```json
{
  "detail": "Insufficient permissions. Required: admin or operator"
}
```

### 测试要求

**单元测试 (`backend/tests/services/test_electrical_param_evidence.py`):**

```python
import pytest
from app.services.diagnosis.evidence_calculator import calc_evidence_probability
from app.models.diagnosis import FaultTreeNode
from app.models import Point
from unittest.mock import AsyncMock, patch
import math

def test_sigmoid_above_threshold():
    """测试 ABOVE 类型阈值（三相不平衡度）"""
    # 超过阈值 20%
    prob = calc_evidence_probability(12.0, 10.0, "ABOVE", sigmoid_k=2.0)
    assert prob > 0.5  # 异常概率应大于 0.5
    assert 0.7 < prob < 0.8  # 预期约 0.73

    # 低于阈值 10%
    prob = calc_evidence_probability(9.0, 10.0, "ABOVE", sigmoid_k=2.0)
    assert prob < 0.5  # 正常概率应小于 0.5

def test_sigmoid_below_threshold():
    """测试 BELOW 类型阈值（功率因数）"""
    # 低于阈值（0.85 < 0.9）
    prob = calc_evidence_probability(0.85, 0.9, "BELOW", sigmoid_k=2.0)
    assert prob > 0.5  # 异常概率应大于 0.5

    # 高于阈值（0.95 > 0.9）
    prob = calc_evidence_probability(0.95, 0.9, "BELOW", sigmoid_k=2.0)
    assert prob < 0.5  # 正常概率应小于 0.5

def test_sigmoid_k_parameter():
    """测试斜率参数影响"""
    # 斜率越大，曲线越陡峭
    prob_k2 = calc_evidence_probability(12.0, 10.0, "ABOVE", sigmoid_k=2.0)
    prob_k5 = calc_evidence_probability(12.0, 10.0, "ABOVE", sigmoid_k=5.0)

    # k=5 时曲线更陡，相同偏离度下概率更接近 1
    assert prob_k5 > prob_k2

def test_edge_cases():
    """测试边界情况"""
    # 阈值为 0
    prob = calc_evidence_probability(10.0, 0.0, "ABOVE", sigmoid_k=2.0)
    assert prob == 0.5  # 返回先验概率

    # 极端偏离（防止溢出）
    prob = calc_evidence_probability(1000.0, 10.0, "ABOVE", sigmoid_k=2.0)
    assert prob == 1.0  # 应限制在 1.0

    # 负数点位值
    prob = calc_evidence_probability(-5.0, 10.0, "ABOVE", sigmoid_k=2.0)
    assert prob == 0.5  # 返回先验概率

    # NaN 点位值
    prob = calc_evidence_probability(float('nan'), 10.0, "ABOVE", sigmoid_k=2.0)
    assert prob == 0.5  # 返回先验概率

    # Infinity 点位值
    prob = calc_evidence_probability(float('inf'), 10.0, "ABOVE", sigmoid_k=2.0)
    assert prob == 0.5  # 返回先验概率

    # 未知 threshold_type
    prob = calc_evidence_probability(12.0, 10.0, "UNKNOWN", sigmoid_k=2.0)
    assert prob == 0.5  # 返回先验概率

@pytest.mark.asyncio
async def test_electrical_param_integration():
    """测试电气参数集成到 L2 推理流程（完整 mock 实现）"""
    from app.services.diagnosis.l2_inference_engine import collect_leaf_evidence

    # 创建测试故障树节点（三相不平衡度）
    node = FaultTreeNode(
        id=1,
        tree_id=1,
        node_type="LEAF",
        point_id=100,
        threshold_type="ABOVE",
        threshold_value=10.0,
        sigmoid_k=2.0,
        prior_probability=0.5
    )

    # Mock get_point_latest_value 返回 12%（超过阈值）
    with patch('app.services.diagnosis.l2_inference_engine.get_point_latest_value',
               new_callable=AsyncMock) as mock_get_value:
        mock_get_value.return_value = 12.0

        # Mock get_point_by_id 返回 Point 对象
        mock_point = Point(id=100, point_type="PHASE_IMBALANCE", point_name="三相不平衡度")
        with patch('app.services.diagnosis.l2_inference_engine.get_point_by_id',
                   new_callable=AsyncMock) as mock_get_point:
            mock_get_point.return_value = mock_point

            # 执行证据收集
            probability = await collect_leaf_evidence(node, time_window=300)

            # 验证结果
            assert probability > 0.5  # 异常概率应大于 0.5
            assert 0.7 < probability < 0.8  # 预期约 0.73

            # 验证 mock 调用
            mock_get_value.assert_called_once_with(100, 300)
            mock_get_point.assert_called_once_with(100)

@pytest.mark.asyncio
async def test_electrical_param_default_threshold():
    """测试使用默认阈值"""
    from app.services.diagnosis.l2_inference_engine import collect_leaf_evidence

    # 创建节点，不配置阈值（使用默认值）
    node = FaultTreeNode(
        id=2,
        tree_id=1,
        node_type="LEAF",
        point_id=101,
        threshold_type=None,  # 未配置
        threshold_value=None,  # 未配置
        sigmoid_k=None,  # 使用默认 2.0
        prior_probability=0.5
    )

    with patch('app.services.diagnosis.l2_inference_engine.get_point_latest_value',
               new_callable=AsyncMock) as mock_get_value:
        mock_get_value.return_value = 6.0  # THD 6% (默认阈值 5%)

        mock_point = Point(id=101, point_type="THD", point_name="谐波畸变率")
        with patch('app.services.diagnosis.l2_inference_engine.get_point_by_id',
                   new_callable=AsyncMock) as mock_get_point:
            mock_get_point.return_value = mock_point

            probability = await collect_leaf_evidence(node, time_window=300)

            # 应使用默认阈值 5%，6% 超过阈值
            assert probability > 0.5

@pytest.mark.asyncio
async def test_electrical_param_no_data():
    """测试点位无数据情况"""
    from app.services.diagnosis.l2_inference_engine import collect_leaf_evidence

    node = FaultTreeNode(
        id=3,
        tree_id=1,
        node_type="LEAF",
        point_id=102,
        threshold_type="ABOVE",
        threshold_value=10.0,
        sigmoid_k=2.0,
        prior_probability=0.3
    )

    # Mock 返回 None（无数据）
    with patch('app.services.diagnosis.l2_inference_engine.get_point_latest_value',
               new_callable=AsyncMock) as mock_get_value:
        mock_get_value.return_value = None

        probability = await collect_leaf_evidence(node, time_window=300)

        # 应返回先验概率
        assert probability == 0.3

@pytest.mark.asyncio
async def test_concurrent_evidence_calculation():
    """测试并发证据计算（模拟多个诊断任务同时运行）"""
    from app.services.diagnosis.l2_inference_engine import collect_leaf_evidence
    import asyncio

    # 创建多个节点
    nodes = [
        FaultTreeNode(
            id=i,
            tree_id=1,
            node_type="LEAF",
            point_id=100 + i,
            threshold_type="ABOVE",
            threshold_value=10.0,
            sigmoid_k=2.0,
            prior_probability=0.5
        )
        for i in range(10)
    ]

    # Mock 返回不同的点位值
    with patch('app.services.diagnosis.l2_inference_engine.get_point_latest_value',
               new_callable=AsyncMock) as mock_get_value:
        mock_get_value.side_effect = lambda point_id, _: float(point_id % 20)

        with patch('app.services.diagnosis.l2_inference_engine.get_point_by_id',
                   new_callable=AsyncMock) as mock_get_point:
            mock_get_point.side_effect = lambda point_id: Point(
                id=point_id,
                point_type="PHASE_IMBALANCE",
                point_name=f"Point-{point_id}"
            )

            # 并发执行证据收集
            tasks = [collect_leaf_evidence(node, time_window=300) for node in nodes]
            results = await asyncio.gather(*tasks)

            # 验证所有结果都有效
            assert len(results) == 10
            assert all(0 <= prob <= 1 for prob in results)
```
    with patch('app.services.diagnosis.l2_inference_engine.get_point_latest_value',
               new_callable=AsyncMock) as mock_get_value:
        mock_get_value.return_value = None

        probability = await collect_leaf_evidence(node, time_window=300)

        # 应返回先验概率
        assert probability == 0.3

def test_prometheus_metrics():
    """测试 Prometheus 指标记录"""
    from app.services.diagnosis.evidence_calculator import (
        electrical_param_evidence_total,
        electrical_param_evidence_errors
    )

    # 记录前的计数
    initial_total = electrical_param_evidence_total.labels(point_type="PHASE_IMBALANCE")._value.get()
    initial_errors = electrical_param_evidence_errors._value.get()

    # 正常计算
    calc_evidence_probability(12.0, 10.0, "ABOVE", sigmoid_k=2.0)

    # 异常计算（触发错误）
    calc_evidence_probability(float('nan'), 10.0, "ABOVE", sigmoid_k=2.0)

    # 验证指标增加（注意：实际测试中需要重置指标或使用独立的测试环境）
    # 这里仅作示例，实际测试需要更复杂的 mock 或测试隔离
```

### 依赖关系

**前置依赖:**
- Epic 24 (Story 24.1-24.5): 诊断引擎核心框架，L2 推理引擎，sigmoid 映射函数
- Epic 24 (Story 24.3): 故障树数据模型和 CRUD API

**后续依赖:**
- Story 25.3: UPS 电池 SOH 预测（可能使用电气参数作为输入）
- Story 25.5: 传感器元数据与精度加权（需要与电气参数证据结合）

### 关键注意事项

1. **验证 Story 24.5 实现**: 首先检查 `backend/app/services/diagnosis/evidence_calculator.py` 是否已存在 sigmoid 映射函数，如存在则导入复用，否则新建实现
2. **阈值配置灵活性**: 支持节点级别自定义阈值，同时提供默认值（ELECTRICAL_PARAM_DEFAULTS）
3. **类型安全**: 使用 Pydantic 枚举验证 `threshold_type`，使用 Field 约束验证数值范围
4. **边界处理**: 阈值为 0、极端偏离值、NaN、Infinity、负数等边界情况需要妥善处理并返回先验概率
5. **日志记录**: 电气参数证据收集过程需详细记录（点位值、阈值、概率），错误情况需记录 ERROR 级别日志
6. **向后兼容**: 新增字段为 nullable，不影响现有故障树节点；非电气参数类型使用原有逻辑
7. **测试覆盖**: 包含 sigmoid 函数测试、阈值类型测试、边界测试、集成测试、Prometheus 指标测试
8. **Prometheus 监控**: 添加 3 个监控指标（duration, total, errors），复用 Story 25.1 的成功模式
9. **辅助函数实现**: `get_point_latest_value()` 和 `get_point_by_id()` 需要完整实现，包含 Redis 降级和错误处理
10. **数据迁移安全**: Alembic 迁移脚本需检查表/列存在性，downgrade 需要安全回滚逻辑
11. **API 文档完整**: 提供完整的 API 请求/响应示例，包含验证错误示例
12. **单一数据源**: 默认值统一在 ELECTRICAL_PARAM_DEFAULTS 定义，避免多处定义导致不一致

### Previous Story Intelligence (Story 25.1)

**成功模式:**
- 使用 NetworkX 库构建图数据结构，性能良好
- Copy-on-write 模式确保并发安全，使用 `copy.deepcopy()` 深拷贝
- Prometheus 监控指标提供可观测性
- Redis 连接错误处理和降级策略（定期重建）
- 单元测试覆盖全面（6 个测试，包含并发测试）

**需要注意的问题:**
- 模型字段名称需要与数据库表一致（如 `transformer_name` 而非 `name`）
- Redis 客户端需要在 finally 块中正确关闭
- 类型提示需要完整（如 `-> None`）
- 依赖库需要在 requirements.txt 中明确声明版本范围

**代码审查修复经验:**
- 添加缺失的依赖声明（redis>=5.0.0, prometheus-client>=0.16.0）
- 实现监控指标（5 个 Prometheus 指标）
- 改进错误处理（Redis 客户端关闭）
- 添加类型提示

**文件修改模式:**
- 服务层代码: `backend/app/services/diagnosis/`
- API 层代码: `backend/app/api/v1/`
- 测试代码: `backend/tests/services/`
- 数据库迁移: `backend/alembic/versions/`
- 依赖声明: `backend/requirements.txt`

### Project Structure Notes

- 遵循棕地项目约定：表名复数形式（`fault_tree_nodes`）
- 服务层代码放在 `backend/app/services/diagnosis/`
- 使用 SQLAlchemy 2.0 异步模式
- 使用 `async_session` (auto-commit) 而非 `get_db` (manual commit)
- Alembic 迁移脚本命名: `xxxx_add_electrical_param_fields.py`
- 测试文件命名: `test_electrical_param_evidence.py`

### References

- [Source: _bmad-output/planning-artifacts/epics.md#Epic 25 Story 25.2]
- [Source: _bmad-output/planning-artifacts/architecture.md#18.7 电气专业参数扩展架构]
- [Source: _bmad-output/implementation-artifacts/25-1-power-topology-cascade-analysis.md#Dev Notes]
- [Source: docs/project-knowledge/backend-architecture.md#数据库模型]
- [Source: docs/project-knowledge/project-context.md#Python Async Database Pattern]

## Dev Agent Record

### Agent Model Used

Claude Opus 4.6 (claude-opus-4-6)

### Debug Log References

### Completion Notes List

### File List
