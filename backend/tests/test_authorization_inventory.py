"""Story 39.1 authorization inventory gate tests."""

from copy import deepcopy

import pytest

from app.core.authorization import (
    AuthorizationInventoryError,
    build_authorization_inventory,
    discover_broadcast_producers,
    load_authorization_inventory,
    validate_authorization_inventory,
)
from app.main import app


@pytest.fixture(scope="module")
def inventory():
    return load_authorization_inventory()


def _assert_invalid(inventory, expected: str) -> None:
    with pytest.raises(AuthorizationInventoryError) as exc_info:
        validate_authorization_inventory(app, inventory=inventory)
    assert expected in str(exc_info.value)


def test_checked_in_inventory_matches_runtime_surface(inventory):
    result = validate_authorization_inventory(app, inventory=inventory)

    assert result.http_count >= 850
    assert result.websocket_count == 3
    assert result.channel_count == 5
    assert result.producer_count == len(discover_broadcast_producers())


def test_candidate_builder_preserves_reviewed_http_classifications(inventory):
    candidate = build_authorization_inventory(app)
    reviewed_by_key = {item["key"]: item for item in inventory["http"]}

    for item in candidate["http"]:
        reviewed = reviewed_by_key[item["key"]]
        assert {
            "access": item["access"],
            "roles": item["roles"],
            "resolver": item["resolver"],
        } == {
            "access": reviewed["access"],
            "roles": reviewed["roles"],
            "resolver": reviewed["resolver"],
        }, item["key"]


@pytest.mark.parametrize(
    ("key", "expected_roles"),
    [
        (
            "GET /api/v1/energy/shift/plans::get_plans",
            ["admin", "operator", "viewer"],
        ),
        (
            "POST /api/v1/energy/shift/plans::create_plan",
            ["admin", "operator"],
        ),
        (
            "POST /api/v1/energy/shift/analysis/feasibility::analyze_feasibility",
            ["admin", "operator", "viewer"],
        ),
        (
            "GET /api/v1/opportunities::list_opportunities",
            ["admin", "operator", "viewer"],
        ),
        (
            "POST /api/v1/opportunities/{opportunity_id}/simulate::simulate_opportunity",
            ["admin", "operator", "viewer"],
        ),
        (
            "GET /api/v1/diagnosis/probability-tuning/adjustments::list_adjustments",
            ["admin", "operator", "viewer"],
        ),
    ],
)
def test_candidate_builder_preserves_inclusive_global_roles(key, expected_roles):
    candidate = build_authorization_inventory(app)
    policies = {item["key"]: item for item in candidate["http"]}

    assert policies[key]["access"] == "GLOBAL"
    assert policies[key]["roles"] == expected_roles


def test_missing_runtime_route_is_rejected(inventory):
    mutated = deepcopy(inventory)
    mutated["http"].pop()
    _assert_invalid(mutated, "missing HTTP policies")


def test_duplicate_policy_key_is_rejected(inventory):
    mutated = deepcopy(inventory)
    mutated["http"].append(deepcopy(mutated["http"][0]))
    _assert_invalid(mutated, "duplicate HTTP policy keys")


def test_unknown_access_type_is_rejected(inventory):
    mutated = deepcopy(inventory)
    mutated["http"][0]["access"] = "TRUST_CLIENT"
    _assert_invalid(mutated, "unknown access type")


def test_stale_policy_is_rejected(inventory):
    mutated = deepcopy(inventory)
    stale = deepcopy(mutated["http"][0])
    stale["key"] = "GET /removed-route::removed_route"
    stale["method"] = "GET"
    stale["path"] = "/removed-route"
    stale["operation"] = "removed_route"
    mutated["http"].append(stale)
    _assert_invalid(mutated, "stale HTTP policies")


def test_missing_test_mapping_is_rejected(inventory):
    mutated = deepcopy(inventory)
    mutated["http"][0]["tests"] = []
    _assert_invalid(mutated, "missing test mapping")


def test_site_policy_without_resolver_is_rejected(inventory):
    mutated = deepcopy(inventory)
    candidate = next(item for item in mutated["http"] if item["access"].startswith("SITE_"))
    candidate["resolver"] = None
    _assert_invalid(mutated, "missing ownership resolver")


def test_unclassified_channel_is_rejected(inventory):
    mutated = deepcopy(inventory)
    mutated["websocket"]["channels"].pop()
    _assert_invalid(mutated, "missing WebSocket channels")


def test_unclassified_websocket_endpoint_is_rejected(inventory):
    mutated = deepcopy(inventory)
    mutated["websocket"]["endpoints"].pop()
    _assert_invalid(mutated, "missing WebSocket endpoints")


def test_unclassified_broadcast_producer_is_rejected(inventory):
    mutated = deepcopy(inventory)
    mutated["websocket"]["producers"].pop()
    _assert_invalid(mutated, "missing broadcast producers")
