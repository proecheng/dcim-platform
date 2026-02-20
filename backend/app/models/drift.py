"""
传感器数据漂移检测模型
Story 9-7: 传感器数据漂移检测
"""

from datetime import datetime
from sqlalchemy import Column, Integer, Float, String, DateTime, Text, ForeignKey

from ..core.database import Base


class DriftDetectionResult(Base):
    """漂移检测结果表"""

    __tablename__ = "drift_detection_results"

    id = Column(Integer, primary_key=True, autoincrement=True)
    point_id = Column(Integer, ForeignKey("points.id"), nullable=False, comment="点位ID")
    point_code = Column(String(50), nullable=False, comment="点位编码")
    point_name = Column(String(100), nullable=False, comment="点位名称")
    area_code = Column(String(10), nullable=True, comment="区域代码")
    status = Column(String(20), nullable=False, comment="状态: suspected/confirmed/resolved")
    mean_value = Column(Float, nullable=False, comment="检测期间均值")
    std_value = Column(Float, nullable=False, comment="检测期间标准差")
    current_value = Column(Float, nullable=False, comment="当前值")
    deviation_sigma = Column(Float, nullable=False, comment="偏差倍数(σ)")
    cross_validation_result = Column(String(20), nullable=True, comment="交叉验证结果: pass/fail/skipped")
    diagnosis = Column(Text, nullable=False, comment="诊断建议")
    detected_at = Column(DateTime, default=datetime.now, comment="检测时间")
    resolved_at = Column(DateTime, nullable=True, comment="解除时间")
    created_at = Column(DateTime, default=datetime.now, comment="记录创建时间")
