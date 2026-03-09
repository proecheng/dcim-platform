from sqlalchemy import Column, Integer, String, ForeignKey, TIMESTAMP, CheckConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship
from app.core.database import Base
from datetime import datetime


class ABTestConfig(Base):
    """A/B 测试配置模型"""
    __tablename__ = "ab_test_configs"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    fault_tree_id = Column(Integer, ForeignKey("fault_trees.id"), nullable=False)
    version_a_id = Column(Integer, ForeignKey("fault_tree_versions.id"), nullable=False)
    version_b_id = Column(Integer, ForeignKey("fault_tree_versions.id"), nullable=False)
    strategy = Column(String(50), nullable=False)  # hash/device_type/site/percentage
    strategy_params = Column(JSONB)
    status = Column(String(20), nullable=False, default="active")  # active/paused/completed
    version = Column(Integer, nullable=False, default=1)  # 乐观锁版本号
    min_duration_hours = Column(Integer, nullable=False, default=168)  # 最小运行时长（小时）
    min_sample_size = Column(Integer, nullable=False, default=100)  # 最小样本量
    created_by = Column(Integer, ForeignKey("users.id"))
    created_at = Column(TIMESTAMP, nullable=False, default=datetime.utcnow)
    updated_at = Column(TIMESTAMP, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    completed_at = Column(TIMESTAMP)

    # Relationships
    fault_tree = relationship("FaultTree", back_populates="ab_tests")
    version_a = relationship("FaultTreeVersion", foreign_keys=[version_a_id])
    version_b = relationship("FaultTreeVersion", foreign_keys=[version_b_id])
    creator = relationship("User")

    __table_args__ = (
        CheckConstraint("status IN ('active', 'paused', 'completed')", name="check_ab_test_status"),
        CheckConstraint("version_a_id != version_b_id", name="check_version_different"),
    )


class ABTestDeviceAssignment(Base):
    """A/B 测试设备版本分配记录"""
    __tablename__ = "ab_test_device_assignments"

    id = Column(Integer, primary_key=True, index=True)
    ab_test_id = Column(Integer, ForeignKey("ab_test_configs.id", ondelete="CASCADE"), nullable=False)
    device_id = Column(String(255), nullable=False)
    assigned_version_id = Column(Integer, ForeignKey("fault_tree_versions.id"), nullable=False)
    assigned_at = Column(TIMESTAMP, nullable=False, default=datetime.utcnow)

    # Relationships
    ab_test = relationship("ABTestConfig")
    assigned_version = relationship("FaultTreeVersion")


class ABTestArchive(Base):
    """A/B 测试归档数据"""
    __tablename__ = "ab_test_archives"

    id = Column(Integer, primary_key=True, index=True)
    ab_test_id = Column(Integer, ForeignKey("ab_test_configs.id"), nullable=False)
    version_a_stats = Column(JSONB, nullable=False)
    version_b_stats = Column(JSONB, nullable=False)
    statistical_test_result = Column(JSONB, nullable=False)
    decision = Column(String(50), nullable=False)
    archived_at = Column(TIMESTAMP, nullable=False, default=datetime.utcnow)
    archived_by = Column(Integer, ForeignKey("users.id"))

    # Relationships
    ab_test = relationship("ABTestConfig")
    archiver = relationship("User")
