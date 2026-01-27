"""
日志模型
"""
from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey

from ..core.database import Base


class OperationLog(Base):
    """操作日志表"""
    __tablename__ = "operation_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), comment="用户ID")
    username = Column(String(50), comment="用户名")
    module = Column(String(50), nullable=False, comment="模块: user/point/alarm/config/report")
    action = Column(String(50), nullable=False, comment="操作: create/update/delete/query/export")
    target_type = Column(String(50), comment="目标类型: point/alarm/threshold/user")
    target_id = Column(Integer, comment="目标ID")
    target_name = Column(String(100), comment="目标名称")
    old_value = Column(Text, comment="旧值(JSON)")
    new_value = Column(Text, comment="新值(JSON)")
    ip_address = Column(String(50), comment="IP地址")
    user_agent = Column(String(255), comment="用户代理")
    request_url = Column(String(255), comment="请求URL")
    request_method = Column(String(10), comment="请求方法")
    request_params = Column(Text, comment="请求参数")
    response_code = Column(Integer, comment="响应码")
    response_time_ms = Column(Integer, comment="响应时间(毫秒)")
    remark = Column(Text, comment="备注")
    created_at = Column(DateTime, default=datetime.now, comment="创建时间")


class SystemLog(Base):
    """系统日志表"""
    __tablename__ = "system_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    log_level = Column(String(20), nullable=False, comment="日志级别: DEBUG/INFO/WARN/ERROR/FATAL")
    module = Column(String(50), comment="模块名")
    message = Column(Text, nullable=False, comment="日志消息")
    exception = Column(Text, comment="异常信息")
    stack_trace = Column(Text, comment="堆栈跟踪")
    created_at = Column(DateTime, default=datetime.now, comment="创建时间")


class CommunicationLog(Base):
    """通讯日志表"""
    __tablename__ = "communication_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    device_id = Column(Integer, comment="设备ID")
    comm_type = Column(String(20), comment="通讯类型: request/response/error")
    protocol = Column(String(20), comment="协议: modbus/snmp/mqtt")
    request_data = Column(Text, comment="请求数据")
    response_data = Column(Text, comment="响应数据")
    status = Column(String(20), comment="状态: success/failed/timeout")
    error_message = Column(Text, comment="错误信息")
    duration_ms = Column(Integer, comment="耗时(毫秒)")
    created_at = Column(DateTime, default=datetime.now, comment="创建时间")
