"""边缘推理 Stub 实现 — 记录调用日志，返回"未实现"状态。

用于系统集成测试和未来开发时的占位验证。
"""

import logging
from typing import Any

from .edge_diagnosis_handler import EdgeDiagnosisHandler

logger = logging.getLogger(__name__)


class EdgeDiagnosisStub(EdgeDiagnosisHandler):
    """Stub 实现：所有方法记录日志并返回未实现状态。"""

    async def connect(self, gateway_id: str, mqtt_broker: str) -> bool:
        logger.info(f"[EdgeStub] connect called: gateway={gateway_id}, broker={mqtt_broker} — 未实现")
        return False

    async def receive_rules(self, gateway_id: str) -> list[dict]:
        logger.info(f"[EdgeStub] receive_rules called: gateway={gateway_id} — 未实现")
        return []

    async def execute_l1(self, rules: list[dict], evidence: dict[str, Any]) -> dict:
        logger.info(f"[EdgeStub] execute_l1 called: {len(rules)} rules — 未实现")
        return {"status": "not_implemented", "message": "边缘推理尚未实现"}

    async def report_result(self, gateway_id: str, result: dict) -> bool:
        logger.info(f"[EdgeStub] report_result called: gateway={gateway_id} — 未实现")
        return False
