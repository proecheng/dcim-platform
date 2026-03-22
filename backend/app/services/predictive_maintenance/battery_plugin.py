"""Battery 劣化分析插件 — Story 36.5

SOH 数据由 DegradationAnalyzer 从 BatterySOHRecord 表注入到 point_history["soh_percent"]，
本插件不直接查询数据库，保持与其他插件一致的 ABC 接口。
"""

import logging
from .base import DegradationPlugin, DegradationResult, _linear_regression_slope
from .registry import register_degradation_plugin
from .config import BATTERY_CONFIG

logger = logging.getLogger(__name__)


@register_degradation_plugin("battery")
class BatteryDegradationPlugin(DegradationPlugin):
    """电池组劣化分析插件"""

    def get_device_type(self) -> str:
        return "battery"

    def get_required_points(self) -> list[str]:
        return BATTERY_CONFIG["required_point_suffixes"]

    def get_optional_points(self) -> list[str]:
        return BATTERY_CONFIG["optional_point_suffixes"]

    async def analyze(
        self,
        device_id: int,
        point_history: dict[str, list],
        window_days: int = 30,
    ) -> DegradationResult:
        detail: dict = {}
        trend_factors: dict[str, float] = {}
        scores: list[tuple[str, float, float]] = []
        weights = BATTERY_CONFIG["weights"]

        total_count = 3  # soh + resistance + temperature
        available_count = 0

        # --- 1. SOH 评分（虚拟注入数据） ---
        soh_data = self._find_point_data(point_history, ["soh_percent"])
        if soh_data:
            available_count += 1
            # 取最新 SOH 值
            latest_soh = soh_data[-1][1]
            trend_factors["soh_percent"] = round(latest_soh, 2)

            # SOH → 分数映射（非线性）
            soh_score = self._soh_to_score(latest_soh)

            # SOH 趋势（如果有多个数据点）
            if len(soh_data) >= 2:
                timestamps = [d[0] for d in soh_data]
                values = [d[1] for d in soh_data]
                slope = _linear_regression_slope(timestamps, values)
                slope_per_month = slope * 30
                trend_factors["soh_slope_per_month"] = round(slope_per_month, 4)
                # SOH 下降趋势加速劣化评分
                if slope_per_month < -1.0:
                    soh_score = max(0, soh_score - abs(slope_per_month) * 5)

            scores.append(("soh", soh_score, weights["soh"]))
            detail["soh"] = {"latest_soh": latest_soh, "score": round(soh_score, 1), "data_points": len(soh_data)}
        else:
            detail["soh"] = {"status": "no_data"}

        # --- 2. 内阻增长趋势（必需点位） ---
        resistance_data = self._find_point_data(point_history, ["internal_resistance"])
        if resistance_data and len(resistance_data) >= 2:
            available_count += 1
            timestamps = [d[0] for d in resistance_data]
            values = [d[1] for d in resistance_data]
            slope = _linear_regression_slope(timestamps, values)
            slope_per_month = slope * 30
            trend_factors["resistance_slope_per_month"] = round(slope_per_month, 4)

            # 内阻上升 → 劣化
            if slope_per_month > 0.5:
                r_score = max(0, 100 - slope_per_month * 40)
            elif slope_per_month > 0:
                r_score = max(60, 100 - slope_per_month * 20)
            else:
                r_score = 100.0
            scores.append(("resistance_trend", r_score, weights["resistance_trend"]))
            detail["resistance"] = {"slope_per_month": slope_per_month, "score": r_score, "data_points": len(resistance_data)}
        else:
            detail["resistance"] = {"status": "no_data"}

        # --- 3. 温度趋势（可选） ---
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
        data_sufficiency = self._determine_sufficiency(available_count, soh_data, resistance_data, window_days)

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

    @staticmethod
    def _soh_to_score(soh_percent: float) -> float:
        """SOH 百分比 → 劣化评分映射（非线性）

        100% → 100分, 80% → 80分, 60% → 40分, 40% → 10分
        """
        soh_percent = max(0.0, min(100.0, soh_percent))
        if soh_percent >= 80:
            return soh_percent  # 线性 80~100
        elif soh_percent >= 60:
            return 80 - (80 - soh_percent) * 2  # 加速下降
        elif soh_percent >= 40:
            return 40 - (60 - soh_percent) * 1.5
        else:
            return max(0, 10 - (40 - soh_percent) * 0.5)

    def _determine_sufficiency(
        self, available_count: int, soh_data: list | None,
        resistance_data: list | None, window_days: int,
    ) -> str:
        """Battery 数据充分度判定"""
        if not soh_data and not resistance_data:
            return "minimal"

        # 有 SOH + 内阻数据
        has_soh = bool(soh_data)
        has_resistance = bool(resistance_data) and len(resistance_data) >= 2

        if has_soh and has_resistance and available_count >= 2:
            # 检查内阻数据时间跨度
            if resistance_data and len(resistance_data) >= 2:
                day_span = resistance_data[-1][0] - resistance_data[0][0]
                if day_span >= window_days * 0.8:
                    return "full"
            return "partial"
        elif has_soh or has_resistance:
            return "partial"
        return "minimal"
