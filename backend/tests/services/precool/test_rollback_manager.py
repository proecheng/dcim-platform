"""
回退保护管理器单元测试（纯 mock）

Story 30.2: 7 项自动回退保护机制
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timedelta

from app.models.rollback import RollbackTriggerType, RollbackEvent
from app.services.precool.rollback_manager import (
    RollbackManager,
    DEFAULT_TEMP_ROLLBACK,
    DEFAULT_PREDICTED_RATE,
    DEFAULT_RATE_MULTIPLIER,
    DEFAULT_RATE_LIMIT,
    DEFAULT_DEW_POINT_MARGIN,
    RECOVERY_WAIT_TEMP,
)


def _mock_session():
    session = AsyncMock()
    session.flush = AsyncMock()
    return session


# ==================== 条件1: 温度超限 ====================

class TestTempOverLimit:
    @pytest.mark.asyncio
    async def test_normal_temp_no_trigger(self):
        """温度正常不触发"""
        mgr = RollbackManager()
        session = _mock_session()

        with patch(
            "app.services.precool.constraints._get_max_inlet_temperature",
            new_callable=AsyncMock,
            return_value=24.0,
        ):
            result = await mgr._check_temp_over_limit(1, session)
            assert result is None

    @pytest.mark.asyncio
    async def test_temp_over_26_triggers(self):
        """温度 > 26°C 触发回退"""
        mgr = RollbackManager()
        session = _mock_session()

        with patch(
            "app.services.precool.constraints._get_max_inlet_temperature",
            new_callable=AsyncMock,
            return_value=26.5,
        ):
            result = await mgr._check_temp_over_limit(1, session)
            assert result is not None
            assert result["value"] == 26.5
            assert result["threshold"] == DEFAULT_TEMP_ROLLBACK

    @pytest.mark.asyncio
    async def test_temp_none_no_trigger(self):
        """无温度数据不触发"""
        mgr = RollbackManager()
        session = _mock_session()

        with patch(
            "app.services.precool.constraints._get_max_inlet_temperature",
            new_callable=AsyncMock,
            return_value=None,
        ):
            result = await mgr._check_temp_over_limit(1, session)
            assert result is None


# ==================== 条件2: 温升超预测 ====================

class TestRateOverPredicted:
    @pytest.mark.asyncio
    async def test_normal_rate_no_trigger(self):
        """温升正常不触发"""
        mgr = RollbackManager()
        session = _mock_session()

        with patch(
            "app.services.datacenter_shift_strategy._calculate_temperature_rise_rate",
            new_callable=AsyncMock,
            return_value=1.0,
        ), patch.object(mgr, "_get_config_value", new_callable=AsyncMock, return_value=DEFAULT_PREDICTED_RATE):
            result = await mgr._check_rate_over_predicted(1, session)
            assert result is None

    @pytest.mark.asyncio
    async def test_rate_over_150_percent_triggers(self):
        """温升 > 150% 基准值触发"""
        mgr = RollbackManager()
        session = _mock_session()

        with patch(
            "app.services.datacenter_shift_strategy._calculate_temperature_rise_rate",
            new_callable=AsyncMock,
            return_value=4.0,  # > 2.0 * 1.5 = 3.0
        ), patch.object(mgr, "_get_config_value", new_callable=AsyncMock, return_value=DEFAULT_PREDICTED_RATE):
            result = await mgr._check_rate_over_predicted(1, session)
            assert result is not None
            assert result["value"] == 4.0

    @pytest.mark.asyncio
    async def test_negative_rate_no_trigger(self):
        """降温不触发"""
        mgr = RollbackManager()
        session = _mock_session()

        with patch(
            "app.services.datacenter_shift_strategy._calculate_temperature_rise_rate",
            new_callable=AsyncMock,
            return_value=-3.0,
        ), patch.object(mgr, "_get_config_value", new_callable=AsyncMock, return_value=DEFAULT_PREDICTED_RATE):
            result = await mgr._check_rate_over_predicted(1, session)
            assert result is None


# ==================== 条件3: 温变速率超限 ====================

class TestRateOverLimit:
    @pytest.mark.asyncio
    async def test_normal_rate_no_trigger(self):
        """速率正常不触发"""
        mgr = RollbackManager()
        session = _mock_session()

        with patch(
            "app.services.datacenter_shift_strategy._calculate_temperature_rise_rate",
            new_callable=AsyncMock,
            return_value=3.0,
        ):
            result = await mgr._check_rate_over_limit(1, session)
            assert result is None

    @pytest.mark.asyncio
    async def test_rate_over_limit_triggers(self):
        """速率 > 5°C/h 触发"""
        mgr = RollbackManager()
        session = _mock_session()

        with patch(
            "app.services.datacenter_shift_strategy._calculate_temperature_rise_rate",
            new_callable=AsyncMock,
            return_value=6.0,
        ):
            result = await mgr._check_rate_over_limit(1, session)
            assert result is not None
            assert result["threshold"] == DEFAULT_RATE_LIMIT


# ==================== 条件4: 空调故障 ====================

class TestAcFault:
    @pytest.mark.asyncio
    async def test_no_fault_no_trigger(self):
        """无故障不触发"""
        mgr = RollbackManager()
        session = _mock_session()

        mock_result = MagicMock()
        mock_result.all.return_value = []
        session.execute = AsyncMock(return_value=mock_result)

        result = await mgr._check_ac_fault(1, session)
        assert result is None

    @pytest.mark.asyncio
    async def test_ac_fault_triggers(self):
        """空调故障触发"""
        mgr = RollbackManager()
        session = _mock_session()

        mock_result = MagicMock()
        mock_result.all.return_value = [("fault", "AC-01")]
        session.execute = AsyncMock(return_value=mock_result)

        result = await mgr._check_ac_fault(1, session)
        assert result is not None
        assert result["value"] == 1


# ==================== 条件5: 传感器离线 ====================

class TestSensorOffline:
    @pytest.mark.asyncio
    async def test_all_online_no_trigger(self):
        """全部在线不触发"""
        mgr = RollbackManager()
        session = _mock_session()

        mock_result = MagicMock()
        mock_result.scalar.return_value = 0
        session.execute = AsyncMock(return_value=mock_result)

        result = await mgr._check_sensor_offline(1, session)
        assert result is None

    @pytest.mark.asyncio
    async def test_sensor_offline_triggers(self):
        """传感器离线触发"""
        mgr = RollbackManager()
        session = _mock_session()

        mock_result = MagicMock()
        mock_result.scalar.return_value = 2
        session.execute = AsyncMock(return_value=mock_result)

        result = await mgr._check_sensor_offline(1, session)
        assert result is not None
        assert result["value"] == 2


# ==================== 条件6: UPS 供电 ====================

class TestUpsActive:
    @pytest.mark.asyncio
    async def test_no_ups_data_no_trigger(self):
        """无 UPS 数据不触发"""
        mgr = RollbackManager()
        session = _mock_session()

        mock_result = MagicMock()
        mock_result.first.return_value = None
        session.execute = AsyncMock(return_value=mock_result)

        result = await mgr._check_ups_active(1, session)
        assert result is None

    @pytest.mark.asyncio
    async def test_ups_battery_mode_triggers(self):
        """UPS 电池模式触发"""
        mgr = RollbackManager()
        session = _mock_session()

        mock_result = MagicMock()
        mock_result.first.return_value = (1, "UPS-01")
        session.execute = AsyncMock(return_value=mock_result)

        result = await mgr._check_ups_active(1, session)
        assert result is not None
        assert result["value"] == 1


# ==================== 条件7: 湿度/露点 ====================

class TestHumidityDewPoint:
    @pytest.mark.asyncio
    async def test_no_th_data_no_trigger(self):
        """无温湿度数据不触发"""
        mgr = RollbackManager()
        session = _mock_session()

        mock_result = MagicMock()
        mock_result.all.return_value = []
        session.execute = AsyncMock(return_value=mock_result)

        result = await mgr._check_humidity_dew_point(1, session)
        assert result is None

    @pytest.mark.asyncio
    async def test_humidity_near_dew_point_triggers(self):
        """湿度接近露点触发"""
        mgr = RollbackManager()
        session = _mock_session()

        # T=12°C, RH=95% → 露点约 11.2°C → margin=0.8°C < 3°C
        mock_result = MagicMock()
        mock_result.all.return_value = [
            ("TH-Temp", 12.0, "°C"),
            ("TH-Humidity", 95.0, "%RH"),
        ]
        session.execute = AsyncMock(return_value=mock_result)

        result = await mgr._check_humidity_dew_point(1, session)
        assert result is not None
        assert result["value"] < DEFAULT_DEW_POINT_MARGIN

    @pytest.mark.asyncio
    async def test_humidity_safe_no_trigger(self):
        """湿度安全不触发"""
        mgr = RollbackManager()
        session = _mock_session()

        # T=20°C, RH=40% → 露点约 6°C → margin=14°C > 3°C
        mock_result = MagicMock()
        mock_result.all.return_value = [
            ("TH-Temp", 20.0, "°C"),
            ("TH-Humidity", 40.0, "%RH"),
        ]
        session.execute = AsyncMock(return_value=mock_result)

        result = await mgr._check_humidity_dew_point(1, session)
        assert result is None


# ==================== 回退触发与记录 ====================

class TestTriggerRollback:
    @pytest.mark.asyncio
    async def test_trigger_creates_event(self):
        """触发回退创建事件记录"""
        mgr = RollbackManager()
        session = _mock_session()

        mock_ws = MagicMock()
        mock_ws.broadcast_alarm = AsyncMock()

        with patch("app.services.websocket.ws_manager", mock_ws):
            result = {
                "value": 27.0,
                "threshold": 26.0,
                "action": "恢复正常制冷",
            }
            await mgr._trigger_rollback(
                1, RollbackTriggerType.TEMP_OVER_LIMIT, result, session
            )

            session.add.assert_called_once()
            session.flush.assert_called_once()

            # 检查内存状态
            state = mgr._zone_states[1][RollbackTriggerType.TEMP_OVER_LIMIT.value]
            assert state["active"] is True

    @pytest.mark.asyncio
    async def test_trigger_pushes_websocket(self):
        """触发回退推送 WebSocket"""
        mgr = RollbackManager()
        session = _mock_session()

        mock_ws = MagicMock()
        mock_ws.broadcast_alarm = AsyncMock()

        with patch(
            "app.services.websocket.ws_manager", mock_ws
        ):
            result = {"value": 27.0, "threshold": 26.0, "action": "恢复正常制冷"}
            await mgr._trigger_rollback(
                1, RollbackTriggerType.TEMP_OVER_LIMIT, result, session
            )

            mock_ws.broadcast_alarm.assert_called_once()
            call_args = mock_ws.broadcast_alarm.call_args[0][0]
            assert call_args["action"] == "rollback"
            assert call_args["zone_id"] == 1


# ==================== 自动恢复 ====================

class TestRecovery:
    @pytest.mark.asyncio
    async def test_recovery_starts_timer(self):
        """恢复开始计时"""
        mgr = RollbackManager()
        mgr._zone_states[1] = {
            RollbackTriggerType.TEMP_OVER_LIMIT.value: {
                "active": True,
                "since": datetime.now() - timedelta(minutes=30),
                "event_id": 99,
                "recovery_start": None,
            }
        }
        session = _mock_session()

        await mgr._try_recovery(1, RollbackTriggerType.TEMP_OVER_LIMIT, session)

        state = mgr._zone_states[1][RollbackTriggerType.TEMP_OVER_LIMIT.value]
        assert state["recovery_start"] is not None
        assert state["active"] is True  # 还在等待

    @pytest.mark.asyncio
    async def test_recovery_after_wait_time(self):
        """等待足够时间后恢复"""
        mgr = RollbackManager()
        mgr._zone_states[1] = {
            RollbackTriggerType.TEMP_OVER_LIMIT.value: {
                "active": True,
                "since": datetime.now() - timedelta(minutes=30),
                "event_id": 99,
                "recovery_start": datetime.now() - timedelta(seconds=RECOVERY_WAIT_TEMP + 1),
            }
        }
        session = _mock_session()

        # Mock event 查询
        mock_event = MagicMock(spec=RollbackEvent)
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_event
        session.execute = AsyncMock(return_value=mock_result)

        with patch(
            "app.services.websocket.ws_manager"
        ) as mock_ws:
            mock_ws.broadcast_alarm = AsyncMock()

            await mgr._try_recovery(1, RollbackTriggerType.TEMP_OVER_LIMIT, session)

            state = mgr._zone_states[1][RollbackTriggerType.TEMP_OVER_LIMIT.value]
            assert state["active"] is False
            assert mock_event.status == "resolved"


# ==================== 状态查询 ====================

class TestStatusQuery:
    def test_no_rollback(self):
        """无回退状态"""
        mgr = RollbackManager()
        status = mgr.get_zone_rollback_status(1)
        assert status["has_active_rollback"] is False
        assert status["active_triggers"] == []

    def test_active_rollback(self):
        """有活跃回退"""
        mgr = RollbackManager()
        mgr._zone_states[1] = {
            RollbackTriggerType.TEMP_OVER_LIMIT.value: {
                "active": True,
                "since": datetime.now(),
                "event_id": 1,
                "recovery_start": None,
            }
        }
        status = mgr.get_zone_rollback_status(1)
        assert status["has_active_rollback"] is True
        assert len(status["active_triggers"]) == 1

    def test_all_statuses(self):
        """查询所有 zone 状态"""
        mgr = RollbackManager()
        mgr._zone_states[1] = {}
        mgr._zone_states[2] = {
            RollbackTriggerType.SENSOR_OFFLINE.value: {
                "active": True,
                "since": datetime.now(),
                "event_id": 5,
                "recovery_start": None,
            }
        }
        statuses = mgr.get_all_statuses()
        assert len(statuses) == 2


# ==================== check_zone 综合测试 ====================

class TestCheckZone:
    @pytest.mark.asyncio
    async def test_check_zone_no_triggers(self):
        """全部条件正常，无触发"""
        mgr = RollbackManager()
        session = _mock_session()

        with patch.object(mgr, "_check_temp_over_limit", new_callable=AsyncMock, return_value=None), \
             patch.object(mgr, "_check_rate_over_predicted", new_callable=AsyncMock, return_value=None), \
             patch.object(mgr, "_check_rate_over_limit", new_callable=AsyncMock, return_value=None), \
             patch.object(mgr, "_check_ac_fault", new_callable=AsyncMock, return_value=None), \
             patch.object(mgr, "_check_sensor_offline", new_callable=AsyncMock, return_value=None), \
             patch.object(mgr, "_check_ups_active", new_callable=AsyncMock, return_value=None), \
             patch.object(mgr, "_check_humidity_dew_point", new_callable=AsyncMock, return_value=None):

            await mgr.check_zone(1, session)
            assert 1 in mgr._zone_states

    @pytest.mark.asyncio
    async def test_check_zone_with_trigger(self):
        """检测到触发条件"""
        mgr = RollbackManager()
        session = _mock_session()

        trigger_result = {"value": 27.0, "threshold": 26.0, "action": "恢复正常制冷"}

        with patch.object(mgr, "_check_temp_over_limit", new_callable=AsyncMock, return_value=trigger_result), \
             patch.object(mgr, "_check_rate_over_predicted", new_callable=AsyncMock, return_value=None), \
             patch.object(mgr, "_check_rate_over_limit", new_callable=AsyncMock, return_value=None), \
             patch.object(mgr, "_check_ac_fault", new_callable=AsyncMock, return_value=None), \
             patch.object(mgr, "_check_sensor_offline", new_callable=AsyncMock, return_value=None), \
             patch.object(mgr, "_check_ups_active", new_callable=AsyncMock, return_value=None), \
             patch.object(mgr, "_check_humidity_dew_point", new_callable=AsyncMock, return_value=None), \
             patch.object(mgr, "_trigger_rollback", new_callable=AsyncMock) as mock_trigger:

            await mgr.check_zone(1, session)
            mock_trigger.assert_called_once()
