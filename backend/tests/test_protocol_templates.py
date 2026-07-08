"""Built-in pilot protocol template tests."""

from app.data.protocol_templates import list_builtin_protocol_templates
from gateway.adapters.modbus_tcp import _parse_address_spec


def test_builtin_protocol_templates_have_parseable_modbus_addresses():
    """Every built-in Modbus template point address must be accepted by adapters."""
    templates = list_builtin_protocol_templates()
    assert {t["key"] for t in templates} == {
        "huawei-ups5000-modbus",
        "huawei-fusioncol5000a-modbus-rtu",
    }

    for template in templates:
        assert template["point_config"], template["key"]
        if template["key"] == "huawei-ups5000-modbus":
            default_config = template["extra_config"]["default_connection_config"]
            assert default_config["load_subtype"] == "ups"
            assert default_config["controllable_params"] == []
        if template["key"] == "huawei-fusioncol5000a-modbus-rtu":
            default_config = template["extra_config"]["default_connection_config"]
            assert default_config["load_subtype"] == "row_ac"
            assert default_config["controllable_params"] == [
                "power_switch",
                "temperature_setpoint",
                "humidity_setpoint",
            ]
            writable_points = {p["point_id"] for p in template["point_config"] if p.get("writable")}
            assert {"unit_power_control", "temperature_setpoint", "humidity_setpoint"} <= writable_points
        seen_point_ids: set[str] = set()
        for point in template["point_config"]:
            assert point["point_id"] not in seen_point_ids
            seen_point_ids.add(point["point_id"])

            spec = _parse_address_spec(point["address"], point["data_type"])
            assert spec.reg_type == "HR"
            assert spec.address >= 0
            assert spec.count >= 1
