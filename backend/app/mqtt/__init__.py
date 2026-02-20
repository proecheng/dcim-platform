"""MQTT 通信层"""

from .client import MqttService

# 全局 MQTT 服务实例
mqtt_service = MqttService()
