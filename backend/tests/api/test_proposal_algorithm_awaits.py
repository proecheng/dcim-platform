from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from decimal import Decimal
from datetime import datetime, timedelta

from app.api.v1 import proposal as proposal_api
from app.models.energy import EnergySavingProposal, ProposalMeasure
from app.services.adaptive_optimization_service import AdaptiveOptimizationService
from app.services.effect_monitoring_service import EffectMonitoringService
from app.services.template_generator import TemplateGenerator


async def test_generate_proposal_awaits_async_generator(monkeypatch):
    generated = SimpleNamespace(id=7)
    generate = AsyncMock(return_value=generated)
    monkeypatch.setattr(TemplateGenerator, "generate_proposal", generate)

    db = MagicMock()
    db.commit = AsyncMock()
    db.refresh = AsyncMock()

    result = await proposal_api.generate_proposal(
        proposal_api.ProposalCreate(template_id="A1", analysis_days=30),
        db,
    )

    assert result is generated
    generate.assert_awaited_once_with("A1", 30)
    db.add.assert_called_once_with(generated)
    db.commit.assert_awaited_once()


async def test_analyze_does_not_duplicate_recent_completed_template(async_db, monkeypatch):
    recent = EnergySavingProposal(
        proposal_code="AWAIT-RECENT-001",
        proposal_type="A",
        template_id="A1",
        template_name="近期已完成方案",
        total_benefit=Decimal("1.00"),
        total_investment=Decimal("0"),
        status="completed",
        created_at=datetime.now() - timedelta(hours=1),
    )
    async_db.add(recent)
    await async_db.commit()

    generate = AsyncMock()
    monkeypatch.setattr(TemplateGenerator, "TEMPLATE_CONFIGS", {"A1": {}})
    monkeypatch.setattr(TemplateGenerator, "generate_proposal", generate)

    result = await proposal_api.analyze_and_generate(async_db)

    assert result["data"]["new_suggestions"] == 0
    generate.assert_not_awaited()


async def test_analyze_allows_completed_template_after_cooldown(async_db, monkeypatch):
    old = EnergySavingProposal(
        proposal_code="AWAIT-OLD-001",
        proposal_type="A",
        template_id="A1",
        template_name="历史已完成方案",
        total_benefit=Decimal("1.00"),
        total_investment=Decimal("0"),
        status="completed",
        created_at=datetime.now() - timedelta(days=2),
    )
    async_db.add(old)
    await async_db.commit()

    generated = EnergySavingProposal(
        proposal_code="AWAIT-NEW-001",
        proposal_type="A",
        template_id="A1",
        template_name="新分析方案",
        total_benefit=Decimal("1.00"),
        total_investment=Decimal("0"),
        status="pending",
    )
    generate = AsyncMock(return_value=generated)
    monkeypatch.setattr(TemplateGenerator, "TEMPLATE_CONFIGS", {"A1": {}})
    monkeypatch.setattr(TemplateGenerator, "generate_proposal", generate)

    result = await proposal_api.analyze_and_generate(async_db)

    assert result["data"]["new_suggestions"] == 1
    generate.assert_awaited_once_with("A1", analysis_days=30)


async def test_rl_model_info_awaits_service(monkeypatch):
    model_info = {
        "model_name": "adaptive_optimizer",
        "is_available": True,
        "is_trained": False,
        "total_steps": 3,
        "total_episodes": 0,
        "exploration_rate": 0.2,
        "exploration_phase": "initial",
        "state_dim": 16,
        "action_spec": {},
    }
    get_model_info = AsyncMock(return_value=model_info)
    monkeypatch.setattr(AdaptiveOptimizationService, "get_model_info", get_model_info)

    result = await proposal_api.get_rl_model_info(MagicMock())

    assert result.model_name == "adaptive_optimizer"
    assert result.total_steps == 3
    get_model_info.assert_awaited_once()


async def test_rl_optimize_awaits_service(monkeypatch):
    optimize = AsyncMock(
        return_value={
            "success": True,
            "adjustments": {
                "temperature": {
                    "value": 25.0,
                    "description": "调整温度设定值",
                    "unit": "C",
                    "index": 1,
                }
            },
            "raw_actions": {"temperature": 0.5},
            "exploration": False,
            "exploration_rate": 0.2,
            "confidence": 0.8,
            "optimization_id": 11,
        }
    )
    monkeypatch.setattr(AdaptiveOptimizationService, "optimize", optimize)

    result = await proposal_api.rl_optimize(9, None, MagicMock())

    assert result.success is True
    assert result.optimization_id == 11
    assert result.adjustments["temperature"].value == 25.0
    optimize.assert_awaited_once_with(9, None)


async def test_monitoring_status_awaits_service(monkeypatch):
    get_status = AsyncMock(return_value={"active": True, "session_id": 5})
    monkeypatch.setattr(EffectMonitoringService, "get_monitoring_status", get_status)

    result = await proposal_api.get_monitoring_status(4, MagicMock())

    assert result["data"]["active"] is True
    get_status.assert_awaited_once_with(4)


async def test_train_from_monitoring_awaits_closed_loop_service(monkeypatch):
    proposal = SimpleNamespace(id=4)
    query_result = MagicMock()
    query_result.scalar_one_or_none.return_value = proposal
    db = MagicMock()
    db.execute = AsyncMock(return_value=query_result)

    train = AsyncMock(return_value={"success": True, "reward": 0.75})
    monkeypatch.setattr(AdaptiveOptimizationService, "train_from_monitoring", train)

    result = await proposal_api.rl_train_from_monitoring(4, db)

    assert result["data"]["reward"] == 0.75
    train.assert_awaited_once_with(4)


