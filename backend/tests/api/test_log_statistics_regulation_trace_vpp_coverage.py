"""
日志/统计/负荷调节/数据追溯/VPP 五模块 API 覆盖率测试
"""
import pytest
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, patch, MagicMock

from app.models.log import OperationLog, SystemLog, CommunicationLog
from app.models.point import Point, PointRealtime
from app.models.device import Device
from app.models.alarm import Alarm
from tests.conftest import auth_headers


# ============== 辅助函数 ==============

async def _seed_logs(db):
    """创建日志种子数据"""
    now = datetime.now()
    op = OperationLog(
        user_id=1, username="admin", module="point", action="create",
        target_name="测试点位", ip_address="127.0.0.1",
        remark="测试操作", created_at=now,
    )
    sys_log = SystemLog(
        log_level="ERROR", module="alarm", message="测试系统日志",
        exception="TestException", created_at=now,
    )
    comm = CommunicationLog(
        device_id=1, comm_type="request", protocol="modbus",
        status="success", duration_ms=50, created_at=now,
    )
    db.add_all([op, sys_log, comm])
    await db.flush()
    return op, sys_log, comm


async def _seed_statistics_data(db):
    """创建统计模块种子数据"""
    p = Point(
        point_code="STAT-AI-001", point_name="统计测试点位",
        point_type="AI", device_type="UPS", area_code="A1", is_enabled=True,
    )
    d = Device(
        device_code="STAT-DEV-001", device_name="统计测试设备",
        device_type="UPS", status="online", area_code="A1",
    )
    db.add_all([p, d])
    await db.flush()
    return p, d


# ============== 日志模块 ==============

