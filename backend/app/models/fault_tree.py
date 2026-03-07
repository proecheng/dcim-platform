"""
故障树数据模型 - Story 24.3
"""
from sqlalchemy import Column, Integer, String, Text, Float, ForeignKey, TIMESTAMP, CheckConstraint, func
from sqlalchemy.orm import relationship
from app.core.database import Base


class FaultTree(Base):
    """故障树元数据"""
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
    versions = relationship("FaultTreeVersion", back_populates="tree", cascade="all, delete-orphan")


class FaultTreeNode(Base):
    """故障树节点"""
    __tablename__ = "fault_tree_nodes"

    id = Column(Integer, primary_key=True, index=True)
    tree_id = Column(Integer, ForeignKey("fault_trees.id", ondelete="CASCADE"), nullable=False, index=True)
    node_type = Column(String(20), nullable=False, index=True)
    gate_type = Column(String(10))
    name = Column(String(200), nullable=False)
    description = Column(Text)
    prior_probability = Column(Float, nullable=False, default=0.5, server_default="0.5")
    evidence_point_id = Column(Integer, ForeignKey("points.id", ondelete="RESTRICT"))
    config = Column(Text)  # SQLite 兼容：使用 Text 存储 JSON

    # Story 25.2: 电气参数阈值配置
    threshold_type = Column(String(10), nullable=True)  # 'ABOVE' or 'BELOW'
    threshold_value = Column(Float, nullable=True)
    sigmoid_k = Column(Float, nullable=True, default=2.0)

    created_at = Column(TIMESTAMP, nullable=False, server_default=func.now())

    __table_args__ = (
        CheckConstraint("prior_probability >= 0.0 AND prior_probability <= 1.0", name="check_prior_probability"),
    )

    tree = relationship("FaultTree", back_populates="nodes")
    parent_edges = relationship("FaultTreeEdge", foreign_keys="FaultTreeEdge.child_node_id", back_populates="child_node")
    child_edges = relationship("FaultTreeEdge", foreign_keys="FaultTreeEdge.parent_node_id", back_populates="parent_node")


class FaultTreeEdge(Base):
    """故障树边"""
    __tablename__ = "fault_tree_edges"

    id = Column(Integer, primary_key=True, index=True)
    tree_id = Column(Integer, ForeignKey("fault_trees.id", ondelete="CASCADE"), nullable=False, index=True)
    parent_node_id = Column(Integer, ForeignKey("fault_tree_nodes.id", ondelete="CASCADE"), nullable=False, index=True)
    child_node_id = Column(Integer, ForeignKey("fault_tree_nodes.id", ondelete="CASCADE"), nullable=False, index=True)
    created_at = Column(TIMESTAMP, nullable=False, server_default=func.now())

    __table_args__ = (
        CheckConstraint("parent_node_id != child_node_id", name="check_no_self_loop"),
    )

    tree = relationship("FaultTree", back_populates="edges")
    parent_node = relationship("FaultTreeNode", foreign_keys=[parent_node_id], back_populates="child_edges")
    child_node = relationship("FaultTreeNode", foreign_keys=[child_node_id], back_populates="parent_edges")


class FaultTreeDeviceMapping(Base):
    """故障树设备映射"""
    __tablename__ = "fault_tree_device_mapping"

    id = Column(Integer, primary_key=True, index=True)
    tree_id = Column(Integer, ForeignKey("fault_trees.id", ondelete="CASCADE"), nullable=False)
    device_type = Column(String(50), nullable=False, index=True)
    alarm_type = Column(String(100), index=True)
    priority = Column(Integer, nullable=False, default=0)
    created_at = Column(TIMESTAMP, nullable=False, server_default=func.now())

    tree = relationship("FaultTree", back_populates="device_mappings")


class FaultTreeVersion(Base):
    """故障树版本"""
    __tablename__ = "fault_tree_versions"

    id = Column(Integer, primary_key=True, index=True)
    tree_id = Column(Integer, ForeignKey("fault_trees.id", ondelete="CASCADE"), nullable=False, index=True)
    version_number = Column(Integer, nullable=False)
    status = Column(String(20), nullable=False, default="draft", index=True)
    snapshot = Column(Text, nullable=False)
    hmac_signature = Column(String(64))
    created_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(TIMESTAMP, nullable=False, server_default=func.now())
    reviewed_by = Column(Integer, ForeignKey("users.id"))
    reviewed_at = Column(TIMESTAMP)
    activated_at = Column(TIMESTAMP)

    __table_args__ = (
        CheckConstraint("status IN ('draft', 'reviewed', 'active', 'archived')", name="check_status"),
        CheckConstraint("version_number > 0", name="check_version_number_positive"),
    )

    tree = relationship("FaultTree", back_populates="versions")
