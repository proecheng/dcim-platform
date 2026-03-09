"""
灾难恢复演练服务 - Story 26.7
验证熔断降级和 FallbackStore 机制
"""

import asyncio
import json
import logging
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.config import SystemConfig
from app.models.report import ReportRecord
from app.services.diagnosis.circuit_breaker import CircuitBreaker, BreakerState
from app.services.diagnosis.fallback_store import DiagnosisFallbackStore

logger = logging.getLogger(__name__)

VALID_SCENARIOS = {"circuit_breaker_degradation", "db_timeout_fallback"}

DEFAULT_SCHEDULE = {
    "enabled": False,
    "cron_expression": "0 2 * * 0",
    "window_minutes": 120,
    "scenarios": ["circuit_breaker_degradation", "db_timeout_fallback"],
    "confirmed": False,
    "confirmed_by": None,
    "confirmed_at": None,
}

SCENARIO_TIMEOUT = 120.0  # 秒


class ChaosDrillService:
    """灾难恢复演练服务"""

    # 类级别状态（进程级共享）
    is_drill_active: bool = False
    _current_drill_id: Optional[str] = None
    _drill_lock: Optional[asyncio.Lock] = None
    _stop_requested: bool = False

    @classmethod
    def _ensure_lock(cls):
        if cls._drill_lock is None:
            cls._drill_lock = asyncio.Lock()

    def __init__(self, db: AsyncSession):
        self.db = db

    # ---- 计划管理 ----

    async def get_drill_schedule(self) -> dict:
        """获取演练计划配置"""
        stmt = select(SystemConfig).where(
            SystemConfig.config_group == "chaos_drill",
            SystemConfig.config_key == "schedule",
        )
        result = await self.db.execute(stmt)
        config = result.scalar_one_or_none()

        if not config or not config.config_value:
            return {**DEFAULT_SCHEDULE}

        try:
            data = json.loads(config.config_value)
            # 合并默认值
            merged = {**DEFAULT_SCHEDULE, **data}
            return merged
        except (json.JSONDecodeError, TypeError):
            return {**DEFAULT_SCHEDULE}

    async def update_drill_schedule(self, updates: dict) -> dict:
        """更新演练计划"""
        # 验证场景名称
        if "scenarios" in updates and updates["scenarios"] is not None:
            invalid = set(updates["scenarios"]) - VALID_SCENARIOS
            if invalid:
                raise ValueError(f"无效的演练场景: {invalid}")

        schedule = await self.get_drill_schedule()

        for key in ("enabled", "cron_expression", "window_minutes", "scenarios"):
            if key in updates and updates[key] is not None:
                schedule[key] = updates[key]

        # 更新后需要重新确认
        schedule["confirmed"] = False
        schedule["confirmed_by"] = None
        schedule["confirmed_at"] = None

        await self._save_schedule(schedule)
        return schedule

    async def confirm_drill_schedule(self, user_id: int) -> dict:
        """确认演练计划"""
        schedule = await self.get_drill_schedule()

        if not schedule.get("enabled"):
            raise ValueError("请先启用演练计划")

        schedule["confirmed"] = True
        schedule["confirmed_by"] = user_id
        schedule["confirmed_at"] = datetime.now(timezone.utc).isoformat()

        await self._save_schedule(schedule)
        return schedule

    async def _save_schedule(self, schedule: dict):
        """保存演练计划到 SystemConfig"""
        stmt = select(SystemConfig).where(
            SystemConfig.config_group == "chaos_drill",
            SystemConfig.config_key == "schedule",
        )
        result = await self.db.execute(stmt)
        config = result.scalar_one_or_none()

        value = json.dumps(schedule, ensure_ascii=False)

        if config:
            config.config_value = value
            config.value_type = "json"
        else:
            config = SystemConfig(
                config_group="chaos_drill",
                config_key="schedule",
                config_value=value,
                value_type="json",
                description="灾难恢复演练计划配置",
                is_editable=True,
            )
            self.db.add(config)

        await self.db.commit()

    # ---- 演练执行 ----

    async def trigger_drill(
        self, scenarios: List[str], breaker: Optional[CircuitBreaker] = None
    ) -> str:
        """手动触发演练"""
        # 验证场景
        invalid = set(scenarios) - VALID_SCENARIOS
        if invalid:
            raise ValueError(f"无效的演练场景: {invalid}")

        # 并发保护
        self.__class__._ensure_lock()
        if self.__class__.is_drill_active:
            raise ValueError("已有演练正在执行，请等待完成或终止后再试")

        drill_id = f"drill-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}"

        # 在后台执行演练
        asyncio.create_task(self._execute_drill(drill_id, scenarios, breaker))

        return drill_id

    async def _execute_drill(
        self,
        drill_id: str,
        scenarios: List[str],
        breaker: Optional[CircuitBreaker] = None,
    ):
        """执行演练（内部方法）"""
        self.__class__._ensure_lock()
        async with self.__class__._drill_lock:
            # 二次检查（防止 TOCTOU 竞态）
            if self.__class__.is_drill_active:
                logger.warning(f"演练 {drill_id} 跳过: 已有演练在执行")
                return

            self.__class__.is_drill_active = True
            self.__class__._current_drill_id = drill_id
            self.__class__._stop_requested = False

            drill_start = time.perf_counter()
            start_time = datetime.now(timezone.utc)
            scenario_results = []

            try:
                for scenario_name in scenarios:
                    if self.__class__._stop_requested:
                        break

                    try:
                        result = await asyncio.wait_for(
                            self._run_scenario(scenario_name, breaker),
                            timeout=SCENARIO_TIMEOUT,
                        )
                    except asyncio.TimeoutError:
                        result = {
                            "name": scenario_name,
                            "status": "timeout",
                            "details": {"error": f"场景超时 ({SCENARIO_TIMEOUT}s)"},
                        }
                    except Exception as e:
                        result = {
                            "name": scenario_name,
                            "status": "failed",
                            "details": {"error": str(e)},
                        }

                    scenario_results.append(result)

                drill_end = time.perf_counter()
                end_time = datetime.now(timezone.utc)

                # 生成报告（使用独立 session，避免请求作用域 session 已关闭）
                await self._generate_drill_report(
                    drill_id=drill_id,
                    start_time=start_time,
                    end_time=end_time,
                    duration_seconds=round(drill_end - drill_start, 2),
                    scenario_results=scenario_results,
                )

            except Exception as e:
                logger.error(f"演练 {drill_id} 执行异常: {e}")

            finally:
                # 确保恢复
                if breaker and breaker.state != BreakerState.CLOSED:
                    breaker.reset()

                self.__class__.is_drill_active = False
                self.__class__._current_drill_id = None
                self.__class__._stop_requested = False

    async def _run_scenario(
        self, name: str, breaker: Optional[CircuitBreaker] = None
    ) -> dict:
        """执行单个场景"""
        if name == "circuit_breaker_degradation":
            return await self._run_circuit_breaker_scenario(breaker)
        elif name == "db_timeout_fallback":
            return await self._run_db_timeout_scenario()
        else:
            return {"name": name, "status": "skipped", "details": {"error": "未知场景"}}

    async def _run_circuit_breaker_scenario(
        self, breaker: Optional[CircuitBreaker] = None
    ) -> dict:
        """场景 1: L2/L3 熔断降级验证"""
        result: Dict[str, Any] = {
            "name": "circuit_breaker_degradation",
            "description": "L2/L3 熔断降级验证",
            "status": "passed",
            "details": {},
        }

        if breaker is None:
            result["status"] = "skipped"
            result["details"]["error"] = "CircuitBreaker 实例不可用"
            return result

        start = time.perf_counter()
        state_before = breaker.state

        # 如果已经 OPEN，跳过
        if state_before == BreakerState.OPEN:
            result["status"] = "skipped"
            result["details"] = {
                "breaker_state_before": state_before.value,
                "reason": "breaker_already_open",
            }
            return result

        try:
            result["details"]["breaker_state_before"] = state_before.value

            # 1. 强制打开熔断器
            await breaker.force_open()
            result["details"]["breaker_forced_to"] = "OPEN"

            # 2. 验证 L2 请求被降级
            allowed, degraded = await breaker.allow_request("L2")
            result["details"]["degradation_detected"] = degraded
            if not degraded:
                result["status"] = "failed"
                result["details"]["error"] = "L2 请求未被降级"
                return result

            # 3. 验证 L1 不受影响
            l1_allowed, l1_degraded = await breaker.allow_request("L1")
            result["details"]["l1_fallback_working"] = l1_allowed and not l1_degraded

            # 4. 恢复
            breaker.reset()
            result["details"]["breaker_restored_to"] = breaker.state.value

            # 5. 验证恢复
            allowed2, degraded2 = await breaker.allow_request("L2")
            if degraded2:
                result["status"] = "failed"
                result["details"]["error"] = "恢复后 L2 仍然被降级"
                return result

            elapsed = time.perf_counter() - start
            result["recovery_seconds"] = round(elapsed, 3)
            result["details"]["degradation_latency_ms"] = round(elapsed * 1000, 1)

        except Exception as e:
            result["status"] = "failed"
            result["details"]["error"] = str(e)
            # 确保恢复
            try:
                breaker.reset()
            except Exception:
                pass

        return result

    async def _run_db_timeout_scenario(self) -> dict:
        """场景 2: 数据库超时 Redis 暂存验证"""
        result: Dict[str, Any] = {
            "name": "db_timeout_fallback",
            "description": "数据库超时 Redis 暂存验证",
            "status": "passed",
            "details": {},
        }

        start = time.perf_counter()

        try:
            # 构造模拟诊断结果
            mock_data = {
                "session_id": f"drill-{uuid.uuid4().hex[:8]}",
                "alarm_id": 0,
                "device_id": 0,
                "engine_level": "L2",
                "status": "drill_test",
                "conclusion": "演练测试数据",
                "start_time": datetime.now(timezone.utc).isoformat(),
                "end_time": datetime.now(timezone.utc).isoformat(),
            }

            # 1. 测试 save_to_redis
            redis_key = await DiagnosisFallbackStore.save_to_redis(
                mock_data, reason="chaos_drill"
            )
            result["details"]["redis_key"] = redis_key
            result["details"]["redis_fallback_working"] = bool(redis_key)

            if not redis_key:
                result["status"] = "failed"
                result["details"]["error"] = "save_to_redis 返回空 key"
                return result

            # 2. 验证 key 存在然后清理（不调用 recover_pending 避免写入 DB）
            from app.core.redis_lock import get_redis_client

            redis = get_redis_client()
            exists = redis.exists(redis_key) if redis else False
            result["details"]["data_integrity_check"] = bool(exists)

            # 3. 清理演练数据
            if redis and exists:
                redis.delete(redis_key)
                result["details"]["fault_cleared"] = True
            else:
                result["details"]["fault_cleared"] = False
                if not redis:
                    result["status"] = "skipped"
                    result["details"]["error"] = "Redis 不可用"
                    return result

            elapsed = time.perf_counter() - start
            result["recovery_seconds"] = round(elapsed, 3)

        except Exception as e:
            result["status"] = "failed"
            result["details"]["error"] = str(e)

        return result

    # ---- 终止演练 ----

    async def stop_drill(self, breaker: Optional[CircuitBreaker] = None) -> str:
        """终止演练"""
        if not self.__class__.is_drill_active:
            raise ValueError("当前没有正在执行的演练")

        drill_id = self.__class__._current_drill_id
        self.__class__._stop_requested = True

        # 立即恢复熔断器
        if breaker and breaker.state != BreakerState.CLOSED:
            breaker.reset()

        return drill_id or "unknown"

    # ---- 报告生成 ----

    async def _generate_drill_report(
        self,
        drill_id: str,
        start_time: datetime,
        end_time: datetime,
        duration_seconds: float,
        scenario_results: List[dict],
    ):
        """生成演练报告"""
        # 判断总体状态
        statuses = [s.get("status") for s in scenario_results]
        if all(s == "passed" for s in statuses):
            overall_status = "passed"
        elif any(s == "failed" for s in statuses):
            overall_status = "failed"
        elif all(s == "skipped" for s in statuses):
            overall_status = "skipped"
        else:
            overall_status = "partial"

        passed_count = sum(1 for s in statuses if s == "passed")
        total_count = len(statuses)

        report_data = {
            "drill_id": drill_id,
            "start_time": start_time.isoformat(),
            "end_time": end_time.isoformat(),
            "duration_seconds": duration_seconds,
            "scenarios": scenario_results,
            "overall_status": overall_status,
            "summary": f"{passed_count}/{total_count} 个场景通过",
        }

        date_str = start_time.strftime("%Y-%m-%d")
        report = ReportRecord(
            report_type="diagnosis_drill",
            report_name=f"灾难恢复演练报告 {date_str}",
            start_time=start_time,
            end_time=end_time,
            status="completed",
            report_data=json.dumps(report_data, ensure_ascii=False),
        )

        # 尝试使用传入的 session，失败则使用独立 session
        # （后台任务中请求作用域 session 可能已关闭）
        try:
            self.db.add(report)
            await self.db.commit()
        except Exception:
            try:
                from app.core.database import async_session
                async with async_session() as db:
                    db.add(report)
                    await db.commit()
            except Exception as e:
                logger.error(f"演练报告保存失败: {e}")

    # ---- 历史查询 ----

    async def get_drill_history(self, page: int = 1, page_size: int = 10) -> dict:
        """查询演练历史"""
        base_query = select(ReportRecord).where(
            ReportRecord.report_type == "diagnosis_drill"
        )

        # 查询总数
        count_query = select(func.count()).select_from(base_query.subquery())
        total_result = await self.db.execute(count_query)
        total = total_result.scalar()

        # 分页查询
        query = base_query.order_by(ReportRecord.created_at.desc())
        query = query.offset((page - 1) * page_size).limit(page_size)

        result = await self.db.execute(query)
        reports = result.scalars().all()

        return {
            "total": total,
            "items": reports,
        }
