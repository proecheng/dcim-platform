"""Story 39.2 single-maintainer governance invariants."""

from __future__ import annotations

from typing import Any


def validate_governance(manifest: dict[str, Any]) -> None:
    if "approvals" in manifest:
        raise ValueError("单维护者证据清单不得包含审批记录")

    governance = manifest["governance"]
    if (
        governance.get("mode") != "single-maintainer"
        or governance.get("maintainer") != "proecheng"
        or governance.get("independent_approval_required") is not False
    ):
        raise ValueError("Story 39.2 治理字段不符合单维护者契约")

    story_gate = manifest["story_gate"]
    expected_decision = "VERIFIED" if story_gate["status"] == "PASS" else "BLOCKED"
    if governance["decision"] != expected_decision:
        raise ValueError("治理验证结论与 Story 门禁状态不一致")
    if story_gate["status"] == "PASS" and story_gate["blockers"]:
        raise ValueError("Story 门禁通过时不能保留 blocker")
    if story_gate["status"] == "BLOCKED" and not story_gate["blockers"]:
        raise ValueError("Story 门禁阻塞时必须列出 blocker")

    epic_gate = manifest["epic_production_gate"]
    if epic_gate["status"] != "BLOCKED" or not epic_gate["blockers"]:
        raise ValueError("Story 39.2 不得解除 Epic 39 总体生产门禁")
