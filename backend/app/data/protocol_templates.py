"""Built-in device templates derived from pilot Modbus protocol PDFs.

The templates are intentionally stored as ordinary Python data so they can be
reviewed, tested, and installed into the editable DeviceTemplate table on demand.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any


def _point(
    point_id: str,
    name: str,
    address: str,
    data_type: str,
    *,
    scale: float = 1.0,
    offset: float = 0.0,
    unit: str = "",
    category: str = "",
    writable: bool = False,
    enum_mapping: dict[str, str] | None = None,
) -> dict[str, Any]:
    point: dict[str, Any] = {
        "point_id": point_id,
        "name": name,
        "address": address,
        "data_type": data_type,
        "scale": scale,
        "offset": offset,
        "unit": unit,
        "category": category,
        "writable": writable,
        "description": name,
    }
    if enum_mapping:
        point["enum_mapping"] = enum_mapping
    return point


UPS5000_TEMPLATE: dict[str, Any] = {
    "key": "huawei-ups5000-modbus",
    "name": "Huawei UPS5000 Modbus Protocol",
    "manufacturer": "Huawei Digital Power",
    "model": "UPS5000",
    "protocol_type": "modbus_tcp",
    "description": (
        "Pilot template based on UPS5000 Modbus external communication protocol, "
        "document version 01, published 2022-05-24."
    ),
    "point_config": [
        _point("input_voltage_a", "A phase input voltage", "HR:40001", "uint16", scale=0.1, unit="V", category="input"),
        _point("input_voltage_b", "B phase input voltage", "HR:40002", "uint16", scale=0.1, unit="V", category="input"),
        _point("input_voltage_c", "C phase input voltage", "HR:40003", "uint16", scale=0.1, unit="V", category="input"),
        _point("input_current_a", "A phase input current", "HR:40007", "uint16", scale=0.1, unit="A", category="input"),
        _point("input_current_b", "B phase input current", "HR:40008", "uint16", scale=0.1, unit="A", category="input"),
        _point("input_current_c", "C phase input current", "HR:40009", "uint16", scale=0.1, unit="A", category="input"),
        _point("input_frequency", "Input frequency", "HR:40010", "uint16", scale=0.01, unit="Hz", category="input"),
        _point("output_voltage_a", "A phase output voltage", "HR:40046", "uint16", scale=0.1, unit="V", category="output"),
        _point("output_voltage_b", "B phase output voltage", "HR:40047", "uint16", scale=0.1, unit="V", category="output"),
        _point("output_voltage_c", "C phase output voltage", "HR:40048", "uint16", scale=0.1, unit="V", category="output"),
        _point("output_current_a", "A phase output current", "HR:40052", "uint16", scale=0.1, unit="A", category="output"),
        _point("output_current_b", "B phase output current", "HR:40053", "uint16", scale=0.1, unit="A", category="output"),
        _point("output_current_c", "C phase output current", "HR:40054", "uint16", scale=0.1, unit="A", category="output"),
        _point("output_frequency", "Output frequency", "HR:40055", "uint16", scale=0.01, unit="Hz", category="output"),
        _point("output_active_power_a", "A phase output active power", "HR:40056", "int16", scale=0.1, unit="kW", category="output"),
        _point("output_active_power_b", "B phase output active power", "HR:40057", "int16", scale=0.1, unit="kW", category="output"),
        _point("output_active_power_c", "C phase output active power", "HR:40058", "int16", scale=0.1, unit="kW", category="output"),
        _point("output_load_rate_a", "A phase output load rate", "HR:40068", "uint16", scale=0.1, unit="%", category="output"),
        _point("output_load_rate_b", "B phase output load rate", "HR:40069", "uint16", scale=0.1, unit="%", category="output"),
        _point("output_load_rate_c", "C phase output load rate", "HR:40070", "uint16", scale=0.1, unit="%", category="output"),
        _point("battery_voltage", "Battery voltage", "HR:40105", "uint16", scale=0.1, unit="V", category="battery"),
        _point("battery_current", "Battery current", "HR:40106", "int16", scale=0.1, unit="A", category="battery"),
        _point("battery_temperature", "Battery temperature", "HR:40108", "int16", scale=0.1, unit="degC", category="battery"),
        _point("battery_backup_time", "Battery backup time", "HR:40109", "uint16", unit="s", category="battery"),
        _point("battery_soc", "Battery remaining capacity", "HR:40110", "uint16", unit="%", category="battery"),
        _point("battery_soh", "Battery SOH", "HR:40835", "uint16", unit="%", category="battery"),
        _point("power_supply_state", "Power supply state", "HR:40131.7-9", "uint16", category="status"),
        _point("ups_run_state", "UPS run state", "HR:40131.10-12", "uint16", category="status"),
        _point("battery_run_state", "Battery run state", "HR:40131.13-15", "uint16", category="status"),
        _point("urgent_alarm", "Urgent alarm", "HR:40300.0", "bool", category="alarm"),
        _point("major_alarm", "Major alarm", "HR:40300.1", "bool", category="alarm"),
        _point("minor_alarm", "Minor alarm", "HR:40300.2", "bool", category="alarm"),
        _point("warning_alarm", "Warning alarm", "HR:40300.3", "bool", category="alarm"),
        _point("battery_power_supply", "Battery power supply", "HR:40303", "bool", category="status"),
        _point("bypass_power_supply", "Bypass power supply", "HR:40304", "bool", category="status"),
    ],
    "extra_config": {
        "source_document": "UPS5000 Modbus对外通讯协议 .pdf",
        "document_version": "01",
        "published_at": "2022-05-24",
        "supported_protocols": ["modbus_tcp", "modbus_rtu"],
        "default_connection_config": {
            "host": "",
            "port": 502,
            "device_id": 1,
            "timeout": 3,
            "word_order": "big",
            "load_subtype": "ups",
            "controllable_params": [],
        },
        "rtu_connection_config": {
            "port": "COM1",
            "baudrate": 9600,
            "bytesize": 8,
            "parity": "N",
            "stopbits": 1,
            "device_id": 1,
            "timeout": 3,
            "word_order": "big",
            "load_subtype": "ups",
            "controllable_params": [],
        },
    },
}


FUSIONCOL5000A_TEMPLATE: dict[str, Any] = {
    "key": "huawei-fusioncol5000a-modbus-rtu",
    "name": "Huawei FusionCol5000-A Modbus RTU Protocol",
    "manufacturer": "Huawei Digital Power",
    "model": "FusionCol5000-A",
    "protocol_type": "modbus_rtu",
    "description": (
        "Pilot template based on FusionCol5000-A row-level air-cooled smart cooling "
        "product Modbus protocol V100R022C10, document version 03, published 2023-01-12."
    ),
    "point_config": [
        _point("unit_power_state", "Unit power state", "HR:0x1800", "bool", category="status"),
        _point("unit_power_control", "Unit power on/off control", "HR:0x1880", "bool", category="control", writable=True),
        _point("cooling_output", "Cooling output", "HR:0x1802", "uint16", unit="%", category="cooling"),
        _point("indoor_fan_output", "Indoor fan output", "HR:0x1803", "uint16", unit="%", category="fan"),
        _point("humidifying_output", "Humidifying output", "HR:0x1804", "uint16", unit="%", category="humidifier"),
        _point("heating_output", "Heating output", "HR:0x1805", "uint16", unit="%", category="heater"),
        _point("dehumidifying_output", "Dehumidifying output", "HR:0x180E", "uint16", unit="%", category="dehumidifier"),
        _point("cooling_capacity", "Cooling capacity", "HR:0x1810:2", "uint32", scale=0.01, unit="kW", category="cooling"),
        _point("power_frequency", "Power frequency", "HR:0x2004", "uint16", unit="Hz", category="power"),
        _point("ab_line_voltage", "AB line voltage", "HR:0x2009", "uint16", unit="V", category="power"),
        _point("bc_line_voltage", "BC line voltage", "HR:0x200A", "uint16", unit="V", category="power"),
        _point("ca_line_voltage", "CA line voltage", "HR:0x200B", "uint16", unit="V", category="power"),
        _point("temperature_control_type", "Temperature/humidity control type", "HR:0x2800", "uint16", category="environment"),
        _point("current_temperature", "Current temperature", "HR:0x2801", "int16", scale=0.1, unit="degC", category="environment"),
        _point("current_humidity", "Current humidity", "HR:0x2802", "uint16", scale=0.1, unit="%RH", category="environment"),
        _point("supply_air_avg_temperature", "Supply air average temperature", "HR:0x2803", "int16", scale=0.1, unit="degC", category="environment"),
        _point("return_air_avg_temperature", "Return air average temperature", "HR:0x2804", "int16", scale=0.1, unit="degC", category="environment"),
        _point("cold_aisle_avg_temperature", "Cold aisle average temperature", "HR:0x2805", "int16", scale=0.1, unit="degC", category="environment"),
        _point("hot_aisle_avg_temperature", "Hot aisle average temperature", "HR:0x2806", "int16", scale=0.1, unit="degC", category="environment"),
        _point("supply_air_avg_humidity", "Supply air average humidity", "HR:0x2807", "uint16", scale=0.1, unit="%RH", category="environment"),
        _point("return_air_avg_humidity", "Return air average humidity", "HR:0x2808", "uint16", scale=0.1, unit="%RH", category="environment"),
        _point("cold_aisle_avg_humidity", "Cold aisle average humidity", "HR:0x2809", "uint16", scale=0.1, unit="%RH", category="environment"),
        _point("hot_aisle_avg_humidity", "Hot aisle average humidity", "HR:0x280A", "uint16", scale=0.1, unit="%RH", category="environment"),
        _point("temperature_setpoint", "Temperature setpoint", "HR:0x2962", "uint16", scale=0.1, unit="degC", category="setpoint", writable=True),
        _point("humidity_setpoint", "Humidity setpoint", "HR:0x2963", "uint16", scale=0.1, unit="%RH", category="setpoint", writable=True),
        _point("compressor_speed", "Compressor speed", "HR:0x3800", "uint16", unit="rpm", category="compressor"),
        _point("indoor_fan_1_speed", "Indoor fan 1 speed", "HR:0x4000", "uint16", unit="rpm", category="fan"),
        _point("indoor_fan_2_speed", "Indoor fan 2 speed", "HR:0x4001", "uint16", unit="rpm", category="fan"),
        _point("indoor_fan_control", "Indoor fan control state", "HR:0x4010", "uint16", unit="%", category="fan"),
        _point("outdoor_fan_state", "Outdoor fan state", "HR:0x4801", "uint16", unit="%", category="fan"),
        _point("water_pump_state", "Drainage pump state", "HR:0x6005", "uint16", unit="%", category="pump"),
        _point("power_lost_alarm", "Power lost alarm", "HR:0x0800.0", "bool", category="alarm"),
        _point("remote_shutdown_alarm", "Remote shutdown alarm", "HR:0x0800.1", "bool", category="alarm"),
        _point("supply_air_high_temperature_alarm", "Supply air high temperature alarm", "HR:0x0808.0", "bool", category="alarm"),
        _point("supply_air_low_temperature_alarm", "Supply air low temperature alarm", "HR:0x0808.1", "bool", category="alarm"),
        _point("return_air_high_temperature_alarm", "Return air high temperature alarm", "HR:0x0808.6", "bool", category="alarm"),
        _point("return_air_low_temperature_alarm", "Return air low temperature alarm", "HR:0x0808.7", "bool", category="alarm"),
        _point("compressor_drive_alarm", "Compressor drive alarm", "HR:0x080C.11", "bool", category="alarm"),
        _point("indoor_fan_1_fault", "Indoor fan 1 fault", "HR:0x081C.0", "bool", category="alarm"),
        _point("indoor_fan_2_fault", "Indoor fan 2 fault", "HR:0x081C.2", "bool", category="alarm"),
    ],
    "extra_config": {
        "source_document": "FusionCol5000-A 行级风冷智能温控产品 Modbus协议 .pdf",
        "document_version": "03",
        "published_at": "2023-01-12",
        "supported_protocols": ["modbus_rtu"],
        "default_connection_config": {
            "port": "COM1",
            "baudrate": 9600,
            "bytesize": 8,
            "parity": "N",
            "stopbits": 1,
            "device_id": 1,
            "timeout": 3,
            "word_order": "big",
            "load_subtype": "row_ac",
            "controllable_params": ["power_switch", "temperature_setpoint", "humidity_setpoint"],
        },
    },
}


_BUILTIN_TEMPLATES = {
    UPS5000_TEMPLATE["key"]: UPS5000_TEMPLATE,
    FUSIONCOL5000A_TEMPLATE["key"]: FUSIONCOL5000A_TEMPLATE,
}


def list_builtin_protocol_templates() -> list[dict[str, Any]]:
    """Return deep copies of all built-in protocol templates."""
    return [deepcopy(template) for template in _BUILTIN_TEMPLATES.values()]


def get_builtin_protocol_template(key: str) -> dict[str, Any] | None:
    """Return a deep copy of one built-in protocol template."""
    template = _BUILTIN_TEMPLATES.get(key)
    return deepcopy(template) if template else None


def as_device_template_payload(template: dict[str, Any]) -> dict[str, Any]:
    """Convert built-in catalog entry to DeviceTemplate model payload."""
    return {
        "name": template["name"],
        "manufacturer": template["manufacturer"],
        "model": template["model"],
        "protocol_type": template["protocol_type"],
        "description": template.get("description"),
        "point_config": deepcopy(template.get("point_config", [])),
        "extra_config": deepcopy(template.get("extra_config")),
    }
