"""Story 39.1 single-maintainer evidence governance tests."""

from copy import deepcopy
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]
SPEC = spec_from_file_location(
    "story_39_1_governance",
    ROOT / "scripts" / "story_39_1_governance.py",
)
assert SPEC and SPEC.loader
GOVERNANCE = module_from_spec(SPEC)
SPEC.loader.exec_module(GOVERNANCE)


@pytest.fixture
def verified_manifest():
    return {
        "governance": {
            "mode": "single-maintainer",
            "maintainer": "proecheng",
            "independent_approval_required": False,
            "decision": "VERIFIED",
        },
        "story_gate": {"status": "PASS", "blockers": []},
        "epic_production_gate": {
            "status": "BLOCKED",
            "blockers": ["Other Epic 39 Stories remain incomplete."],
        },
    }


def test_verified_single_maintainer_story_can_pass(verified_manifest):
    GOVERNANCE.validate_governance(verified_manifest)


def test_legacy_virtual_role_approvals_are_rejected(verified_manifest):
    manifest = deepcopy(verified_manifest)
    manifest["approvals"] = {"security": {"name": "Charlie"}}

    with pytest.raises(ValueError, match="不得包含虚拟角色审批"):
        GOVERNANCE.validate_governance(manifest)


def test_governance_decision_must_match_story_gate(verified_manifest):
    manifest = deepcopy(verified_manifest)
    manifest["governance"]["decision"] = "BLOCKED"

    with pytest.raises(ValueError, match="治理验证结论与 Story 门禁状态不一致"):
        GOVERNANCE.validate_governance(manifest)


def test_story_cannot_unblock_epic_production_gate(verified_manifest):
    manifest = deepcopy(verified_manifest)
    manifest["epic_production_gate"]["status"] = "APPROVED"

    with pytest.raises(ValueError, match="不得解除 Epic 39 总体生产门禁"):
        GOVERNANCE.validate_governance(manifest)
