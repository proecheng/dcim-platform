"""
RC 参数最小二乘自动校准 - 单元测试

Story 32.1: 测试 RCCalibrator 的事件收集、异常值过滤、拟合算法、
物理合理性检查、保存逻辑和整体校准流程
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch, PropertyMock
import math


# 条件导入 numpy/scipy（测试环境可能未安装）
try:
    import numpy as np
    from scipy.optimize import curve_fit

    _scipy_available = True
except ImportError:
    _scipy_available = False

pytestmark = pytest.mark.skipif(
    not _scipy_available, reason="scipy 未安装"
)


class TestFilterOutliers:
    """测试异常值过滤 (AC: #2)"""

    def setup_method(self):
        from app.services.precool.calibrator import RCCalibrator

        self.calibrator = RCCalibrator()

    def _make_sample(
        self, env_temp=22.0, power_change=10.0, before_power=100.0
    ):
        return {
            "t_data": [0, 0.083, 0.167],
            "T_data": [22.0, 22.5, 23.0],
            "T0": 22.0,
            "T_ambient": env_temp,
            "Q_IT": before_power,
            "power_change": power_change,
            "before_power": before_power,
            "env_temp": env_temp,
        }

    def test_normal_data_passes(self):
        """正常数据不被过滤"""
        samples = [self._make_sample() for _ in range(25)]
        filtered = self.calibrator._filter_outliers(samples)
        assert len(filtered) == 25

    def test_3sigma_filter(self):
        """3σ 过滤温度异常值"""
        samples = [self._make_sample(env_temp=22.0) for _ in range(30)]
        # 添加远离均值的异常点
        samples.append(self._make_sample(env_temp=50.0))
        samples.append(self._make_sample(env_temp=-5.0))
        filtered = self.calibrator._filter_outliers(samples)
        # 异常点应被 3σ 或环境温度范围过滤
        assert len(filtered) < len(samples)

    def test_extreme_power_filter(self):
        """极端事件过滤（power_change > 50%）"""
        samples = [self._make_sample() for _ in range(25)]
        # 功率变化 60%（超过 50% 阈值）
        samples.append(
            self._make_sample(power_change=60.0, before_power=100.0)
        )
        filtered = self.calibrator._filter_outliers(samples)
        assert len(filtered) == 25

    def test_env_temp_filter_low(self):
        """环境温度过滤 - 低于 10°C"""
        samples = [self._make_sample() for _ in range(25)]
        samples.append(self._make_sample(env_temp=5.0))
        filtered = self.calibrator._filter_outliers(samples)
        assert len(filtered) == 25

    def test_env_temp_filter_high(self):
        """环境温度过滤 - 高于 35°C"""
        samples = [self._make_sample() for _ in range(25)]
        samples.append(self._make_sample(env_temp=40.0))
        filtered = self.calibrator._filter_outliers(samples)
        assert len(filtered) == 25

    def test_empty_samples(self):
        """空样本列表"""
        filtered = self.calibrator._filter_outliers([])
        assert filtered == []

    def test_combined_filter(self):
        """组合过滤"""
        samples = [self._make_sample() for _ in range(25)]
        # 多种异常
        samples.append(self._make_sample(env_temp=5.0))  # 环境温度低
        samples.append(
            self._make_sample(power_change=60.0, before_power=100.0)
        )  # 极端事件
        samples.append(self._make_sample(env_temp=40.0))  # 环境温度高
        filtered = self.calibrator._filter_outliers(samples)
        assert len(filtered) == 25


class TestFitRCParameters:
    """测试拟合算法 (AC: #3)"""

    def setup_method(self):
        from app.services.precool.calibrator import RCCalibrator

        self.calibrator = RCCalibrator()

    def _make_ideal_samples(self, R=0.03, C=2.0, n_samples=30):
        """生成理想的温度响应数据用于拟合"""
        tau = R * C
        samples = []
        for i in range(n_samples):
            T_ambient = 20.0 + np.random.uniform(-1, 1)
            Q_IT = 80.0 + np.random.uniform(-5, 5)
            T_steady = T_ambient + Q_IT * R
            T0 = T_ambient + Q_IT * R * 0.5  # 初始温度低于稳态

            t_data = np.linspace(0, 2.0, 25)  # 0-2小时，25个点
            T_data = T_steady + (T0 - T_steady) * np.exp(-t_data / tau)
            # 添加小量噪声
            T_data += np.random.normal(0, 0.05, len(T_data))

            samples.append(
                {
                    "t_data": t_data.tolist(),
                    "T_data": T_data.tolist(),
                    "T0": float(T0),
                    "T_ambient": float(T_ambient),
                    "Q_IT": float(Q_IT),
                    "power_change": 10.0,
                    "before_power": 100.0,
                    "env_temp": float(T_ambient),
                }
            )
        return samples

    def test_normal_fitting(self):
        """正常拟合应返回合理的 R/C 值"""
        np.random.seed(42)
        samples = self._make_ideal_samples(R=0.03, C=2.0)
        result = self.calibrator._fit_rc_parameters(samples)

        assert "error" not in result
        assert 0.01 < result["R"] < 0.1  # R 在合理范围
        assert 0.5 < result["C"] < 10.0  # C 在合理范围
        assert result["r_squared"] > 0.5  # R² 较高

    def test_fitting_returns_r_squared(self):
        """拟合结果包含 R² 值"""
        np.random.seed(42)
        samples = self._make_ideal_samples()
        result = self.calibrator._fit_rc_parameters(samples)
        assert "r_squared" in result
        assert 0 <= result["r_squared"] <= 1

    def test_fitting_with_noisy_data(self):
        """噪声数据拟合（可能失败或 R² 较低）"""
        samples = []
        for _ in range(30):
            t_data = np.linspace(0, 2.0, 25).tolist()
            T_data = (np.random.uniform(18, 28, 25)).tolist()  # 纯噪声
            samples.append(
                {
                    "t_data": t_data,
                    "T_data": T_data,
                    "T0": 22.0,
                    "T_ambient": 20.0,
                    "Q_IT": 80.0,
                    "power_change": 10.0,
                    "before_power": 100.0,
                    "env_temp": 20.0,
                }
            )
        result = self.calibrator._fit_rc_parameters(samples)
        # 纯噪声数据可能拟合失败或 R² 很低
        if "error" not in result:
            assert result["r_squared"] < MIN_R_SQUARED_FOR_TEST


# 用于测试的 R² 阈值
MIN_R_SQUARED_FOR_TEST = 0.7


class TestValidateResult:
    """测试物理合理性检查 (AC: #4)"""

    def setup_method(self):
        from app.services.precool.calibrator import RCCalibrator

        self.calibrator = RCCalibrator()

    def test_valid_parameters(self):
        """合法参数通过检查"""
        # τ = 0.05 * 20 = 1.0h，在 [0.5, 8.0] 范围内
        result = self.calibrator._validate_result(R=0.05, C=20.0)
        assert result.get("valid") is True

    def test_R_zero(self):
        """R=0 失败"""
        result = self.calibrator._validate_result(R=0, C=2.0)
        assert result.get("error") == "invalid_R"

    def test_R_negative(self):
        """R<0 失败"""
        result = self.calibrator._validate_result(R=-0.01, C=2.0)
        assert result.get("error") == "invalid_R"

    def test_C_zero(self):
        """C=0 失败"""
        result = self.calibrator._validate_result(R=0.03, C=0)
        assert result.get("error") == "invalid_C"

    def test_C_negative(self):
        """C<0 失败"""
        result = self.calibrator._validate_result(R=0.03, C=-1.0)
        assert result.get("error") == "invalid_C"

    def test_tau_too_small(self):
        """τ=RC < 0.5h 失败"""
        # R=0.01, C=0.1 → τ=0.001 < 0.5
        result = self.calibrator._validate_result(R=0.01, C=0.1)
        assert result.get("error") == "tau_out_of_range"

    def test_tau_too_large(self):
        """τ=RC > 8h 失败"""
        # R=0.2, C=50 → τ=10 > 8
        result = self.calibrator._validate_result(R=0.2, C=50.0)
        assert result.get("error") == "tau_out_of_range"

    def test_tau_at_lower_boundary(self):
        """τ 刚好在下限（0.5h）"""
        # R=0.05, C=10 → τ=0.5
        result = self.calibrator._validate_result(R=0.05, C=10.0)
        assert result.get("valid") is True

    def test_tau_at_upper_boundary(self):
        """τ 刚好在上限（8h）"""
        # R=0.1, C=80 → τ=8.0
        result = self.calibrator._validate_result(R=0.1, C=80.0)
        assert result.get("valid") is True


class TestSaveCalibration:
    """测试保存逻辑 (AC: #4)"""

    @pytest.mark.asyncio
    async def test_save_creates_new_record(self):
        """保存校准结果创建新的 ThermalParameter 记录"""
        from app.services.precool.calibrator import RCCalibrator

        calibrator = RCCalibrator()
        session = AsyncMock()
        session.execute = AsyncMock(return_value=MagicMock())
        session.flush = AsyncMock()
        session.add = MagicMock()

        await calibrator._save_calibration(
            zone_id=1,
            R=0.03,
            C=2.0,
            r_squared=0.85,
            sample_count=25,
            session=session,
        )

        # 验证调用顺序：delete(旧inactive) → update(active→inactive) → flush → add(新active) → update(CoolingZone)
        assert session.execute.call_count == 3  # delete + update(active→inactive) + update(CoolingZone)
        assert session.flush.call_count == 1
        assert session.add.call_count == 1

        # 检查新记录的属性
        added_param = session.add.call_args[0][0]
        assert added_param.thermal_R == 0.03
        assert added_param.thermal_C == 2.0
        assert added_param.fitting_r_squared == 0.85
        assert added_param.fitting_method == "auto_fit"
        assert added_param.sample_count == 25
        assert added_param.is_active is True
        assert added_param.is_demo is False

    @pytest.mark.asyncio
    async def test_save_deactivates_old_records(self):
        """保存时先停用旧的活跃记录"""
        from app.services.precool.calibrator import RCCalibrator

        calibrator = RCCalibrator()
        session = AsyncMock()
        session.execute = AsyncMock(return_value=MagicMock())
        session.flush = AsyncMock()
        session.add = MagicMock()

        await calibrator._save_calibration(
            zone_id=1,
            R=0.03,
            C=2.0,
            r_squared=0.85,
            sample_count=25,
            session=session,
        )

        # 第一个 execute: delete inactive
        # 第二个 execute: update active → inactive
        # flush
        # add new
        # 第三个 execute: update CoolingZone
        calls = session.execute.call_args_list
        assert len(calls) == 3  # delete + update + update CoolingZone


class TestCalibrateFlow:
    """测试整体校准流程 (AC: #1-4)"""

    @pytest.mark.asyncio
    async def test_scipy_not_installed(self):
        """scipy 未安装时返回错误"""
        from app.services.precool.calibrator import RCCalibrator

        calibrator = RCCalibrator()
        with patch(
            "app.services.precool.calibrator._scipy_available", False
        ):
            result = await calibrator.calibrate(zone_id=1)
            assert result["error"] == "scipy_not_installed"

    @pytest.mark.asyncio
    async def test_no_events(self):
        """无校准事件时返回错误"""
        from app.services.precool.calibrator import RCCalibrator

        calibrator = RCCalibrator()

        with patch.object(
            calibrator,
            "_collect_calibration_events",
            new_callable=AsyncMock,
            return_value=[],
        ):
            with patch(
                "app.services.precool.calibrator.async_session"
            ) as mock_session_factory:
                mock_session = AsyncMock()
                mock_session_factory.return_value.__aenter__ = AsyncMock(
                    return_value=mock_session
                )
                mock_session_factory.return_value.__aexit__ = AsyncMock(
                    return_value=False
                )

                result = await calibrator.calibrate(zone_id=1)
                assert result["error"] == "no_events"

    @pytest.mark.asyncio
    async def test_insufficient_data(self):
        """数据不足时返回 insufficient_data"""
        from app.services.precool.calibrator import RCCalibrator

        calibrator = RCCalibrator()

        events = [{"timestamp": datetime.now(), "power_change": 10}]

        with patch.object(
            calibrator,
            "_collect_calibration_events",
            new_callable=AsyncMock,
            return_value=events,
        ):
            with patch.object(
                calibrator,
                "_get_temperature_point_ids",
                new_callable=AsyncMock,
                return_value=[1, 2],
            ):
                with patch.object(
                    calibrator,
                    "_build_fitting_samples",
                    new_callable=AsyncMock,
                    return_value=[{"env_temp": 22, "power_change": 10, "before_power": 100}] * 5,
                ):
                    with patch(
                        "app.services.precool.calibrator.async_session"
                    ) as mock_sf:
                        mock_s = AsyncMock()
                        mock_sf.return_value.__aenter__ = AsyncMock(
                            return_value=mock_s
                        )
                        mock_sf.return_value.__aexit__ = AsyncMock(
                            return_value=False
                        )
                        result = await calibrator.calibrate(zone_id=1)
                        assert result["error"] == "insufficient_data"
                        assert result["valid_samples"] < 20

    @pytest.mark.asyncio
    async def test_fitting_quality_low(self):
        """R² 低于阈值时返回错误"""
        from app.services.precool.calibrator import RCCalibrator

        calibrator = RCCalibrator()

        with patch.object(
            calibrator,
            "_collect_calibration_events",
            new_callable=AsyncMock,
            return_value=[{"timestamp": datetime.now()}] * 30,
        ):
            with patch.object(
                calibrator,
                "_get_temperature_point_ids",
                new_callable=AsyncMock,
                return_value=[1],
            ):
                samples = [
                    {
                        "t_data": [0, 0.1],
                        "T_data": [22, 22.5],
                        "T0": 22,
                        "T_ambient": 20,
                        "Q_IT": 80,
                        "power_change": 10,
                        "before_power": 100,
                        "env_temp": 22,
                    }
                ] * 25
                with patch.object(
                    calibrator,
                    "_build_fitting_samples",
                    new_callable=AsyncMock,
                    return_value=samples,
                ):
                    with patch.object(
                        calibrator,
                        "_filter_outliers",
                        return_value=samples,
                    ):
                        with patch.object(
                            calibrator,
                            "_fit_rc_parameters",
                            return_value={
                                "R": 0.05,
                                "C": 20.0,
                                "r_squared": 0.3,
                            },
                        ):
                            with patch(
                                "app.services.precool.calibrator.async_session"
                            ) as mock_sf:
                                mock_s = AsyncMock()
                                mock_sf.return_value.__aenter__ = AsyncMock(
                                    return_value=mock_s
                                )
                                mock_sf.return_value.__aexit__ = AsyncMock(
                                    return_value=False
                                )
                                result = await calibrator.calibrate(
                                    zone_id=1
                                )
                                assert (
                                    result["error"]
                                    == "fitting_quality_low"
                                )

    @pytest.mark.asyncio
    async def test_validation_failure(self):
        """物理合理性检查失败"""
        from app.services.precool.calibrator import RCCalibrator

        calibrator = RCCalibrator()

        with patch.object(
            calibrator,
            "_collect_calibration_events",
            new_callable=AsyncMock,
            return_value=[{"timestamp": datetime.now()}] * 30,
        ):
            with patch.object(
                calibrator,
                "_get_temperature_point_ids",
                new_callable=AsyncMock,
                return_value=[1],
            ):
                samples = [
                    {
                        "t_data": [0, 0.1],
                        "T_data": [22, 22.5],
                        "T0": 22,
                        "T_ambient": 20,
                        "Q_IT": 80,
                        "power_change": 10,
                        "before_power": 100,
                        "env_temp": 22,
                    }
                ] * 25
                with patch.object(
                    calibrator,
                    "_build_fitting_samples",
                    new_callable=AsyncMock,
                    return_value=samples,
                ):
                    with patch.object(
                        calibrator,
                        "_filter_outliers",
                        return_value=samples,
                    ):
                        # τ = 0.001 * 0.1 = 0.0001，远低于 0.5h
                        with patch.object(
                            calibrator,
                            "_fit_rc_parameters",
                            return_value={
                                "R": 0.001,
                                "C": 0.1,
                                "r_squared": 0.9,
                            },
                        ):
                            with patch(
                                "app.services.precool.calibrator.async_session"
                            ) as mock_sf:
                                mock_s = AsyncMock()
                                mock_sf.return_value.__aenter__ = AsyncMock(
                                    return_value=mock_s
                                )
                                mock_sf.return_value.__aexit__ = AsyncMock(
                                    return_value=False
                                )
                                result = await calibrator.calibrate(
                                    zone_id=1
                                )
                                assert (
                                    result["error"]
                                    == "tau_out_of_range"
                                )

    @pytest.mark.asyncio
    async def test_successful_calibration(self):
        """完整成功校准流程"""
        from app.services.precool.calibrator import RCCalibrator

        calibrator = RCCalibrator()

        with patch.object(
            calibrator,
            "_collect_calibration_events",
            new_callable=AsyncMock,
            return_value=[{"timestamp": datetime.now()}] * 30,
        ):
            with patch.object(
                calibrator,
                "_get_temperature_point_ids",
                new_callable=AsyncMock,
                return_value=[1],
            ):
                samples = [
                    {
                        "t_data": [0, 0.1],
                        "T_data": [22, 22.5],
                        "T0": 22,
                        "T_ambient": 20,
                        "Q_IT": 80,
                        "power_change": 10,
                        "before_power": 100,
                        "env_temp": 22,
                    }
                ] * 25
                with patch.object(
                    calibrator,
                    "_build_fitting_samples",
                    new_callable=AsyncMock,
                    return_value=samples,
                ):
                    with patch.object(
                        calibrator,
                        "_filter_outliers",
                        return_value=samples,
                    ):
                        with patch.object(
                            calibrator,
                            "_fit_rc_parameters",
                            return_value={
                                "R": 0.05,
                                "C": 20.0,
                                "r_squared": 0.85,
                            },
                        ):
                            with patch.object(
                                calibrator,
                                "_save_calibration",
                                new_callable=AsyncMock,
                            ):
                                with patch(
                                    "app.services.precool.calibrator.async_session"
                                ) as mock_sf:
                                    mock_s = AsyncMock()
                                    mock_sf.return_value.__aenter__ = (
                                        AsyncMock(return_value=mock_s)
                                    )
                                    mock_sf.return_value.__aexit__ = (
                                        AsyncMock(return_value=False)
                                    )
                                    result = await calibrator.calibrate(
                                        zone_id=1
                                    )
                                    assert result.get("success") is True
                                    assert result["R"] == 0.05
                                    assert result["C"] == 20.0
                                    assert result["r_squared"] == 0.85

    @pytest.mark.asyncio
    async def test_no_temperature_sensors(self):
        """无温度传感器时返回错误"""
        from app.services.precool.calibrator import RCCalibrator

        calibrator = RCCalibrator()

        with patch.object(
            calibrator,
            "_collect_calibration_events",
            new_callable=AsyncMock,
            return_value=[{"timestamp": datetime.now()}],
        ):
            with patch.object(
                calibrator,
                "_get_temperature_point_ids",
                new_callable=AsyncMock,
                return_value=[],
            ):
                with patch(
                    "app.services.precool.calibrator.async_session"
                ) as mock_sf:
                    mock_s = AsyncMock()
                    mock_sf.return_value.__aenter__ = AsyncMock(
                        return_value=mock_s
                    )
                    mock_sf.return_value.__aexit__ = AsyncMock(
                        return_value=False
                    )
                    result = await calibrator.calibrate(zone_id=1)
                    assert result["error"] == "no_temperature_sensors"


class TestMonthlyCalibration:
    """测试月度全区域校准 (AC: #5)"""

    @pytest.mark.asyncio
    async def test_monthly_calibration_iterates_zones(self):
        """月度校准遍历所有 zone"""
        from app.services.precool.calibrator import RCCalibrator

        calibrator = RCCalibrator()

        # Mock async_session 返回 zone_ids
        mock_result = MagicMock()
        mock_result.all.return_value = [(1,), (2,), (3,)]

        with patch(
            "app.services.precool.calibrator.async_session"
        ) as mock_sf:
            mock_s = AsyncMock()
            mock_s.execute = AsyncMock(return_value=mock_result)
            mock_sf.return_value.__aenter__ = AsyncMock(
                return_value=mock_s
            )
            mock_sf.return_value.__aexit__ = AsyncMock(return_value=False)

            with patch.object(
                calibrator,
                "calibrate",
                new_callable=AsyncMock,
                return_value={"success": True, "R": 0.03, "C": 2.0, "r_squared": 0.85, "sample_count": 25},
            ) as mock_calibrate:
                results = await calibrator.run_monthly_calibration()
                assert mock_calibrate.call_count == 3
                assert len(results["success"]) == 3

    @pytest.mark.asyncio
    async def test_monthly_calibration_continues_on_failure(self):
        """单 zone 失败不中断其他 zone"""
        from app.services.precool.calibrator import RCCalibrator

        calibrator = RCCalibrator()

        mock_result = MagicMock()
        mock_result.all.return_value = [(1,), (2,), (3,)]

        with patch(
            "app.services.precool.calibrator.async_session"
        ) as mock_sf:
            mock_s = AsyncMock()
            mock_s.execute = AsyncMock(return_value=mock_result)
            mock_sf.return_value.__aenter__ = AsyncMock(
                return_value=mock_s
            )
            mock_sf.return_value.__aexit__ = AsyncMock(return_value=False)

            # zone 1 成功, zone 2 失败, zone 3 成功
            side_effects = [
                {"success": True, "R": 0.03, "C": 2.0, "r_squared": 0.85, "sample_count": 25},
                {"error": "insufficient_data", "valid_samples": 5},
                {"success": True, "R": 0.04, "C": 1.5, "r_squared": 0.80, "sample_count": 22},
            ]
            with patch.object(
                calibrator,
                "calibrate",
                new_callable=AsyncMock,
                side_effect=side_effects,
            ):
                results = await calibrator.run_monthly_calibration()
                assert len(results["success"]) == 2
                assert len(results["skipped"]) == 1
                assert len(results["failed"]) == 0

    @pytest.mark.asyncio
    async def test_monthly_calibration_handles_exception(self):
        """zone 校准抛异常时不中断"""
        from app.services.precool.calibrator import RCCalibrator

        calibrator = RCCalibrator()

        mock_result = MagicMock()
        mock_result.all.return_value = [(1,), (2,)]

        with patch(
            "app.services.precool.calibrator.async_session"
        ) as mock_sf:
            mock_s = AsyncMock()
            mock_s.execute = AsyncMock(return_value=mock_result)
            mock_sf.return_value.__aenter__ = AsyncMock(
                return_value=mock_s
            )
            mock_sf.return_value.__aexit__ = AsyncMock(return_value=False)

            side_effects = [
                Exception("数据库连接失败"),
                {"success": True, "R": 0.03, "C": 2.0, "r_squared": 0.85, "sample_count": 25},
            ]
            with patch.object(
                calibrator,
                "calibrate",
                new_callable=AsyncMock,
                side_effect=side_effects,
            ):
                results = await calibrator.run_monthly_calibration()
                assert len(results["failed"]) == 1
                assert len(results["success"]) == 1
