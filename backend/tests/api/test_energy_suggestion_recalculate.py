from datetime import date

import pytest

from app.api.v1.energy import recalculate_suggestion
from app.models.energy import EnergySavingProposal


@pytest.mark.asyncio
async def test_recalculate_accepts_energy_saving_proposal_id(async_db):
    proposal = EnergySavingProposal(
        proposal_code="TEST-RECALCULATE-001",
        proposal_type="A",
        template_id="A1",
        template_name="峰谷套利优化方案",
        total_benefit=1,
        analysis_start_date=date.today(),
        analysis_end_date=date.today(),
    )
    async_db.add(proposal)
    await async_db.commit()
    await async_db.refresh(proposal)

    response = await recalculate_suggestion(
        suggestion_id=proposal.id,
        params={
            "selected_devices": [],
            "shift_hours": 2,
            "source_period": "peak",
            "target_period": "valley",
        },
        db=async_db,
        current_user=None,
    )

    assert response.data["effects"]["daily_energy_kwh"] == 0
    assert response.data["effects"]["annual_saving_yuan"] == 0
