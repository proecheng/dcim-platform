"""Story 39.1 single-maintainer governance invariants."""

from __future__ import annotations

from typing import Any


def validate_governance(manifest: dict[str, Any]) -> None:
    if "approvals" in manifest:
        raise ValueError("单维护者证据清单不得包含虚拟角色审批")

    governance = manifest["governance"]
    story_gate = manifest["story_gate"]
    expected_decision = "VERIFIED" if story_gate["status"] == "PASS" else "BLOCKED"
    if governance["decision"] != expected_decision:
        raise ValueError("治理验证结论与 Story 门禁状态不一致")
    if story_gate["status"] == "PASS" and story_gate["blockers"]:
        raise ValueError("Story 门禁通过时不能保留 Story blocker")
    if story_gate["status"] == "BLOCKED" and not story_gate["blockers"]:
        raise ValueError("Story 门禁阻塞时必须列出 blocker")
    if manifest["epic_production_gate"]["status"] != "BLOCKED":
        raise ValueError("Story 39.1 不得解除 Epic 39 总体生产门禁")
