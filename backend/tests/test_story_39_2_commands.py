"""Story 39.2 command registry and fail-closed execution tests."""

import ast
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.services.command_registry import (
    CommandPolicyError,
    authorize_command,
    get_command_definition,
    COMMAND_DEFINITIONS,
)
from app.services.command_service import get_risk_configs, get_risk_level, update_risk_configs
from app.services.device_control_service import ControlResult, DeviceControlService
from app.services.execution_service import ExecutionService


def test_unknown_command_is_not_registered():
    with pytest.raises(CommandPolicyError, match="未知命令"):
        get_command_definition("future_unclassified_command")


def test_registered_command_rejects_invalid_parameters():
    with pytest.raises(CommandPolicyError, match="参数"):
        authorize_command("ac_temp_set", {"temperature": "hot"}, entrypoint="command_api")


def test_registry_authorization_contains_policy_metadata():
    authorization = authorize_command("power_off", {"circuit": "B-01"}, entrypoint="command_api")

    assert authorization.command_type == "power_off"
    assert authorization.risk_level == "critical"
    assert authorization.requires_approval is True
    assert authorization.entrypoint == "command_api"
    assert authorization.parameters == {"circuit": "B-01"}


def test_every_registered_command_has_a_test_and_entrypoint():
    assert COMMAND_DEFINITIONS
    for command_type, definition in COMMAND_DEFINITIONS.items():
        assert definition.entrypoints, command_type
        assert definition.test_ids, command_type
        assert all(test_id.startswith("CMD-") for test_id in definition.test_ids)


def test_device_control_callers_are_explicitly_inventoried():
    services_root = Path(__file__).parents[1] / "app" / "services"
    callers = set()
    for source_file in services_root.rglob("*.py"):
        tree = ast.parse(source_file.read_text(encoding="utf-8"), filename=str(source_file))
        if any(
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "control_device_regulation"
            for node in ast.walk(tree)
        ):
            callers.add(source_file.relative_to(services_root).as_posix())

    assert callers == {"device_control_service.py", "execution_service.py", "load_regulation.py"}


@pytest.mark.asyncio
async def test_unknown_command_risk_lookup_fails_closed(async_db):
    with pytest.raises(CommandPolicyError, match="未知命令"):
        await get_risk_level(async_db, "future_unclassified_command")


@pytest.mark.asyncio
async def test_risk_config_cannot_lower_minimum_risk(async_db):
    with pytest.raises(ValueError, match="最低风险等级"):
        await update_risk_configs(
            async_db,
            [{"command_type": "power_off", "risk_level": "normal", "description": "unsafe"}],
            updated_by=1,
        )


@pytest.mark.asyncio
async def test_risk_config_description_round_trips(async_db):
    await update_risk_configs(
        async_db,
        [{"command_type": "ac_temp_set", "risk_level": "normal", "description": "界面自定义说明"}],
        updated_by=1,
    )

    configs = await get_risk_configs(async_db)
    config = next(item for item in configs if item["command_type"] == "ac_temp_set")
    assert config["description"] == "界面自定义说明"


@pytest.mark.asyncio
async def test_device_control_rejects_missing_registry_authorization(async_db):
    service = DeviceControlService(async_db)

    action = await service.control_device_regulation(1, "temperature", 25.0)

    assert action.result == ControlResult.FAILED
    assert "命令策略授权" in action.message


@pytest.mark.asyncio
async def test_device_control_rejects_mismatched_registry_authorization(async_db):
    service = DeviceControlService(async_db)
    authorization = authorize_command(
        "device_regulation",
        {
            "device_id": 2,
            "regulation_type": "temperature",
            "target_value": 25.0,
            "force": False,
        },
        entrypoint="execution_service",
    )

    action = await service.control_device_regulation(
        1,
        "temperature",
        25.0,
        command_authorization=authorization,
    )

    assert action.result == ControlResult.FAILED
    assert "不匹配" in action.message


@pytest.mark.asyncio
async def test_execution_service_validates_parameters_before_state_change():
    task = SimpleNamespace(
        execution_mode="auto",
        status="pending",
        parameters={"target_state": {"value": 25.0}, "selected_devices": []},
    )
    query_result = SimpleNamespace(scalar_one_or_none=lambda: task)
    db = SimpleNamespace(execute=AsyncMock(return_value=query_result), commit=AsyncMock())
    service = ExecutionService(db)

    result = await service.execute_auto_task(1)

    assert result["success"] is False
    assert "参数无效" in result["error"]
    assert task.status == "pending"
    db.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_batch_control_validates_entire_batch_before_execution():
    service = DeviceControlService(None)
    service.control_device_regulation = AsyncMock()

    with pytest.raises(CommandPolicyError, match="参数无效"):
        await service.batch_control(
            [
                {
                    "device_id": 1,
                    "regulation_type": "temperature",
                    "target_value": 25.0,
                },
                {
                    "device_id": "not-an-integer",
                    "regulation_type": "temperature",
                    "target_value": 25.0,
                },
            ]
        )

    service.control_device_regulation.assert_not_awaited()
