"""边缘推理预留接口 — 愿景阶段，仅定义抽象接口不实现具体逻辑。

Architecture Reference: Section 18.13 边缘推理架构（FR34-33~34）
- 网关层预留 diagnosis_handler 接口
- 协议: 中心节点通过 MQTT 下发规则子集到边缘
- 边缘执行 L1 规则匹配，复杂场景上报中心
- 多节点一致性: 中心节点作为仲裁者
"""

from abc import ABC, abstractmethod
from typing import Any

# 预留 MQTT Topic 模板
EDGE_DIAGNOSIS_TOPICS = {
    "rules_push": "dcim/diagnosis/rules/{gateway_id}",
    "results_report": "dcim/diagnosis/results/{gateway_id}",
}


class EdgeDiagnosisHandler(ABC):
    """边缘诊断处理器抽象接口。

    未来实现时，网关端实例化此接口的具体实现类，
    通过 MQTT 接收中心节点下发的 L1 规则子集并本地执行。
    """

    @abstractmethod
    async def connect(self, gateway_id: str, mqtt_broker: str) -> bool:
        """连接到中心节点的 MQTT broker，订阅规则下发 topic。"""
        ...

    @abstractmethod
    async def receive_rules(self, gateway_id: str) -> list[dict]:
        """接收中心节点下发的 L1 规则子集。"""
        ...

    @abstractmethod
    async def execute_l1(self, rules: list[dict], evidence: dict[str, Any]) -> dict:
        """在边缘端执行 L1 规则匹配。"""
        ...

    @abstractmethod
    async def report_result(self, gateway_id: str, result: dict) -> bool:
        """将诊断结果上报中心节点。"""
        ...


def get_edge_diagnosis_config() -> dict:
    """返回边缘推理预留配置（用于 API 查询和未来集成）。"""
    return {
        "enabled": False,
        "status": "reserved",
        "description": "边缘推理接口预留，愿景阶段，待 FR34-33/34 实现",
        "mqtt_topics": EDGE_DIAGNOSIS_TOPICS,
        "supported_levels": ["L1"],
        "arbitration": "center_node",
    }
