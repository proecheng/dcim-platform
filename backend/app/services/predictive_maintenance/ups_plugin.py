"""UPS 劣化分析插件 — Story 36.5"""

import math
import logging
from .base import DegradationPlugin, DegradationResult, _linear_regression_slope
from .registry import register_degradation_plugin
from .config import UPS_CONFIG

logger = logging.getLogger(__name__)


@register_degradation_plugin("ups")
class UPSDegradationPlugin(DegradationPlugin):
    """UPS 主机劣化分析插件"""

    def get_device_type(self) -> str:
        return "ups"

    def get_required_points(self) -> list[str]:
        return UPS_CONFIG["required_point_suffixes"]

    def get_optional_points(self) -> list[str]:
        return UPS_CONFIG["optional_point_suffixes"]

    async def analyze(
        self,
        device_id: int,
        point_history: dict[str, list],
        window_days: int = 30,
    ) -> DegradationResult:
        detail: dict = {}
        trend_factors: dict[str, float] = {}
        scores: list[tuple[str, float, float]] = []
        weights = UPS_CONFIG["weights"]

        required_count = len(UPS_CONFIG["required_point_suffixes"])
        optional_count_max = len(UPS_CONFIG["optional_point_suffixes"])
        total_count = required_count + optional_count_max
        available_count = 0

        # --- 1. 输出电压稳定性（必需） ---
        voltage_data = self._find_point_data(point_history, ["output_voltage"])
        if voltage_data and len(voltage_data) >= 2:
            available_count += 1
            score, info = self._analyze_voltage_stability(voltage_data)
            scores.append(("voltage_stability", score, weights["voltage_stability"]))
            trend_factors["voltage_std_trend"] = info.get("std_slope", 0.0)
            detail["voltage_stability"] = info
        else:
            detail["voltage_stability"] = {"status": "no_data"}

        # --- 2. 效率趋势（可选） ---
        efficiency_data = self._find_point_data(point_history, ["efficiency"])
        if efficiency_data and len(efficiency_data) >= 2:
            available_count += 1
            timestamps = [d[0] for d in efficiency_data]
            values = [d[1] for d in efficiency_data]
            slope = _linear_regression_slope(timestamps, values)
            slope_per_month = slope * 30
            trend_factors["efficiency_slope_per_month"] = round(slope_per_month, 4)

            threshold = UPS_CONFIG["efficiency_slope_threshold_per_month"]
            if slope_per_month < threshold:
                eff_score = max(0, 100 + slope_per_month * 40)
            elif slope_per_month < 0:
                eff_score = max(60, 100 + slope_per_month * 40)
            else:
                eff_score = 100.0
            scores.append(("efficiency_trend", eff_score, weights["efficiency_trend"]))
            detail["efficiency"] = {"slope_per_month": slope_per_month, "score": eff_score, "data_points": len(efficiency_data)}
        else:
            detail["efficiency"] = {"status": "no_data"}

        # --- 3. 切换次数（可选） ---
        transfer_data = self._find_point_data(point_history, ["transfer_count"])
        if transfer_data and len(transfer_data) >= 2:
            available_count += 1
            values = [d[1] for d in transfer_data]
            # 脉冲型：统计非零值次数
            transfer_events = sum(1 for v in values if v > 0)
            trend_factors["transfer_count"] = float(transfer_events)

            threshold = UPS_CONFIG["transfer_count_threshold"]
            if transfer_events > threshold * 2:
                tc_score = max(0, 100 - (transfer_events - threshold) * 10)
            elif transfer_events > threshold:
                tc_score = max(40, 100 - (transfer_events - threshold) * 20)
            else:
                tc_score = 100.0
            scores.append(("transfer_count", tc_score, weights["transfer_count"]))
            detail["transfer_count"] = {"events": transfer_events, "score": tc_score}
        else:
            detail["transfer_count"] = {"status": "no_data"}

        # --- 4. 温度趋势（可选） ---
        temp_data = self._find_point_data(point_history, ["temperature"])
        if temp_data and len(temp_data) >= 2:
            available_count += 1
            timestamps = [d[0] for d in temp_data]
            values = [d[1] for d in temp_data]
            slope = _linear_regression_slope(timestamps, values)
            slope_per_month = slope * 30
            trend_factors["temperature_slope_per_month"] = round(slope_per_month, 4)

            if slope_per_month > 2.0:
                temp_score = max(0, 100 - slope_per_month * 20)
            elif slope_per_month > 0:
                temp_score = max(60, 100 - slope_per_month * 10)
            else:
                temp_score = 100.0
            scores.append(("temperature", temp_score, weights["temperature"]))
            detail["temperature"] = {"slope_per_month": slope_per_month, "score": temp_score, "data_points": len(temp_data)}
        else:
            detail["temperature"] = {"status": "no_data"}

        # --- 综合评分 ---
        data_sufficiency = self._determine_sufficiency(available_count, voltage_data, window_days)

        if not scores:
            return DegradationResult(
                device_id=device_id, score=100.0, confidence=0.0,
                available_points=0, total_points=total_count,
                trend_factors=trend_factors, primary_concern=None,
                data_sufficiency="minimal", detail=detail,
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

    def _analyze_voltage_stability(self, voltage_data: list) -> tuple[float, dict]:
        """分段计算输出电压标准差，检查标准差增大趋势"""
        segment_count = UPS_CONFIG["voltage_segment_count"]
        min_segments = UPS_CONFIG["min_segments_for_trend"]
        n = len(voltage_data)
        seg_size = max(1, n // segment_count)

        segment_stds = []
        for i in range(0, n, seg_size):
            seg = voltage_data[i:i + seg_size]
            if len(seg) >= 2:
                vals = [d[1] for d in seg]
                mean = sum(vals) / len(vals)
                variance = sum((v - mean) ** 2 for v in vals) / len(vals)
                segment_stds.append(math.sqrt(variance))

        info: dict = {"segments": len(segment_stds)}

        if len(segment_stds) < min_segments:
            # 数据不足以做趋势分析，使用整体标准差
            all_vals = [d[1] for d in voltage_data]
            mean = sum(all_vals) / len(all_vals)
            overall_std = math.sqrt(sum((v - mean) ** 2 for v in all_vals) / len(all_vals))
            info["overall_std"] = round(overall_std, 4)
            threshold = UPS_CONFIG["voltage_std_threshold"]
            if overall_std > threshold:
                score = max(0, 100 - (overall_std - threshold) * 50)
            else:
                score = 100.0
            info["score"] = score
            return score, info

        # 检查标准差增大趋势
        timestamps = list(range(len(segment_stds)))
        std_slope = _linear_regression_slope([float(t) for t in timestamps], segment_stds)
        info["std_slope"] = round(std_slope, 6)
        info["segment_stds"] = [round(s, 4) for s in segment_stds]

        last_std = segment_stds[-1]
        threshold = UPS_CONFIG["voltage_std_threshold"]

        if last_std > threshold and std_slope > 0:
            score = max(0, 100 - last_std * 30 - std_slope * 100)
        elif last_std > threshold:
            score = max(30, 100 - last_std * 20)
        elif std_slope > 0.1:
            score = max(50, 100 - std_slope * 200)
        else:
            score = 100.0

        info["score"] = round(score, 1)
        return round(score, 1), info

    def _determine_sufficiency(
        self, available_count: int, voltage_data: list | None, window_days: int
    ) -> str:
        """UPS 数据充分度判定"""
        if not voltage_data:
            return "minimal"

        if len(voltage_data) >= 2:
            day_span = voltage_data[-1][0] - voltage_data[0][0]
        else:
            day_span = 0

        has_enough_days = day_span >= window_days * 0.8
        optional_avail = available_count - 1  # 减去电压（必需）

        if has_enough_days and optional_avail >= 2:
            return "full"
        elif voltage_data:
            return "partial"
        return "minimal"
