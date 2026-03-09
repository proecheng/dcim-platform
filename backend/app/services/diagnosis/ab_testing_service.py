"""
A/B 测试服务 - Story 26.5
"""
import hashlib
import json
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
from sqlalchemy import select, func, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession
from redis import asyncio as aioredis

from app.models.ab_test_config import ABTestConfig, ABTestDeviceAssignment, ABTestArchive
from app.models.fault_tree import FaultTree, FaultTreeVersion
from app.models.diagnosis import DiagnosisResult, DiagnosisAnnotation
from app.core.config import get_settings

settings = get_settings()


class ABTestingService:
    """A/B 测试服务"""

    def __init__(self, db: AsyncSession, redis_client: Optional[aioredis.Redis] = None):
        self.db = db
        self.redis = redis_client
        self.cache_ttl = 60  # 缓存 60 秒

    async def create_ab_test(
        self,
        name: str,
        fault_tree_id: int,
        version_a_id: int,
        version_b_id: int,
        strategy: str,
        strategy_params: Dict[str, Any],
        min_duration_hours: int = 168,
        min_sample_size: int = 100,
        created_by: int = None,
    ) -> ABTestConfig:
        """创建 A/B 测试配置"""
        # 检查是否已有活跃的 A/B 测试
        stmt = select(ABTestConfig).where(
            and_(
                ABTestConfig.fault_tree_id == fault_tree_id,
                ABTestConfig.status == "active"
            )
        )
        result = await self.db.execute(stmt)
        existing = result.scalar_one_or_none()
        if existing:
            raise ValueError(f"故障树 {fault_tree_id} 已有活跃的 A/B 测试")

        # 创建 A/B 测试配置
        ab_test = ABTestConfig(
            name=name,
            fault_tree_id=fault_tree_id,
            version_a_id=version_a_id,
            version_b_id=version_b_id,
            strategy=strategy,
            strategy_params=strategy_params,
            min_duration_hours=min_duration_hours,
            min_sample_size=min_sample_size,
            created_by=created_by,
        )
        self.db.add(ab_test)
        await self.db.commit()
        await self.db.refresh(ab_test)

        # 删除缓存
        await self._invalidate_cache(fault_tree_id)

        return ab_test

    async def update_ab_test(
        self,
        ab_test_id: int,
        strategy_params: Dict[str, Any],
        version: int,
    ) -> ABTestConfig:
        """更新 A/B 测试配置（扩大灰度）"""
        # 查询 A/B 测试配置
        stmt = select(ABTestConfig).where(ABTestConfig.id == ab_test_id)
        result = await self.db.execute(stmt)
        ab_test = result.scalar_one_or_none()
        if not ab_test:
            raise ValueError(f"A/B 测试 {ab_test_id} 不存在")

        # 检查乐观锁版本号
        if ab_test.version != version:
            raise ValueError(f"版本冲突：当前版本为 {ab_test.version}，请求版本为 {version}")

        # 验证灰度扩大不超过 2 倍
        if ab_test.strategy == "percentage" or ab_test.strategy == "hash":
            old_percentage = ab_test.strategy_params.get("percentage", 0)
            new_percentage = strategy_params.get("percentage", 0)
            if new_percentage > old_percentage * 2:
                raise ValueError(f"灰度扩大不能超过 2 倍（当前 {old_percentage}%，请求 {new_percentage}%）")

        # 更新配置
        ab_test.strategy_params = strategy_params
        ab_test.version += 1
        ab_test.updated_at = datetime.utcnow()
        await self.db.commit()
        await self.db.refresh(ab_test)

        # 删除缓存
        await self._invalidate_cache(ab_test.fault_tree_id)

        return ab_test

    async def select_version(
        self,
        fault_tree_id: int,
        device_id: str,
        device_type: Optional[str] = None,
        site_id: Optional[int] = None,
    ) -> int:
        """根据分流策略选择版本"""
        # 查询活跃的 A/B 测试配置（优先从缓存读取）
        ab_test = await self._get_active_ab_test(fault_tree_id)
        if not ab_test:
            # 没有活跃的 A/B 测试，返回 active 版本
            return await self._get_active_version_id(fault_tree_id)

        # 获取或分配设备版本
        version_id = await self._get_or_assign_device_version(
            ab_test, device_id, device_type, site_id
        )
        return version_id

    async def _get_active_ab_test(self, fault_tree_id: int) -> Optional[ABTestConfig]:
        """获取活跃的 A/B 测试配置（优先从缓存读取）"""
        cache_key = f"ab_test:fault_tree:{fault_tree_id}"

        # 尝试从 Redis 缓存读取
        if self.redis:
            try:
                cached = await self.redis.get(cache_key)
                if cached:
                    data = json.loads(cached)
                    # 重建 ABTestConfig 对象
                    ab_test = ABTestConfig(**data)
                    return ab_test
            except Exception:
                pass  # 缓存失败，从数据库读取

        # 从数据库读取
        stmt = select(ABTestConfig).where(
            and_(
                ABTestConfig.fault_tree_id == fault_tree_id,
                ABTestConfig.status == "active"
            )
        )
        result = await self.db.execute(stmt)
        ab_test = result.scalar_one_or_none()

        # 写入缓存
        if ab_test and self.redis:
            try:
                data = {
                    "id": ab_test.id,
                    "fault_tree_id": ab_test.fault_tree_id,
                    "version_a_id": ab_test.version_a_id,
                    "version_b_id": ab_test.version_b_id,
                    "strategy": ab_test.strategy,
                    "strategy_params": ab_test.strategy_params,
                }
                await self.redis.setex(cache_key, self.cache_ttl, json.dumps(data))
            except Exception:
                pass  # 缓存失败不影响主流程

        return ab_test

    async def _get_or_assign_device_version(
        self,
        ab_test: ABTestConfig,
        device_id: str,
        device_type: Optional[str],
        site_id: Optional[int],
    ) -> int:
        """获取或分配设备版本"""
        # 查询设备是否已分配版本
        stmt = select(ABTestDeviceAssignment).where(
            and_(
                ABTestDeviceAssignment.ab_test_id == ab_test.id,
                ABTestDeviceAssignment.device_id == device_id
            )
        )
        result = await self.db.execute(stmt)
        assignment = result.scalar_one_or_none()

        if assignment:
            # 设备已分配版本，直接返回
            return assignment.assigned_version_id

        # 设备未分配，根据分流策略计算版本
        if ab_test.strategy == "hash" or ab_test.strategy == "percentage":
            percentage = ab_test.strategy_params.get("percentage", 0)
            version_id = self._select_version_by_hash(
                device_id, percentage, ab_test.version_a_id, ab_test.version_b_id
            )
        elif ab_test.strategy == "device_type":
            device_types_a = ab_test.strategy_params.get("device_types_a", [])
            version_id = self._select_version_by_device_type(
                device_type, device_types_a, ab_test.version_a_id, ab_test.version_b_id
            )
        elif ab_test.strategy == "site":
            site_ids_a = ab_test.strategy_params.get("site_ids_a", [])
            version_id = self._select_version_by_site(
                site_id, site_ids_a, ab_test.version_a_id, ab_test.version_b_id
            )
        else:
            # 未知策略，使用版本B（对照版本）
            version_id = ab_test.version_b_id

        # 记录设备版本分配
        assignment = ABTestDeviceAssignment(
            ab_test_id=ab_test.id,
            device_id=device_id,
            assigned_version_id=version_id,
        )
        self.db.add(assignment)
        await self.db.commit()

        return version_id

    def _select_version_by_hash(
        self, device_id: str, percentage: int, version_a_id: int, version_b_id: int
    ) -> int:
        """使用一致性哈希确保同一设备始终使用同一版本"""
        hash_value = int(hashlib.sha256(device_id.encode()).hexdigest(), 16)
        bucket = hash_value % 100
        return version_a_id if bucket < percentage else version_b_id

    def _select_version_by_device_type(
        self, device_type: str, device_types_a: List[str], version_a_id: int, version_b_id: int
    ) -> int:
        """按设备类型分流"""
        return version_a_id if device_type in device_types_a else version_b_id

    def _select_version_by_site(
        self, site_id: int, site_ids_a: List[int], version_a_id: int, version_b_id: int
    ) -> int:
        """按站点分流"""
        return version_a_id if site_id in site_ids_a else version_b_id

    async def _get_active_version_id(self, fault_tree_id: int) -> int:
        """获取故障树的 active 版本ID"""
        stmt = select(FaultTreeVersion.id).where(
            and_(
                FaultTreeVersion.tree_id == fault_tree_id,
                FaultTreeVersion.status == "active"
            )
        )
        result = await self.db.execute(stmt)
        version_id = result.scalar_one_or_none()
        if not version_id:
            raise ValueError(f"故障树 {fault_tree_id} 没有 active 版本")
        return version_id

    async def _invalidate_cache(self, fault_tree_id: int):
        """删除 Redis 缓存"""
        if self.redis:
            try:
                cache_key = f"ab_test:fault_tree:{fault_tree_id}"
                await self.redis.delete(cache_key)
            except Exception:
                pass  # 缓存失败不影响主流程

    async def get_ab_test_report(self, ab_test_id: int) -> Dict[str, Any]:
        """获取 A/B 测试效果报告"""
        # 查询 A/B 测试配置
        stmt = select(ABTestConfig).where(ABTestConfig.id == ab_test_id)
        result = await self.db.execute(stmt)
        ab_test = result.scalar_one_or_none()
        if not ab_test:
            raise ValueError(f"A/B 测试 {ab_test_id} 不存在")

        # 计算运行时长
        duration_hours = int((datetime.utcnow() - ab_test.created_at).total_seconds() / 3600)
        duration_days = duration_hours // 24

        # 统计版本A效果
        version_a_stats = await self._calculate_version_stats(
            ab_test.version_a_id, ab_test.created_at, datetime.utcnow()
        )

        # 统计版本B效果
        version_b_stats = await self._calculate_version_stats(
            ab_test.version_b_id, ab_test.created_at, datetime.utcnow()
        )

        # 执行统计检验
        statistical_test = self._perform_chi_square_test(version_a_stats, version_b_stats)

        # 检查完成条件
        completion_requirements = self._check_completion_requirements(
            ab_test, duration_hours, version_a_stats, version_b_stats
        )

        # 生成建议
        recommendation = self._generate_recommendation(
            version_a_stats, version_b_stats, statistical_test, completion_requirements
        )

        return {
            "ab_test_id": ab_test.id,
            "name": ab_test.name,
            "duration_days": duration_days,
            "duration_hours": duration_hours,
            "version_a": version_a_stats,
            "version_b": version_b_stats,
            "statistical_test": statistical_test,
            "recommendation": recommendation,
            "can_complete": completion_requirements["can_complete"],
            "completion_requirements": completion_requirements,
        }

    async def _calculate_version_stats(
        self, version_id: int, start_date: datetime, end_date: datetime
    ) -> Dict[str, Any]:
        """计算指定版本的统计数据"""
        # 查询版本名称
        stmt = select(FaultTreeVersion.version_number).where(FaultTreeVersion.id == version_id)
        result = await self.db.execute(stmt)
        version_number = result.scalar_one_or_none()

        # 计算诊断次数
        stmt = select(func.count(DiagnosisResult.id)).where(
            and_(
                DiagnosisResult.fault_tree_version_id == version_id,
                DiagnosisResult.created_at.between(start_date, end_date)
            )
        )
        result = await self.db.execute(stmt)
        diagnosis_count = result.scalar() or 0

        # 计算准确率
        accuracy_rate = await self._calculate_accuracy_rate(version_id, start_date, end_date)

        # 计算平均推理耗时
        avg_inference_time_ms = await self._calculate_avg_inference_time(version_id, start_date, end_date)

        # 计算误报率
        false_positive_rate = await self._calculate_false_positive_rate(version_id, start_date, end_date)

        # 计算漏报率
        false_negative_rate = await self._calculate_false_negative_rate(version_id, start_date, end_date)

        return {
            "version_id": version_id,
            "version_name": f"v{version_number}" if version_number else "unknown",
            "diagnosis_count": diagnosis_count,
            "accuracy_rate": accuracy_rate,
            "avg_inference_time_ms": avg_inference_time_ms,
            "false_positive_rate": false_positive_rate,
            "false_negative_rate": false_negative_rate,
        }

    async def _calculate_accuracy_rate(
        self, version_id: int, start_date: datetime, end_date: datetime
    ) -> float:
        """计算准确率"""
        stmt = select(
            func.count(DiagnosisAnnotation.id).filter(DiagnosisAnnotation.is_accurate == True).label("accurate_count"),
            func.count(DiagnosisAnnotation.id).label("total_count")
        ).select_from(DiagnosisResult).join(
            DiagnosisAnnotation, DiagnosisResult.id == DiagnosisAnnotation.diagnosis_result_id
        ).where(
            and_(
                DiagnosisResult.fault_tree_version_id == version_id,
                DiagnosisResult.created_at.between(start_date, end_date)
            )
        )
        result = await self.db.execute(stmt)
        row = result.first()
        if not row or row.total_count == 0:
            return 0.0
        return row.accurate_count / row.total_count

    async def _calculate_avg_inference_time(
        self, version_id: int, start_date: datetime, end_date: datetime
    ) -> float:
        """计算平均推理耗时"""
        stmt = select(func.avg(DiagnosisResult.inference_time_ms)).where(
            and_(
                DiagnosisResult.fault_tree_version_id == version_id,
                DiagnosisResult.created_at.between(start_date, end_date),
                DiagnosisResult.inference_time_ms.isnot(None)
            )
        )
        result = await self.db.execute(stmt)
        avg_time = result.scalar()
        return float(avg_time) if avg_time else 0.0

    async def _calculate_false_positive_rate(
        self, version_id: int, start_date: datetime, end_date: datetime
    ) -> float:
        """计算误报率"""
        stmt = select(
            func.count(DiagnosisResult.id).filter(
                and_(
                    DiagnosisResult.root_cause.isnot(None),
                    DiagnosisAnnotation.is_accurate == False
                )
            ).label("false_positive_count"),
            func.count(DiagnosisResult.id).filter(DiagnosisResult.root_cause.isnot(None)).label("total_positive_count")
        ).select_from(DiagnosisResult).join(
            DiagnosisAnnotation, DiagnosisResult.id == DiagnosisAnnotation.diagnosis_result_id
        ).where(
            and_(
                DiagnosisResult.fault_tree_version_id == version_id,
                DiagnosisResult.created_at.between(start_date, end_date)
            )
        )
        result = await self.db.execute(stmt)
        row = result.first()
        if not row or row.total_positive_count == 0:
            return 0.0
        return row.false_positive_count / row.total_positive_count

    async def _calculate_false_negative_rate(
        self, version_id: int, start_date: datetime, end_date: datetime
    ) -> float:
        """计算漏报率"""
        # 简化实现：漏报率 = 1 - 准确率（实际应通过工单系统关联）
        accuracy_rate = await self._calculate_accuracy_rate(version_id, start_date, end_date)
        return max(0.0, 1.0 - accuracy_rate) if accuracy_rate > 0 else 0.0

    def _perform_chi_square_test(
        self, version_a_stats: Dict[str, Any], version_b_stats: Dict[str, Any]
    ) -> Dict[str, Any]:
        """执行卡方检验"""
        try:
            from scipy.stats import chi2_contingency, fisher_exact
        except ImportError:
            return {
                "method": "unavailable",
                "p_value": None,
                "is_significant": False,
                "warning": "scipy 未安装，无法执行统计检验"
            }

        # 计算准确和不准确的次数
        total_a = version_a_stats["diagnosis_count"]
        total_b = version_b_stats["diagnosis_count"]
        accurate_a = int(total_a * version_a_stats["accuracy_rate"])
        accurate_b = int(total_b * version_b_stats["accuracy_rate"])
        inaccurate_a = total_a - accurate_a
        inaccurate_b = total_b - accurate_b

        # 检查样本量充足性
        if total_a < 10 or total_b < 10:
            return {
                "method": "insufficient_sample",
                "p_value": None,
                "is_significant": False,
                "warning": f"样本量不足（版本A: {total_a}, 版本B: {total_b}），建议至少各 10 次诊断"
            }

        # 构建列联表
        observed = [[accurate_a, inaccurate_a], [accurate_b, inaccurate_b]]

        # 计算期望频数
        chi2, p_value, dof, expected = chi2_contingency(observed)

        # 检查期望频数是否 ≥ 5
        import numpy as np
        if (np.array(expected) < 5).any():
            # 使用 Fisher 精确检验
            oddsratio, p_value_fisher = fisher_exact(observed)
            return {
                "method": "fisher_exact",
                "p_value": p_value_fisher,
                "odds_ratio": float(oddsratio),
                "is_significant": p_value_fisher < 0.05,
                "note": "期望频数 < 5，使用 Fisher 精确检验"
            }

        return {
            "method": "chi_square",
            "chi2_statistic": float(chi2),
            "p_value": float(p_value),
            "degrees_of_freedom": int(dof),
            "is_significant": p_value < 0.05
        }

    def _check_completion_requirements(
        self,
        ab_test: ABTestConfig,
        duration_hours: int,
        version_a_stats: Dict[str, Any],
        version_b_stats: Dict[str, Any],
    ) -> Dict[str, Any]:
        """检查完成条件"""
        duration_met = duration_hours >= ab_test.min_duration_hours
        sample_size_a_met = version_a_stats["diagnosis_count"] >= ab_test.min_sample_size
        sample_size_b_met = version_b_stats["diagnosis_count"] >= ab_test.min_sample_size

        can_complete = duration_met and sample_size_a_met and sample_size_b_met

        return {
            "can_complete": can_complete,
            "duration_met": duration_met,
            "duration_required": ab_test.min_duration_hours,
            "duration_actual": duration_hours,
            "sample_size_a_met": sample_size_a_met,
            "sample_size_b_met": sample_size_b_met,
            "sample_size_required": ab_test.min_sample_size,
            "sample_size_a_actual": version_a_stats["diagnosis_count"],
            "sample_size_b_actual": version_b_stats["diagnosis_count"],
        }

    def _generate_recommendation(
        self,
        version_a_stats: Dict[str, Any],
        version_b_stats: Dict[str, Any],
        statistical_test: Dict[str, Any],
        completion_requirements: Dict[str, Any],
    ) -> str:
        """生成建议"""
        if not completion_requirements["can_complete"]:
            return "建议继续运行，尚未满足完成条件（最小运行时长或样本量不足）"

        if statistical_test["method"] == "insufficient_sample":
            return "样本量不足，建议继续运行以收集更多数据"

        if statistical_test["is_significant"]:
            if version_a_stats["accuracy_rate"] > version_b_stats["accuracy_rate"]:
                return "版本A准确率显著高于版本B，建议扩大灰度或全量切换到版本A"
            else:
                return "版本B准确率显著高于版本A，建议回滚到版本B"
        else:
            if version_a_stats["accuracy_rate"] >= version_b_stats["accuracy_rate"]:
                return "两版本准确率无显著差异，但版本A略优，建议全量切换到版本A"
            else:
                return "两版本准确率无显著差异，建议继续观察或回滚到版本B"

    async def complete_ab_test(
        self,
        ab_test_id: int,
        action: str,
        version: int,
        archived_by: int = None,
    ) -> Dict[str, Any]:
        """完成 A/B 测试（全量切换或回滚）"""
        # 查询 A/B 测试配置
        stmt = select(ABTestConfig).where(ABTestConfig.id == ab_test_id)
        result = await self.db.execute(stmt)
        ab_test = result.scalar_one_or_none()
        if not ab_test:
            raise ValueError(f"A/B 测试 {ab_test_id} 不存在")

        # 检查乐观锁版本号
        if ab_test.version != version:
            raise ValueError(f"版本冲突：当前版本为 {ab_test.version}，请求版本为 {version}")

        # 获取效果报告
        report = await self.get_ab_test_report(ab_test_id)

        # 检查完成条件
        if not report["can_complete"]:
            raise ValueError("尚未满足完成条件（最小运行时长或样本量不足）")

        # 执行操作
        if action == "promote_version_a":
            # 将版本A设为 active，版本B归档
            await self._promote_version(ab_test.version_a_id, ab_test.version_b_id)
            new_active_version_id = ab_test.version_a_id
            archived_version_id = ab_test.version_b_id
        elif action == "rollback_to_version_b":
            # 保持版本B为 active
            new_active_version_id = ab_test.version_b_id
            archived_version_id = None
        else:
            raise ValueError(f"未知操作: {action}")

        # 归档统计数据
        archive = ABTestArchive(
            ab_test_id=ab_test.id,
            version_a_stats=report["version_a"],
            version_b_stats=report["version_b"],
            statistical_test_result=report["statistical_test"],
            decision=action,
            archived_by=archived_by,
        )
        self.db.add(archive)

        # 更新 A/B 测试状态
        ab_test.status = "completed"
        ab_test.completed_at = datetime.utcnow()
        ab_test.version += 1
        await self.db.commit()

        # 删除缓存
        await self._invalidate_cache(ab_test.fault_tree_id)

        return {
            "message": f"A/B 测试已完成，{'版本A已设为 active' if action == 'promote_version_a' else '保持版本B为 active'}",
            "new_active_version_id": new_active_version_id,
            "archived_version_id": archived_version_id,
        }

    async def _promote_version(self, new_active_id: int, old_active_id: int):
        """将新版本设为 active，旧版本归档"""
        # 将旧版本设为 archived
        stmt = select(FaultTreeVersion).where(FaultTreeVersion.id == old_active_id)
        result = await self.db.execute(stmt)
        old_version = result.scalar_one_or_none()
        if old_version:
            old_version.status = "archived"

        # 将新版本设为 active
        stmt = select(FaultTreeVersion).where(FaultTreeVersion.id == new_active_id)
        result = await self.db.execute(stmt)
        new_version = result.scalar_one_or_none()
        if new_version:
            new_version.status = "active"
            new_version.activated_at = datetime.utcnow()

        await self.db.commit()

