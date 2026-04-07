"""HVAC 劣化分析插件 — Story 36.1"""

import logging
from .base import DegradationPlugin, DegradationResult, _linear_regression_slope
from .registry import register_degradation_plugin
from .config import HVAC_CONFIG

logger = logging.getLogger(__name__)


@register_degradation_plugin("hvac")
class HVACDegradationPlugin(DegradationPlugin):
    """空调（HVAC）劣化分析插件"""

    def get_device_type(self) -> str:
        return "hvac"

    def get_required_points(self) -> list[str]:
        return HVAC_CONFIG["required_point_suffixes"]

    def get_optional_points(self) -> list[str]:
        return HVAC_CONFIG["optional_point_suffixes"]

    async def analyze(
        self,
        device_id: int,
        point_history: dict[str, list],
        window_days: int = 30,
    ) -> DegradationResult:
        """执行 HVAC 劣化分析

        point_history: {point_code_suffix: [(day_offset, value), ...]}
        """
        detail: dict = {}
        trend_factors: dict[str, float] = {}
        scores: list[tuple[str, float, float]] = []  # (指标名, 分值0~100, 权重)
        weights = HVAC_CONFIG["weights"]

        # 统计可用数据
        available_count = 0
        total_count = (
            len(HVAC_CONFIG["required_point_suffixes"])
            + len(HVAC_CONFIG["compressor_status_suffixes"][:1])
            + len(HVAC_CONFIG["optional_point_suffixes"])
        )

        # --- 1. 回风温度偏差趋势 ---
        return_temp_data = self._find_point_data(point_history, HVAC_CONFIG["required_point_suffixes"])
        if return_temp_data and len(return_temp_data) >= 2:
            available_count += 1
            timestamps = [d[0] for d in return_temp_data]
            values = [d[1] for d in return_temp_data]
            slope = _linear_regression_slope(timestamps, values)
            slope_per_month = slope * 30
            trend_factors["return_temp_slope_per_month"] = round(slope_per_month, 4)

            # 斜率 > 0 表示回风温度上升趋势（劣化）
            if slope_per_month > 0.5:
                temp_score = max(0, 100 - slope_per_month * 40)
            elif slope_per_month > 0:
                temp_score = max(50, 100 - slope_per_month * 20)
            else:
                temp_score = 100.0
            scores.append(("return_temp_trend", temp_score, weights["return_temp_trend"]))
            detail["return_temp"] = {
                "slope_per_month": slope_per_month,
                "score": temp_score,
                "data_points": len(return_temp_data),
            }
        else:
            detail["return_temp"] = {"status": "no_data"}

        # --- 2. 压缩机运行状态（启停频率） ---
        compressor_data = self._find_point_data(point_history, HVAC_CONFIG["compressor_status_suffixes"])
        if compressor_data and len(compressor_data) >= 2:
            available_count += 1
            values = [d[1] for d in compressor_data]
            # 计算状态切换次数
            toggles = sum(1 for i in range(1, len(values)) if values[i] != values[i - 1])
            toggle_rate = toggles / max(1, len(values))
            trend_factors["compressor_toggle_rate"] = round(toggle_rate, 4)

            # 高频启停（>10%切换率）劣化信号
            if toggle_rate > 0.2:
                comp_score = max(0, 100 - (toggle_rate - 0.1) * 500)
            elif toggle_rate > 0.1:
                comp_score = max(50, 100 - (toggle_rate - 0.05) * 200)
            else:
                comp_score = 100.0
            scores.append(("compressor_status", comp_score, weights["compressor_status"]))
            detail["compressor_status"] = {"toggle_rate": toggle_rate, "score": comp_score, "toggles": toggles}
        else:
            detail["compressor_status"] = {"status": "no_data"}

        # --- 3. COP 趋势（可选） ---
        cop_data = self._find_point_data(point_history, ["cop"])
        if cop_data and len(cop_data) >= 2:
            available_count += 1
            timestamps = [d[0] for d in cop_data]
            values = [d[1] for d in cop_data]
            slope = _linear_regression_slope(timestamps, values)
            slope_per_month = slope * 30
            trend_factors["cop_slope_per_month"] = round(slope_per_month, 4)

            threshold = HVAC_CONFIG["cop_slope_threshold_per_month"]
            if slope_per_month < threshold:
                cop_score = max(0, 100 + (slope_per_month - threshold) * 200)
            elif slope_per_month < 0:
                cop_score = max(60, 100 + slope_per_month * 100)
            else:
                cop_score = 100.0
            scores.append(("cop_trend", cop_score, weights["cop_trend"]))
            detail["cop"] = {"slope_per_month": slope_per_month, "score": cop_score, "data_points": len(cop_data)}
        else:
            detail["cop"] = {"status": "no_data"}

        # --- 4. 压缩机运行时长（可选） ---
        hours_data = self._find_point_data(point_history, ["compressor_hours"])
        if hours_data:
            available_count += 1
            max_hours = max(d[1] for d in hours_data)
            maint_hours = HVAC_CONFIG["compressor_maintenance_hours"]
            trend_factors["compressor_hours"] = round(max_hours, 1)

            ratio = max_hours / maint_hours
            if ratio > 1.0:
                hours_score = max(0, 100 - (ratio - 1.0) * 200)
            elif ratio > 0.8:
                hours_score = max(50, 100 - (ratio - 0.5) * 100)
            else:
                hours_score = 100.0
            scores.append(("compressor_hours", hours_score, weights["compressor_hours"]))
            detail["compressor_hours"] = {
                "max_hours": max_hours,
                "maintenance_threshold": maint_hours,
                "score": hours_score,
            }
        else:
            detail["compressor_hours"] = {"status": "no_data"}

        # --- 5. 滤网告警频率（可选） ---
        filter_data = self._find_point_data(point_history, ["filter_alarm"])
        if filter_data:
            available_count += 1
            values = [d[1] for d in filter_data]
            alarm_count = sum(1 for v in values if v >= 1.0)
            alarm_rate = alarm_count / max(1, len(values))
            trend_factors["filter_alarm_rate"] = round(alarm_rate, 4)

            if alarm_rate > 0.3:
                filter_score = max(0, 100 - alarm_rate * 200)
            elif alarm_rate > 0.1:
                filter_score = max(50, 100 - alarm_rate * 100)
            else:
                filter_score = 100.0
            scores.append(("filter_alarm", filter_score, weights["filter_alarm"]))
            detail["filter_alarm"] = {"alarm_rate": alarm_rate, "alarm_count": alarm_count, "score": filter_score}
        else:
            detail["filter_alarm"] = {"status": "no_data"}

        # --- 综合评分 ---
        data_sufficiency = self._determine_sufficiency(available_count, return_temp_data, window_days)

        if not scores:
            return DegradationResult(
                device_id=device_id,
                score=100.0,
                confidence=0.0,
                available_points=0,
                total_points=total_count,
                trend_factors=trend_factors,
                primary_concern=None,
                data_sufficiency="minimal",
                detail=detail,
            )

        # 加权平均（仅对有数据的指标）
        total_weight = sum(w for _, _, w in scores)
        weighted_score = sum(s * w for _, s, w in scores) / total_weight if total_weight > 0 else 100.0

        # 置信度基于数据充分度
        if data_sufficiency == "full":
            confidence = min(1.0, available_count / total_count * 1.2)
        elif data_sufficiency == "partial":
            confidence = min(0.6, available_count / total_count)
        else:
            confidence = 0.0

        # 找出最差指标
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

    def _determine_sufficiency(self, available_count: int, return_temp_data: list | None, window_days: int) -> str:
        """判定数据充分度"""
        if not return_temp_data:
            return "minimal"

        # 检查数据天数跨度
        if len(return_temp_data) >= 2:
            day_span = return_temp_data[-1][0] - return_temp_data[0][0]
        else:
            day_span = 0

        has_enough_days = day_span >= window_days * 0.8
        optional_count = available_count - 1  # 减去回风温度（必需）

        if has_enough_days and optional_count >= 2:
            return "full"
        elif return_temp_data:
            return "partial"
        return "minimal"
