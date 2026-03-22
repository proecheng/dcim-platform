"""PDU 劣化分析插件 — Story 36.5"""

import math
import logging
from .base import DegradationPlugin, DegradationResult, _linear_regression_slope
from .registry import register_degradation_plugin
from .config import PDU_CONFIG

logger = logging.getLogger(__name__)


@register_degradation_plugin("pdu")
class PDUDegradationPlugin(DegradationPlugin):
    """PDU 劣化分析插件"""

    def get_device_type(self) -> str:
        return "pdu"

    def get_required_points(self) -> list[str]:
        return PDU_CONFIG["required_point_suffixes"]

    def get_optional_points(self) -> list[str]:
        return PDU_CONFIG["optional_point_suffixes"]

    async def analyze(
        self,
        device_id: int,
        point_history: dict[str, list],
        window_days: int = 30,
    ) -> DegradationResult:
        detail: dict = {}
        trend_factors: dict[str, float] = {}
        scores: list[tuple[str, float, float]] = []
        weights = PDU_CONFIG["weights"]

        required_count = len(PDU_CONFIG["required_point_suffixes"])
        optional_count_max = len(PDU_CONFIG["optional_point_suffixes"])
        total_count = required_count + optional_count_max
        available_count = 0

        # --- 1. 负载率趋势（必需） ---
        load_data = self._find_point_data(point_history, ["load_percentage"])
        zero_load = False
        if load_data and len(load_data) >= 2:
            available_count += 1
            values = [d[1] for d in load_data]
            load_mean = sum(values) / len(values)

            # 零负载保护：均值 < 1% 时不评分
            if load_mean < 1.0:
                zero_load = True
                detail["load_trend"] = {"status": "zero_load", "mean": round(load_mean, 2)}
            else:
                timestamps = [d[0] for d in load_data]
                slope = _linear_regression_slope(timestamps, values)
                slope_per_month = slope * 30
                trend_factors["load_slope_per_month"] = round(slope_per_month, 4)
                trend_factors["load_mean"] = round(load_mean, 2)

                threshold = PDU_CONFIG["load_high_threshold"]
                if load_mean > threshold and slope_per_month > 0:
                    load_score = max(0, 100 - (load_mean - threshold) * 2 - slope_per_month * 10)
                elif load_mean > threshold:
                    load_score = max(30, 100 - (load_mean - threshold) * 2)
                elif slope_per_month > 1.0:
                    load_score = max(50, 100 - slope_per_month * 10)
                else:
                    load_score = 100.0
                scores.append(("load_trend", load_score, weights["load_trend"]))
                detail["load_trend"] = {
                    "mean": round(load_mean, 2), "slope_per_month": slope_per_month,
                    "score": load_score, "data_points": len(load_data),
                }
        else:
            detail["load_trend"] = {"status": "no_data"}

        # --- 2. 电压稳定性（必需） ---
        voltage_data = self._find_point_data(point_history, ["voltage"])
        if voltage_data and len(voltage_data) >= 2:
            available_count += 1
            values = [d[1] for d in voltage_data]
            mean = sum(values) / len(values)
            std = math.sqrt(sum((v - mean) ** 2 for v in values) / len(values))
            trend_factors["voltage_std"] = round(std, 4)

            threshold = PDU_CONFIG["voltage_std_threshold"]
            if std > threshold:
                v_score = max(0, 100 - (std - threshold) * 200)
            else:
                v_score = 100.0
            scores.append(("voltage_stability", v_score, weights["voltage_stability"]))
            detail["voltage_stability"] = {"std": round(std, 4), "score": v_score, "data_points": len(voltage_data)}
        else:
            detail["voltage_stability"] = {"status": "no_data"}

        # --- 3. 谐波畸变率趋势（可选） ---
        thd_data = self._find_point_data(point_history, ["thd"])
        if thd_data and len(thd_data) >= 2:
            available_count += 1
            timestamps = [d[0] for d in thd_data]
            values = [d[1] for d in thd_data]
            slope = _linear_regression_slope(timestamps, values)
            slope_per_month = slope * 30
            trend_factors["thd_slope_per_month"] = round(slope_per_month, 4)

            threshold = PDU_CONFIG["thd_slope_threshold_per_month"]
            if slope_per_month > threshold:
                thd_score = max(0, 100 - (slope_per_month - threshold) * 100)
            elif slope_per_month > 0:
                thd_score = max(60, 100 - slope_per_month * 50)
            else:
                thd_score = 100.0
            scores.append(("thd_trend", thd_score, weights["thd_trend"]))
            detail["thd"] = {"slope_per_month": slope_per_month, "score": thd_score, "data_points": len(thd_data)}
        else:
            detail["thd"] = {"status": "no_data"}

        # --- 4. 温升异常（可选） ---
        temp_data = self._find_point_data(point_history, ["temperature_rise"])
        if temp_data and len(temp_data) >= 2:
            available_count += 1
            timestamps = [d[0] for d in temp_data]
            values = [d[1] for d in temp_data]
            slope = _linear_regression_slope(timestamps, values)
            slope_per_month = slope * 30
            trend_factors["temp_rise_slope_per_month"] = round(slope_per_month, 4)

            if slope_per_month > 2.0:
                tr_score = max(0, 100 - slope_per_month * 20)
            elif slope_per_month > 0:
                tr_score = max(60, 100 - slope_per_month * 10)
            else:
                tr_score = 100.0
            scores.append(("temperature_rise", tr_score, weights["temperature_rise"]))
            detail["temperature_rise"] = {"slope_per_month": slope_per_month, "score": tr_score, "data_points": len(temp_data)}
        else:
            detail["temperature_rise"] = {"status": "no_data"}

        # --- 综合评分 ---
        data_sufficiency = self._determine_sufficiency(available_count, load_data, voltage_data, window_days, zero_load)

        if not scores:
            return DegradationResult(
                device_id=device_id, score=100.0, confidence=0.0,
                available_points=0, total_points=total_count,
                trend_factors=trend_factors, primary_concern=None,
                data_sufficiency="minimal" if not zero_load else "partial",
                detail=detail,
            )

        total_weight = sum(w for _, _, w in scores)
        weighted_score = sum(s * w for _, s, w in scores) / total_weight if total_weight > 0 else 100.0

        if data_sufficiency == "full":
            confidence = min(1.0, available_count / total_count * 1.2)
        elif data_sufficiency == "partial":
            confidence = min(0.6, available_count / total_count)
        else:
            confidence = 0.0

        primary_concern = None
        if scores:
            worst = min(scores, key=lambda x: x[1])
            if worst[1] < 80:
                primary_concern = worst[0]

        return DegradationResult(
            device_id=device_id,
            score=round(weighted_score, 1),
            confidence=round(confidence, 2),
            available_points=available_count,
            total_points=total_count,
            trend_factors=trend_factors,
            primary_concern=primary_concern,
            data_sufficiency=data_sufficiency,
            detail=detail,
        )

    def _determine_sufficiency(
        self, available_count: int, load_data: list | None,
        voltage_data: list | None, window_days: int, zero_load: bool,
    ) -> str:
        """PDU 数据充分度判定"""
        if not load_data and not voltage_data:
            return "minimal"

        if zero_load:
            return "partial"

        # 取负载率或电压数据中的 day_span
        primary = load_data or voltage_data
        if primary and len(primary) >= 2:
            day_span = primary[-1][0] - primary[0][0]
        else:
            day_span = 0

        has_enough_days = day_span >= window_days * 0.8
        optional_avail = max(0, available_count - 2)  # 减去负载率+电压（必需）

        if has_enough_days and optional_avail >= 1:
            return "full"
        elif load_data or voltage_data:
            return "partial"
        return "minimal"
