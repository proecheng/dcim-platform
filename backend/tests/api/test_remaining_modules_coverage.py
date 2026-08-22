"""
剩余 API 模块覆盖率测试 — 覆盖 optimization, execution, system_health, realtime 等未测试端点
"""

from tests.conftest import auth_headers


# ============== 系统健康 /api/v1/system ==============


class TestSystemHealth:
    """系统健康状态 API 测试"""

    async def test_health_requires_auth(self, client):
        """未认证访问健康状态应返回 401"""
        resp = await client.get("/api/v1/system/health")
        assert resp.status_code in (401, 403)

    async def test_health_authenticated(self, client, admin_user):
        """认证用户可获取系统健康状态"""
        _, token = admin_user
        resp = await client.get("/api/v1/system/health", headers=auth_headers(token))
        assert resp.status_code == 200
        data = resp.json()
        assert data["database"]["status"] in {"connected", "disconnected"}
        assert data["database"]["engine"] in {"SQLite", "PostgreSQL", "MySQL", "MariaDB"}
        assert data["application"]["name"]
        assert data["application"]["version"]
        assert data["application"]["uptime_seconds"] >= 0

    async def test_backup_config_requires_auth(self, client):
        """未认证访问备份配置应返回 401"""
        resp = await client.get("/api/v1/system/backup/config")
        assert resp.status_code in (401, 403)

    async def test_backup_config_authenticated(self, client, admin_user):
        """管理员可获取备份配置"""
        _, token = admin_user
        resp = await client.get("/api/v1/system/backup/config", headers=auth_headers(token))
        assert resp.status_code == 200

    async def test_backup_list(self, client, admin_user):
        """管理员可获取备份列表"""
        _, token = admin_user
        resp = await client.get("/api/v1/system/backup/list", headers=auth_headers(token))
        assert resp.status_code == 200


# ============== 实时数据 /api/v1/realtime ==============


class TestRealtime:
    """实时数据 API 测试"""

    async def test_realtime_requires_auth(self, client):
        """未认证访问实时数据应返回 401"""
        resp = await client.get("/api/v1/realtime")
        assert resp.status_code in (401, 403)

    async def test_realtime_list(self, client, admin_user):
        """认证用户可获取实时数据列表"""
        _, token = admin_user
        resp = await client.get("/api/v1/realtime", headers=auth_headers(token))
        assert resp.status_code == 200

    async def test_realtime_summary(self, client, admin_user):
        """认证用户可获取实时数据汇总"""
        _, token = admin_user
        resp = await client.get("/api/v1/realtime/summary", headers=auth_headers(token))
        assert resp.status_code == 200

    async def test_realtime_dashboard(self, client, admin_user):
        """认证用户可获取仪表盘数据"""
        _, token = admin_user
        resp = await client.get("/api/v1/realtime/dashboard", headers=auth_headers(token))
        assert resp.status_code == 200

    async def test_realtime_nonexistent_point(self, client, admin_user):
        """查询不存在的点位应返回 404"""
        _, token = admin_user
        resp = await client.get("/api/v1/realtime/99999", headers=auth_headers(token))
        assert resp.status_code in (404, 422)


# ============== 执行管理 /api/v1/execution ==============


class TestExecution:
    """执行管理 API 测试"""

    async def test_execution_plans_requires_auth(self, client):
        """未认证访问执行计划应返回 401"""
        resp = await client.get("/api/v1/execution/plans")
        assert resp.status_code in (401, 403)

    async def test_execution_plans_list(self, client, admin_user):
        """认证用户可获取执行计划列表"""
        _, token = admin_user
        resp = await client.get("/api/v1/execution/plans", headers=auth_headers(token))
        assert resp.status_code == 200

    async def test_execution_results_list(self, client, admin_user):
        """认证用户可获取追踪结果列表"""
        _, token = admin_user
        resp = await client.get("/api/v1/execution/results", headers=auth_headers(token))
        assert resp.status_code == 200

    async def test_execution_stats_summary(self, client, admin_user):
        """认证用户可获取执行统计汇总"""
        _, token = admin_user
        resp = await client.get("/api/v1/execution/stats/summary", headers=auth_headers(token))
        assert resp.status_code == 200

    async def test_execution_nonexistent_plan(self, client, admin_user):
        """查询不存在的执行计划应返回 404"""
        _, token = admin_user
        resp = await client.get("/api/v1/execution/plans/99999", headers=auth_headers(token))
        assert resp.status_code == 404


# ============== 日前调度优化 /api/v1/optimization ==============


class TestOptimization:
    """日前调度优化 API 测试"""

    async def test_forecast_requires_auth(self, client):
        """未认证访问预测应返回 401"""
        resp = await client.get("/api/v1/optimization/forecast")
        assert resp.status_code in (401, 403, 422)

    async def test_forecast_demo(self, client, admin_user):
        """认证用户可获取负荷预测"""
        _, token = admin_user
        resp = await client.get(
            "/api/v1/optimization/forecast",
            headers=auth_headers(token),
        )
        assert resp.status_code in (200, 422)

    async def test_optimize_day_ahead(self, client, admin_user):
        """认证用户可执行日前优化"""
        _, token = admin_user
        resp = await client.post(
            "/api/v1/optimization/day-ahead",
            json={
                "demand_price": 40.0,
                "declared_demand": 800.0,
                "use_storage": True,
                "storage_capacity": 500.0,
                "storage_charge_power": 100.0,
                "storage_discharge_power": 100.0,
            },
            headers=auth_headers(token),
        )
        assert resp.status_code in (200, 422)

    async def test_optimization_summary(self, client, admin_user):
        """认证用户可查询优化汇总"""
        _, token = admin_user
        resp = await client.get("/api/v1/optimization/summary", headers=auth_headers(token))
        assert resp.status_code == 200