class TestLogOperations:
    """日志 API: /api/v1/logs/*"""

    async def test_get_operation_logs(self, client, admin_user, async_db):
        """GET /logs/operations — 操作日志列表"""
        _, token = admin_user
        await _seed_logs(async_db)
        resp = await client.get("/api/v1/logs/operations", headers=auth_headers(token))
        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data
        assert "total" in data

    async def test_get_operation_logs_with_filters(self, client, admin_user, async_db):
        """GET /logs/operations — 带筛选参数"""
        _, token = admin_user
        await _seed_logs(async_db)
        resp = await client.get(
            "/api/v1/logs/operations",
            params={"module": "point", "action": "create", "keyword": "测试"},
            headers=auth_headers(token),
        )
        assert resp.status_code == 200

    async def test_get_system_logs(self, client, admin_user, async_db):
        """GET /logs/systems — 系统日志列表"""
        _, token = admin_user
        await _seed_logs(async_db)
        resp = await client.get("/api/v1/logs/systems", headers=auth_headers(token))
        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data

    async def test_get_system_logs_filter_level(self, client, admin_user, async_db):
        """GET /logs/systems?log_level=ERROR"""
        _, token = admin_user
        await _seed_logs(async_db)
        resp = await client.get(
            "/api/v1/logs/systems",
            params={"log_level": "ERROR"},
            headers=auth_headers(token),
        )
        assert resp.status_code == 200

    async def test_get_communication_logs(self, client, admin_user, async_db):
        """GET /logs/communications — 通讯日志列表"""
        _, token = admin_user
        await _seed_logs(async_db)
        resp = await client.get("/api/v1/logs/communications", headers=auth_headers(token))
        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data

    async def test_get_communication_logs_filter_status(self, client, admin_user, async_db):
        """GET /logs/communications?status=success"""
        _, token = admin_user
        await _seed_logs(async_db)
        resp = await client.get(
            "/api/v1/logs/communications",
            params={"status": "success"},
            headers=auth_headers(token),
        )
        assert resp.status_code == 200

    async def test_export_operation_logs(self, client, admin_user, async_db):
        """GET /logs/export?log_type=operation — CSV导出"""
        _, token = admin_user
        await _seed_logs(async_db)
        resp = await client.get(
            "/api/v1/logs/export",
            params={"log_type": "operation"},
            headers=auth_headers(token),
        )
        assert resp.status_code == 200
        assert "text/csv" in resp.headers.get("content-type", "")

    async def test_export_system_logs(self, client, admin_user, async_db):
        """GET /logs/export?log_type=system"""
        _, token = admin_user
        await _seed_logs(async_db)
        resp = await client.get(
            "/api/v1/logs/export",
            params={"log_type": "system"},
            headers=auth_headers(token),
        )
        assert resp.status_code == 200

    async def test_export_communication_logs(self, client, admin_user, async_db):
        """GET /logs/export?log_type=communication"""
        _, token = admin_user
        await _seed_logs(async_db)
        resp = await client.get(
            "/api/v1/logs/export",
            params={"log_type": "communication"},
            headers=auth_headers(token),
        )
        assert resp.status_code == 200

    async def test_export_invalid_type(self, client, admin_user, async_db):
        """GET /logs/export?log_type=invalid — 400"""
        _, token = admin_user
        resp = await client.get(
            "/api/v1/logs/export",
            params={"log_type": "invalid"},
            headers=auth_headers(token),
        )
        assert resp.status_code == 400

    async def test_get_log_statistics(self, client, admin_user, async_db):
        """GET /logs/statistics — 日志统计"""
        _, token = admin_user
        await _seed_logs(async_db)
        resp = await client.get(
            "/api/v1/logs/statistics",
            params={"days": 7},
            headers=auth_headers(token),
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "operation_logs" in data
        assert "system_logs" in data
        assert "communication_logs" in data


# ============== 统计分析模块 ==============

class TestStatistics:
    """统计分析 API: /api/v1/statistics/*"""

    async def test_get_overview(self, client, admin_user, async_db):
        """GET /statistics/overview — 系统概览"""
        _, token = admin_user
        await _seed_statistics_data(async_db)
        resp = await client.get("/api/v1/statistics/overview", headers=auth_headers(token))
        assert resp.status_code == 200
        data = resp.json()
        assert "points" in data
        assert "devices" in data
        assert "alarms" in data

    async def test_get_points_statistics(self, client, admin_user, async_db):
        """GET /statistics/points — 点位统计"""
        _, token = admin_user
        await _seed_statistics_data(async_db)
        resp = await client.get("/api/v1/statistics/points", headers=auth_headers(token))
        assert resp.status_code == 200
        data = resp.json()
        assert "by_type" in data

    async def test_get_alarms_statistics(self, client, admin_user, async_db):
        """GET /statistics/alarms — 告警统计"""
        _, token = admin_user
        resp = await client.get(
            "/api/v1/statistics/alarms",
            params={"days": 7},
            headers=auth_headers(token),
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "by_level" in data
        assert "daily_trend" in data

    async def test_get_energy_statistics(self, client, admin_user, async_db):
        """GET /statistics/energy — 能耗统计"""
        _, token = admin_user
        resp = await client.get(
            "/api/v1/statistics/energy",
            params={"days": 7},
            headers=auth_headers(token),
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "period_days" in data
        assert "power_points" in data

    async def test_get_availability_statistics(self, client, admin_user, async_db):
        """GET /statistics/availability — 可用性统计"""
        _, token = admin_user
        resp = await client.get(
            "/api/v1/statistics/availability",
            params={"days": 7},
            headers=auth_headers(token),
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "overall_availability" in data
        assert "by_device_type" in data

    async def test_get_comparison_alarm(self, client, admin_user, async_db):
        """GET /statistics/comparison?metric=alarm — 告警同环比"""
        _, token = admin_user
        resp = await client.get(
            "/api/v1/statistics/comparison",
            params={"metric": "alarm"},
            headers=auth_headers(token),
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["metric"] == "alarm"

    async def test_get_comparison_energy(self, client, admin_user, async_db):
        """GET /statistics/comparison?metric=energy — 能耗同环比"""
        _, token = admin_user
        resp = await client.get(
            "/api/v1/statistics/comparison",
            params={"metric": "energy"},
            headers=auth_headers(token),
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["metric"] == "energy"


# ============== 负荷调节模块 ==============

class TestRegulation:
    """负荷调节 API: /api/v1/regulation/*"""

    async def test_get_configs_empty(self, client, admin_user, async_db):
        """GET /regulation/configs — 空列表"""
        _, token = admin_user
        with patch(
            "app.services.load_regulation.LoadRegulationService.get_configs",
            new_callable=AsyncMock, return_value=[],
        ):
            resp = await client.get("/api/v1/regulation/configs", headers=auth_headers(token))
        assert resp.status_code == 200
        assert resp.json() == []

    async def test_get_config_not_found(self, client, admin_user, async_db):
        """GET /regulation/configs/999 — 404"""
        _, token = admin_user
        with patch(
            "app.services.load_regulation.LoadRegulationService.get_config_by_id",
            new_callable=AsyncMock, return_value=None,
        ):
            resp = await client.get("/api/v1/regulation/configs/999", headers=auth_headers(token))
        assert resp.status_code == 404

    async def test_create_config(self, client, admin_user, async_db):
        """POST /regulation/configs — 创建配置"""
        _, token = admin_user
        mock_config = MagicMock()
        mock_config.id = 1
        mock_resp = {
            "id": 1, "device_id": 1, "regulation_type": "temperature",
            "min_value": 18.0, "max_value": 28.0, "current_value": 24.0,
            "default_value": 24.0, "step_size": 1.0, "unit": "℃",
            "power_factor": 0.5, "base_power": 10.0, "priority": 5,
            "comfort_impact": "low", "performance_impact": "none",
            "power_curve": None, "is_enabled": True, "is_auto": False,
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
            "device_name": "测试空调", "device_type": "AC", "rated_power": 10.0,
        }
        with patch(
            "app.services.load_regulation.LoadRegulationService.create_config",
            new_callable=AsyncMock, return_value=mock_config,
        ), patch(
            "app.services.load_regulation.LoadRegulationService.get_config_by_id",
            new_callable=AsyncMock, return_value=mock_resp,
        ):
            resp = await client.post(
                "/api/v1/regulation/configs",
                json={
                    "device_id": 1, "regulation_type": "temperature",
                    "min_value": 18.0, "max_value": 28.0,
                },
                headers=auth_headers(token),
            )
        assert resp.status_code == 200

    async def test_delete_config_not_found(self, client, admin_user, async_db):
        """DELETE /regulation/configs/999 — 404"""
        _, token = admin_user
        with patch(
            "app.services.load_regulation.LoadRegulationService.delete_config",
            new_callable=AsyncMock, return_value=False,
        ):
            resp = await client.delete("/api/v1/regulation/configs/999", headers=auth_headers(token))
        assert resp.status_code == 404

    async def test_simulate_not_found(self, client, admin_user, async_db):
        """POST /regulation/simulate — 配置不存在 404"""
        _, token = admin_user
        with patch(
            "app.services.load_regulation.LoadRegulationService.simulate_regulation",
            new_callable=AsyncMock, return_value=None,
        ):
            resp = await client.post(
                "/api/v1/regulation/simulate",
                json={"config_id": 999, "target_value": 20.0},
                headers=auth_headers(token),
            )
        assert resp.status_code == 404

    async def test_apply_not_found(self, client, admin_user, async_db):
        """POST /regulation/apply — 配置不存在 404"""
        _, token = admin_user
        with patch(
            "app.services.load_regulation.LoadRegulationService.apply_regulation",
            new_callable=AsyncMock, return_value=None,
        ):
            resp = await client.post(
                "/api/v1/regulation/apply",
                json={"config_id": 999, "target_value": 20.0, "reason": "test"},
                headers=auth_headers(token),
            )
        assert resp.status_code == 404

    async def test_get_history(self, client, admin_user, async_db):
        """GET /regulation/history — 调节历史"""
        _, token = admin_user
        with patch(
            "app.services.load_regulation.LoadRegulationService.get_history",
            new_callable=AsyncMock, return_value=[],
        ):
            resp = await client.get("/api/v1/regulation/history", headers=auth_headers(token))
        assert resp.status_code == 200
        assert resp.json() == []

    async def test_get_recommendations(self, client, admin_user, async_db):
        """GET /regulation/recommendations — 调节建议"""
        _, token = admin_user
        with patch(
            "app.services.load_regulation.LoadRegulationService.get_recommendations",
            new_callable=AsyncMock, return_value=[],
        ):
            resp = await client.get("/api/v1/regulation/recommendations", headers=auth_headers(token))
        assert resp.status_code == 200


# ============== 数据追溯链模块 ==============

class TestTrace:
    """数据追溯链 API: /api/v1/trace/*"""

    async def test_get_trace_detail_not_found(self, client, admin_user, async_db):
        """GET /trace/{trace_id} — 404"""
        _, token = admin_user
        with patch(
            "app.services.data_trace_service.DataTraceService.get_trace_by_id",
            new_callable=AsyncMock, return_value=None,
        ):
            resp = await client.get("/api/v1/trace/nonexistent-id", headers=auth_headers(token))
        assert resp.status_code == 404

    async def test_get_trace_tree_not_found(self, client, admin_user, async_db):
        """GET /trace/{trace_id}/tree — 404"""
        _, token = admin_user
        with patch(
            "app.services.data_trace_service.DataTraceService.get_trace_tree",
            new_callable=AsyncMock, return_value=None,
        ):
            resp = await client.get("/api/v1/trace/nonexistent-id/tree", headers=auth_headers(token))
        assert resp.status_code == 404

    async def test_get_trace_detail_found(self, client, admin_user, async_db):
        """GET /trace/{trace_id} — 200"""
        _, token = admin_user
        mock_trace = MagicMock()
        mock_trace.id = 1
        mock_trace.trace_id = "TR-001"
        mock_trace.param_code = "test_param"
        mock_trace.param_name = "测试参数"
        mock_trace.mapping_type = "direct"
        mock_trace.raw_value = 42.0
        mock_trace.formatted_value = "42.0"
        mock_trace.value_unit = "kW"
        mock_trace.depth = 0
        mock_trace.parent_trace_id = None
        mock_trace.child_trace_ids = None
        mock_trace.calculated_at = datetime.now()
        mock_trace.created_at = datetime.now()
        mock_trace.source_table = "test_table"
        mock_trace.source_field = "test_field"
        mock_trace.filter_condition = None
        with patch(
            "app.services.data_trace_service.DataTraceService.get_trace_by_id",
            new_callable=AsyncMock, return_value=mock_trace,
        ):
            resp = await client.get("/api/v1/trace/TR-001", headers=auth_headers(token))
        assert resp.status_code == 200
        assert resp.json()["code"] == 0

    async def test_get_proposal_traces_empty(self, client, admin_user, async_db):
        """GET /trace/proposal/{proposal_id} — 空结果"""
        _, token = admin_user
        with patch(
            "app.services.data_trace_service.DataTraceService.get_traces_by_proposal",
            new_callable=AsyncMock, return_value=[],
        ):
            resp = await client.get("/api/v1/trace/proposal/1", headers=auth_headers(token))
        assert resp.status_code == 200
        assert resp.json()["data"]["total_traces"] == 0

    async def test_get_measure_traces(self, client, admin_user, async_db):
        """GET /trace/measure/{measure_id} — 措施追溯"""
        _, token = admin_user
        with patch(
            "app.services.data_trace_service.DataTraceService.get_traces_by_measure",
            new_callable=AsyncMock, return_value=[],
        ):
            resp = await client.get("/api/v1/trace/measure/1", headers=auth_headers(token))
        assert resp.status_code == 200
        assert resp.json()["data"]["total"] == 0

    async def test_get_proposal_ml_traces(self, client, admin_user, async_db):
        """GET /trace/proposal/{id}/ml — ML预测追溯"""
        _, token = admin_user
        resp = await client.get("/api/v1/trace/proposal/1/ml", headers=auth_headers(token))
        assert resp.status_code == 200
        data = resp.json()
        assert data["data"]["summary"]["total_ml_traces"] == 0

    async def test_get_measure_ml_traces(self, client, admin_user, async_db):
        """GET /trace/measure/{id}/ml — 措施ML追溯"""
        _, token = admin_user
        resp = await client.get("/api/v1/trace/measure/1/ml", headers=auth_headers(token))
        assert resp.status_code == 200
        assert resp.json()["data"]["has_ml_predictions"] is False

    async def test_list_mappings(self, client, admin_user, async_db):
        """GET /trace/mappings/list — 映射列表"""
        _, token = admin_user
        resp = await client.get("/api/v1/trace/mappings/list", headers=auth_headers(token))
        assert resp.status_code == 200
        data = resp.json()
        assert data["data"]["total"] == 0

    async def test_create_mapping(self, client, admin_user, async_db):
        """POST /trace/mappings — 创建映射"""
        _, token = admin_user
        resp = await client.post(
            "/api/v1/trace/mappings",
            json={
                "param_code": "test_param_001",
                "param_name": "测试参数",
                "mapping_type": "direct",
                "source_table": "test_table",
                "source_field": "test_field",
            },
            headers=auth_headers(token),
        )
        assert resp.status_code == 200
        assert resp.json()["code"] == 0

    async def test_create_mapping_duplicate(self, client, admin_user, async_db):
        """POST /trace/mappings — 重复创建 409"""
        _, token = admin_user
        payload = {
            "param_code": "dup_param",
            "param_name": "重复参数",
            "mapping_type": "direct",
        }
        # 第一次创建
        await client.post("/api/v1/trace/mappings", json=payload, headers=auth_headers(token))
        # 第二次重复
        resp = await client.post("/api/v1/trace/mappings", json=payload, headers=auth_headers(token))
        assert resp.status_code == 409

    async def test_get_template_params(self, client, admin_user, async_db):
        """GET /trace/templates/{template_id}/params"""
        _, token = admin_user
        with patch(
            "app.services.data_trace_service.DataTraceService.get_template_parameters",
            new_callable=AsyncMock, return_value=[],
        ):
            resp = await client.get("/api/v1/trace/templates/A1/params", headers=auth_headers(token))
        assert resp.status_code == 200
        assert resp.json()["data"]["total"] == 0

    async def test_init_default_mappings(self, client, admin_user, async_db):
        """POST /trace/mappings/init — 初始化默认映射"""
        _, token = admin_user
        resp = await client.post("/api/v1/trace/mappings/init", headers=auth_headers(token))
        assert resp.status_code == 200
        assert resp.json()["data"]["created_count"] >= 0


# ============== VPP 方案分析模块 ==============

class TestVPP:
    """VPP 方案分析 API: /api/v1/vpp/*"""

    async def test_get_formula_reference(self, client, admin_user, async_db):
        """GET /vpp/formula-reference — 公式参考（无外部依赖）"""
        _, token = admin_user
        resp = await client.get("/api/v1/vpp/formula-reference", headers=auth_headers(token))
        assert resp.status_code == 200
        data = resp.json()
        assert data["code"] == 0
        assert "用电规模指标" in data["data"]

    async def test_get_load_metrics(self, client, admin_user, async_db):
        """GET /vpp/load-metrics — 负荷特性"""
        _, token = admin_user
        mock_result = {"P_max": {"value": 100, "unit": "kW"}}
        with patch(
            "app.services.vpp_calculator.VPPCalculator.calc_load_metrics",
            new_callable=AsyncMock, return_value=mock_result,
        ):
            resp = await client.get(
                "/api/v1/vpp/load-metrics",
                params={"start_date": "2025-10-01", "end_date": "2025-10-30"},
                headers=auth_headers(token),
            )
        assert resp.status_code == 200
        assert resp.json()["code"] == 0

    async def test_get_cost_structure(self, client, admin_user, async_db):
        """GET /vpp/cost-structure/{month} — 电费结构"""
        _, token = admin_user
        mock_result = {"market_ratio": {"value": 68.0, "unit": "%"}}
        with patch(
            "app.services.vpp_calculator.VPPCalculator.calc_cost_structure",
            new_callable=AsyncMock, return_value=mock_result,
        ):
            resp = await client.get("/api/v1/vpp/cost-structure/2025-01", headers=auth_headers(token))
        assert resp.status_code == 200

    async def test_get_transfer_potential(self, client, admin_user, async_db):
        """GET /vpp/transfer-potential — 峰谷转移潜力"""
        _, token = admin_user
        mock_result = {"transferable_load": {"value": 4500, "unit": "kW"}}
        with patch(
            "app.services.vpp_calculator.VPPCalculator.calc_transfer_potential",
            new_callable=AsyncMock, return_value=mock_result,
        ):
            resp = await client.get("/api/v1/vpp/transfer-potential", headers=auth_headers(token))
        assert resp.status_code == 200

    async def test_get_vpp_revenue(self, client, admin_user, async_db):
        """GET /vpp/vpp-revenue — VPP收益测算"""
        _, token = admin_user
        mock_result = {"total_vpp_revenue": {"value": 1710000, "unit": "元/年"}}
        with patch(
            "app.services.vpp_calculator.VPPCalculator.calc_vpp_revenue",
            new_callable=AsyncMock, return_value=mock_result,
        ):
            resp = await client.get(
                "/api/v1/vpp/vpp-revenue",
                params={"adjustable_capacity": 4500.0},
                headers=auth_headers(token),
            )
        assert resp.status_code == 200

    async def test_get_roi(self, client, admin_user, async_db):
        """GET /vpp/roi — 投资回报"""
        _, token = admin_user
        mock_result = {"roi": {"value": 312.5, "unit": "%"}}
        with patch(
            "app.services.vpp_calculator.VPPCalculator.calc_roi",
            new_callable=AsyncMock, return_value=mock_result,
        ):
            resp = await client.get(
                "/api/v1/vpp/roi",
                params={"annual_benefit": 5000000.0},
                headers=auth_headers(token),
            )
        assert resp.status_code == 200

    async def test_generate_analysis(self, client, admin_user, async_db):
        """POST /vpp/analysis — 完整分析"""
        _, token = admin_user
        mock_result = {"summary": {"total_benefit": 5000000}}
        with patch(
            "app.services.vpp_calculator.VPPCalculator.generate_full_analysis",
            new_callable=AsyncMock, return_value=mock_result,
        ):
            resp = await client.post(
                "/api/v1/vpp/analysis",
                json={
                    "months": ["2025-01", "2025-03"],
                    "start_date": "2025-10-01",
                    "end_date": "2025-10-30",
                },
                headers=auth_headers(token),
            )
        assert resp.status_code == 200
        assert resp.json()["code"] == 0
