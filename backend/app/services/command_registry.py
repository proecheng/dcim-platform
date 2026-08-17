"""Fail-closed command definitions shared by every execution entrypoint."""

from dataclasses import dataclass, field
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError


class CommandPolicyError(ValueError):
    """Raised when a command cannot be proven safe to execute."""


class _CommandParameters(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class AcTempSetParameters(_CommandParameters):
    temperature: float = Field(ge=16, le=32)


class LightSwitchParameters(_CommandParameters):
    enabled: bool


class DoorAccessParameters(_CommandParameters):
    action: Literal["open", "close", "lock", "unlock"]


class PowerOffParameters(_CommandParameters):
    circuit: str = Field(min_length=1, max_length=100)


class UpsSwitchParameters(_CommandParameters):
    mode: Literal["inverter", "bypass", "off"]


class DeviceDecommissionParameters(_CommandParameters):
    reason: str = Field(min_length=1, max_length=500)


class DeviceRegulationParameters(_CommandParameters):
    device_id: int = Field(gt=0)
    regulation_type: Literal["temperature", "brightness", "mode", "load"]
    target_value: float
    force: bool = False


@dataclass(frozen=True)
class CommandDefinition:
    parameter_schema: type[_CommandParameters]
    minimum_risk: Literal["normal", "critical"]
    requires_approval: bool
    description: str
    entrypoints: frozenset[str]
    test_ids: tuple[str, ...]


_AUTHORIZATION_PROOF = object()


@dataclass(frozen=True)
class CommandAuthorization:
    command_type: str
    risk_level: Literal["normal", "critical"]
    requires_approval: bool
    entrypoint: str
    parameters: dict
    _proof: object = field(repr=False, compare=False)


COMMAND_DEFINITIONS: dict[str, CommandDefinition] = {
    "ac_temp_set": CommandDefinition(
        AcTempSetParameters,
        "normal",
        False,
        "调整空调温度",
        frozenset({"command_api"}),
        ("CMD-AC-TEMP-01",),
    ),
    "light_switch": CommandDefinition(
        LightSwitchParameters,
        "normal",
        False,
        "开关照明",
        frozenset({"command_api"}),
        ("CMD-LIGHT-01",),
    ),
    "door_access": CommandDefinition(
        DoorAccessParameters,
        "normal",
        False,
        "门禁开关",
        frozenset({"command_api"}),
        ("CMD-DOOR-01",),
    ),
    "power_off": CommandDefinition(
        PowerOffParameters,
        "critical",
        True,
        "切断回路电源",
        frozenset({"command_api"}),
        ("CMD-POWER-OFF-01",),
    ),
    "ups_switch": CommandDefinition(
        UpsSwitchParameters,
        "critical",
        True,
        "UPS 切换",
        frozenset({"command_api"}),
        ("CMD-UPS-01",),
    ),
    "device_decommission": CommandDefinition(
        DeviceDecommissionParameters,
        "critical",
        True,
        "设备下架断电",
        frozenset({"command_api"}),
        ("CMD-DECOMMISSION-01",),
    ),
    "device_regulation": CommandDefinition(
        DeviceRegulationParameters,
        "normal",
        False,
        "执行节能计划设备调节",
        frozenset({"execution_service", "device_control_batch", "load_regulation"}),
        ("CMD-REGULATION-01",),
    ),
}


def get_command_definition(command_type: str) -> CommandDefinition:
    definition = COMMAND_DEFINITIONS.get(command_type)
    if definition is None:
        raise CommandPolicyError(f"未知命令类型: {command_type!r}")
    return definition


def authorize_command(command_type: str, parameters: dict, *, entrypoint: str) -> CommandAuthorization:
    definition = get_command_definition(command_type)
    if entrypoint not in definition.entrypoints:
        raise CommandPolicyError(f"命令 {command_type!r} 不允许从入口 {entrypoint!r} 执行")
    try:
        validated = definition.parameter_schema.model_validate(parameters)
    except ValidationError as exc:
        raise CommandPolicyError(f"命令 {command_type!r} 参数无效") from exc
    return CommandAuthorization(
        command_type=command_type,
        risk_level=definition.minimum_risk,
        requires_approval=definition.requires_approval,
        entrypoint=entrypoint,
        parameters=validated.model_dump(),
        _proof=_AUTHORIZATION_PROOF,
    )


def verify_device_regulation_authorization(
    authorization: CommandAuthorization | None,
    *,
    device_id: int,
    regulation_type: str,
    target_value: float,
    force: bool,
) -> None:
    if authorization is None or authorization._proof is not _AUTHORIZATION_PROOF:
        raise CommandPolicyError("缺少有效的命令策略授权")
    if authorization.command_type != "device_regulation":
        raise CommandPolicyError("命令策略授权与设备调节不匹配")
    expected = DeviceRegulationParameters.model_validate(
        {
            "device_id": device_id,
            "regulation_type": regulation_type,
            "target_value": target_value,
            "force": force,
        }
    ).model_dump()
    if authorization.parameters != expected:
        raise CommandPolicyError("命令策略授权与设备调节参数不匹配")