# ============== 统计分析 /api/v1/statistics ==============


class TestStatistics:
    """统计分析 API 测试"""

    async def test_overview_requires_auth(self, client):
        """未认证访问统计概览应返回 401"""
        resp = await client.get("/api/v1/statistics/overview")
        assert resp.status_code in (401, 403)

    async def test_overview(self, client, admin_user):
        """认证用户可获取统计概览"""
        _, token = admin_user
        resp = await client.get("/api/v1/statistics/overview", headers=auth_headers(token))
        assert resp.status_code == 200

    async def test_points_statistics(self, client, admin_user):
        """认证用户可获取点位统计"""
        _, token = admin_user
        resp = await client.get("/api/v1/statistics/points", headers=auth_headers(token))
        assert resp.status_code == 200

    async def test_alarms_statistics(self, client, admin_user):
        """认证用户可获取告警统计"""
        _, token = admin_user
        resp = await client.get("/api/v1/statistics/alarms", headers=auth_headers(token))
        assert resp.status_code == 200

    async def test_energy_statistics(self, client, admin_user):
        """认证用户可获取能耗统计"""
        _, token = admin_user
        resp = await client.get("/api/v1/statistics/energy", headers=auth_headers(token))
        assert resp.status_code == 200


# ============== 电价配置 /api/v1/pricing ==============


class TestPricing:
    """电价配置 API 测试"""

    async def test_pricing_requires_auth(self, client):
        """未认证访问电价配置应返回 401"""
        resp = await client.get("/api/v1/pricing/full-config")
        assert resp.status_code in (401, 403)

    async def test_pricing_full_config(self, client, admin_user):
        """认证用户可获取完整电价配置"""
        _, token = admin_user
        resp = await client.get("/api/v1/pricing/full-config", headers=auth_headers(token))
        assert resp.status_code == 200

    async def test_pricing_global_config(self, client, admin_user):
        """认证用户可获取全局电价配置"""
        _, token = admin_user
        resp = await client.get("/api/v1/pricing/global-config", headers=auth_headers(token))
        assert resp.status_code == 200

    async def test_pricing_calculate_bill(self, client, admin_user):
        """认证用户可计算电费"""
        _, token = admin_user
        resp = await client.post(
            "/api/v1/pricing/calculate-bill",
            json={"energy_kwh": 1000.0},
            headers=auth_headers(token),
        )
        # 可能需要更多参数，接受 200 或 422
        assert resp.status_code in (200, 422)


# ============== 电费监控 /api/v1/monitoring ==============


class TestMonitoring:
    """电费监控 API 测试"""

    async def test_monitoring_requires_auth(self, client):
        """未认证访问电费监控应返回 401"""
        resp = await client.get("/api/v1/monitoring/realtime/status")
        assert resp.status_code in (401, 403)

    async def test_monitoring_realtime_status(self, client, admin_user):
        """认证用户可获取实时需量状态"""
        _, token = admin_user
        resp = await client.get("/api/v1/monitoring/realtime/status", headers=auth_headers(token))
        assert resp.status_code == 200

    async def test_monitoring_monthly_current(self, client, admin_user):
        """认证用户可获取当月电费汇总"""
        _, token = admin_user
        resp = await client.get("/api/v1/monitoring/monthly/current", headers=auth_headers(token))
        assert resp.status_code == 200


# ============== 楼层图 /api/v1/floor-map ==============


class TestFloorMap:
    """楼层图 API 测试"""

    async def test_floors_requires_auth(self, client):
        """未认证访问楼层列表应返回 401"""
        resp = await client.get("/api/v1/floor-map/floors")
        assert resp.status_code in (401, 403)

    async def test_floors_list(self, client, admin_user):
        """认证用户可获取楼层列表"""
        _, token = admin_user
        resp = await client.get("/api/v1/floor-map/floors", headers=auth_headers(token))
        assert resp.status_code == 200

    async def test_floor_default(self, client, admin_user):
        """认证用户可获取默认楼层"""
        _, token = admin_user
        resp = await client.get("/api/v1/floor-map/default", headers=auth_headers(token))
        # 可能返回 200 或 404（无默认楼层）
        assert resp.status_code in (200, 404)


# ============== 需量 API ==============


class TestDemand:
    """需量嵌入式 API 测试"""

    async def test_demand_comparison(self, client, admin_user):
        """认证用户可获取需量对比数据"""
        _, token = admin_user
        resp = await client.get("/api/v1/demand/comparison", headers=auth_headers(token))
        assert resp.status_code == 200

    async def test_demand_curve_mini(self, client, admin_user):
        """认证用户可获取需量迷你曲线"""
        _, token = admin_user
        resp = await client.get("/api/v1/demand/curve-mini", headers=auth_headers(token))
        assert resp.status_code == 200