async def test_proposal_list_eager_loads_algorithm_measures(async_db):
    proposal = EnergySavingProposal(
        proposal_code="AWAIT-LIST-001",
        proposal_type="A",
        template_id="A1",
        template_name="测试方案",
        total_benefit=Decimal("1.20"),
        total_investment=Decimal("0"),
        status="pending",
    )
    proposal.measures.append(
        ProposalMeasure(
            measure_code="AWAIT-LIST-M001",
            regulation_object="测试负荷",
            regulation_description="测试措施",
            annual_benefit=Decimal("1.20"),
            investment=Decimal("0"),
            is_selected=False,
            execution_status="pending",
        )
    )
    async_db.add(proposal)
    await async_db.commit()
    async_db.expire_all()

    result = await proposal_api.get_proposals(limit=10, db=async_db)

    item = next(p for p in result["data"]["items"] if p.proposal_code == "AWAIT-LIST-001")
    assert len(item.measures) == 1
    assert item.measures[0].measure_code == "AWAIT-LIST-M001"


async def test_proposal_suggestion_accept_and_complete_closed_loop(async_db):
    proposal = EnergySavingProposal(
        proposal_code="AWAIT-CYCLE-001",
        proposal_type="A",
        template_id="A2",
        template_name="闭环测试方案",
        total_benefit=Decimal("2.00"),
        total_investment=Decimal("0"),
        status="pending",
    )
    proposal.measures.append(
        ProposalMeasure(
            measure_code="AWAIT-CYCLE-M001",
            regulation_object="测试需量",
            annual_benefit=Decimal("2.00"),
            investment=Decimal("0"),
            is_selected=False,
            execution_status="pending",
        )
    )
    async_db.add(proposal)
    await async_db.commit()

    accepted = await proposal_api.accept_all_proposal_measures(
        proposal.id,
        proposal_api.ProposalRemarkRequest(remark="浏览器测试接受"),
        async_db,
    )
    assert accepted["data"]["status"] == "accepted"
    assert accepted["data"]["selected_measure_ids"] == [proposal.measures[0].id]

    completed = await proposal_api.complete_proposal(
        proposal.id,
        proposal_api.ProposalCompletionRequest(actual_saving=123.4, remark="闭环完成"),
        async_db,
    )
    assert completed["data"]["status"] == "completed"

    suggestions = await proposal_api.get_proposals_as_suggestions(db=async_db)
    item = next(row for row in suggestions["data"] if row["id"] == proposal.id)
    assert item["template_id"] == "A2"
    assert item["status"] == "completed"
    assert item["actual_saving"] == 123.4
    assert item["remark"] == "闭环完成"

    potential = await proposal_api.get_saving_potential(db=async_db)
    assert potential["data"]["actual_saving_ytd"] == 123.4


async def test_saving_potential_converts_cost_to_energy_and_excludes_prior_year(async_db):
    current_year = datetime.now().year
    current = EnergySavingProposal(
        proposal_code="AWAIT-SAVING-CURRENT",
        proposal_type="A",
        template_id="A1",
        template_name="本年完成方案",
        total_benefit=Decimal("12.00"),
        total_investment=Decimal("0"),
        status="completed",
        trace_summary={
            "status_history": [
                {
                    "status": "completed",
                    "timestamp": f"{current_year}-08-16T10:00:00",
                    "actual_saving": 456.7,
                }
            ]
        },
    )
    previous = EnergySavingProposal(
        proposal_code="AWAIT-SAVING-PREVIOUS",
        proposal_type="A",
        template_id="A2",
        template_name="往年完成方案",
        total_benefit=Decimal("0"),
        total_investment=Decimal("0"),
        status="completed",
        trace_summary={
            "status_history": [
                {
                    "status": "completed",
                    "timestamp": f"{current_year - 1}-12-31T23:59:59Z",
                    "actual_saving": 999.9,
                }
            ]
        },
    )
    async_db.add_all([current, previous])
    await async_db.commit()

    result = await proposal_api.get_saving_potential(db=async_db)

    assert result["data"]["total_cost_saving"] == 10000.0
    assert result["data"]["total_potential_saving"] == 10000.0 / 0.6
    assert result["data"]["actual_saving_ytd"] == 456.7


async def test_proposal_suggestion_reject_records_reason(async_db):
    proposal = EnergySavingProposal(
        proposal_code="AWAIT-REJECT-001",
        proposal_type="B",
        template_id="B1",
        template_name="拒绝测试方案",
        total_benefit=Decimal("3.00"),
        total_investment=Decimal("1.00"),
        status="pending",
    )
    async_db.add(proposal)
    await async_db.commit()

    result = await proposal_api.reject_proposal(
        proposal.id,
        proposal_api.ProposalRemarkRequest(remark="暂不具备实施条件"),
        async_db,
    )

    assert result["data"]["status"] == "rejected"
    suggestions = await proposal_api.get_proposals_as_suggestions(db=async_db)
    item = next(row for row in suggestions["data"] if row["id"] == proposal.id)
    assert item["remark"] == "暂不具备实施条件"
