from app.services.load_shift.cooling_linkage_service import CoolingLinkageService


async def test_empty_cooling_linkage_status_has_no_simulated_metrics(async_db):
    status = await CoolingLinkageService.get_status(async_db)

    assert status["data_sufficient"] is False
    assert status["linkage_active"] is False
    assert status["adjust_count"] == 0
    assert status["total_cooling_power"] is None
    assert status["total_energy_saving"] is None
    assert status["total_cost_saving"] is None
    assert "暂无制冷联动执行记录" in status["warning"]
