from app.models.energy import MeterPoint
from tests.conftest import auth_headers


async def test_demand_algorithms_do_not_fabricate_results_without_data(client, admin_user, async_db):
    _, token = admin_user
    meter = MeterPoint(
        meter_code="DEMAND-NO-DATA",
        meter_name="无数据计量点",
        declared_demand=300,
        is_enabled=True,
    )
    async_db.add(meter)
    await async_db.flush()
    headers = auth_headers(token)

    config_response = await client.get("/api/v1/energy/analysis/demand-config", headers=headers)
    curve_response = await client.get(
        "/api/v1/energy/demand/aggregated-curve",
        params={"meter_point_id": meter.id, "days": 30},
        headers=headers,
    )
    plan_response = await client.get(
        "/api/v1/energy/demand/optimization-plan",
        params={"meter_point_id": meter.id},
        headers=headers,
    )

    assert config_response.status_code == 200
    config_item = next(item for item in config_response.json()["data"]["items"] if item["meter_point_id"] == meter.id)
    assert config_item["data_sufficient"] is False
    assert config_item["max_demand_12m"] == 0
    assert config_item["optimal_demand"] == 300
    assert config_item["potential_saving"] == 0
    assert "数据不足" in config_item["recommendation"]

    assert curve_response.status_code == 200
    curve = curve_response.json()["data"]
    assert curve["statistics"]["data_sufficient"] is False
    assert curve["statistics"]["max_demand"] == 0
    assert all(point["avg_demand"] == 0 for point in curve["aggregated_points"])

    assert plan_response.status_code == 200
    plan = plan_response.json()["data"]
    assert plan["data_sufficient"] is False
    assert plan["statistics"]["max_demand"] == 0
    assert plan["optimization"]["recommended_demand"] == 300
    assert plan["optimization"]["annual_saving"] == 0
    assert plan["optimization"]["recommendations"][0]["type"] == "insufficient_data"
