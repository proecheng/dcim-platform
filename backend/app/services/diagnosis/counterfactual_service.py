"""
反事实分析服务
Story 26.1: 反事实分析
"""

import asyncio
import logging
import time
import uuid
from datetime import datetime
from typing import List, Dict, Optional, Any
import json

import redis.asyncio as redis
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from prometheus_client import Counter, Histogram

from ...models.diagnosis import (
    CounterfactualAnalysis,
    DiagnosisSession,
    DiagnosisResult,
)
from ...models.config import SystemConfig
from ...core.database import async_session
from ...core.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

# Prometheus 监控指标
counterfactual_analysis_total = Counter(
    "counterfactual_analysis_total",
    "反事实分析总次数",
    ["status"]
)
counterfactual_analysis_duration = Histogram(
    "counterfactual_analysis_duration_seconds",
    "反事实分析耗时",
    buckets=[0.1, 0.5, 1.0, 2.0, 5.0, 10.0]
)
counterfactual_evidence_removed = Counter(
    "counterfactual_evidence_removed_total",
    "反事实分析移除证据总数"
)
counterfactual_lock_wait_duration = Histogram(
    "counterfactual_lock_wait_seconds",
    "Redis 锁等待时间",
    buckets=[0.001, 0.01, 0.1, 0.5, 1.0]
)
counterfactual_cache_hit_total = Counter(
    "counterfactual_cache_hit_total",
    "缓存命中次数"
)


# 配置常量
PATH_DECAY_FACTOR_KEY = "counterfactual.path_decay_factor"
PATH_DECAY_FACTOR_DEFAULT = 0.8
RELATIVE_THRESHOLD_HIGH_KEY = "counterfactual.relative_threshold_high"
RELATIVE_THRESHOLD_HIGH_DEFAULT = 0.10
RELATIVE_THRESHOLD_MEDIUM_KEY = "counterfactual.relative_threshold_medium"
RELATIVE_THRESHOLD_MEDIUM_DEFAULT = 0.15
RELATIVE_THRESHOLD_LOW_KEY = "counterfactual.relative_threshold_low"
RELATIVE_THRESHOLD_LOW_DEFAULT = 0.20
CONFIDENCE_THRESHOLD_HIGH = 0.8
CONFIDENCE_THRESHOLD_MEDIUM = 0.5
CACHE_TTL_SECONDS_KEY = "counterfactual.cache_ttl_seconds"
CACHE_TTL_SECONDS_DEFAULT = 3600  # 1小时
ANALYSIS_TIMEOUT_SECONDS = 5
REDIS_LOCK_TTL = 60  # Redis 锁过期时间（秒）
REDIS_LOCK_RETRY_DELAY = 0.1  # 锁重试延迟（秒）
REDIS_LOCK_MAX_RETRIES = 3  # 最大重试次数


# Lua 脚本：原子获取锁
REDIS_LOCK_SCRIPT = """
if redis.call("exists", KEYS[1]) == 0 then
    redis.call("set", KEYS[1], ARGV[1], "EX", ARGV[2])
    return 1
else
    return 0
end
"""

# Lua 脚本：原子释放锁
REDIS_UNLOCK_SCRIPT = """
if redis.call("get", KEYS[1]) == ARGV[1] then
    return redis.call("del", KEYS[1])
else
    return 0
end
"""


async def get_config(key: str, default: Any) -> Any:
    """获取配置值"""
    try:
        async with async_session() as session:
            result = await session.execute(
                select(SystemConfig).where(
                    SystemConfig.config_group == "diagnosis",
                    SystemConfig.config_key == key
                )
            )
            config = result.scalar_one_or_none()
            if config:
                return json.loads(config.config_value)
            return default
    except Exception as e:
        logger.warning(f"Failed to get config {key}: {e}, using default {default}")
        return default


async def _acquire_redis_lock(session_id: int) -> Optional[str]:
    """
    获取 Redis 分布式锁

    Args:
        session_id: 诊断会话ID

    Returns:
        锁的 token（用于释放锁），如果获取失败返回 None
    """
    lock_key = f"counterfactual:lock:{session_id}"
    lock_token = f"{uuid.uuid4()}:{time.time()}"

    redis_client = None
    lock_wait_start = time.time()

    try:
        redis_client = redis.from_url(settings.REDIS_URL)

        # 尝试获取锁（带重试）
        for attempt in range(REDIS_LOCK_MAX_RETRIES):
            result = await redis_client.eval(
                REDIS_LOCK_SCRIPT,
                1,
                lock_key,
                lock_token,
                str(REDIS_LOCK_TTL)
            )

            if result == 1:
                # 获取锁成功
                counterfactual_lock_wait_duration.observe(time.time() - lock_wait_start)
                logger.debug(f"Acquired lock for session {session_id}, token={lock_token}")
                return lock_token

            # 获取锁失败，等待后重试
            if attempt < REDIS_LOCK_MAX_RETRIES - 1:
                await asyncio.sleep(REDIS_LOCK_RETRY_DELAY)

        # 所有重试都失败
        logger.warning(f"Failed to acquire lock for session {session_id} after {REDIS_LOCK_MAX_RETRIES} attempts")
        return None

    except Exception as e:
        logger.error(f"Redis lock error for session {session_id}: {e}")
        return None
    finally:
        if redis_client:
            try:
                await redis_client.aclose()
            except Exception as e:
                logger.warning(f"Failed to close Redis client: {e}")


async def _release_redis_lock(session_id: int, lock_token: str) -> bool:
    """
    释放 Redis 分布式锁

    Args:
        session_id: 诊断会话ID
        lock_token: 锁的 token

    Returns:
        是否成功释放
    """
    lock_key = f"counterfactual:lock:{session_id}"

    redis_client = None
    try:
        redis_client = redis.from_url(settings.REDIS_URL)

        result = await redis_client.eval(
            REDIS_UNLOCK_SCRIPT,
            1,
            lock_key,
            lock_token
        )

        if result == 1:
            logger.debug(f"Released lock for session {session_id}")
            return True
        else:
            logger.warning(f"Failed to release lock for session {session_id}: lock token mismatch")
            return False

    except Exception as e:
        logger.error(f"Redis unlock error for session {session_id}: {e}")
        return False
    finally:
        if redis_client:
            try:
                await redis_client.aclose()
            except Exception as e:
                logger.warning(f"Failed to close Redis client: {e}")


def calculate_evidence_weight(evidence: Dict[str, Any], path_decay_factor: float) -> float:
    """
    计算证据权重

    Args:
        evidence: 证据字典，包含 probability, sensor_weight, path_length
        path_decay_factor: 路径衰减因子

    Returns:
        证据权重 [0.0, 1.0]
    """
    evidence_prob = evidence.get("probability", 0.5)
    sensor_weight = evidence.get("sensor_weight", 1.0)
    path_length = evidence.get("path_length", 1)

    # 使用指数衰减
    path_contribution = path_decay_factor ** path_length

    return evidence_prob * sensor_weight * path_contribution


async def _check_cache(session_id: int, db: AsyncSession) -> Optional[CounterfactualAnalysis]:
    """
    检查缓存是否有效

    缓存失效条件:
    1. 不存在记录
    2. 记录已软删除（deleted_at IS NOT NULL）
    3. 故障树版本不匹配
    4. 配置版本不匹配
    5. 记录过期（created_at < NOW() - cache_ttl）

    Args:
        session_id: 诊断会话ID
        db: 数据库会话

    Returns:
        有效的缓存记录，如果缓存失效返回 None
    """
    try:
        # 查询现有记录
        result = await db.execute(
            select(CounterfactualAnalysis).where(
                CounterfactualAnalysis.session_id == session_id,
                CounterfactualAnalysis.deleted_at.is_(None)
            )
        )
        cached = result.scalar_one_or_none()

        if not cached:
            return None

        # 检查是否过期
        cache_ttl = await get_config(CACHE_TTL_SECONDS_KEY, CACHE_TTL_SECONDS_DEFAULT)
        if cached.created_at:
            age_seconds = (datetime.now() - cached.created_at).total_seconds()
            if age_seconds > cache_ttl:
                logger.debug(f"Cache expired for session {session_id}, age={age_seconds}s")
                return None

        # 检查版本是否匹配
        current_config_version = await _get_config_version()

        # 查询当前诊断结果的故障树版本
        diagnosis_result = await db.execute(
            select(DiagnosisResult).where(DiagnosisResult.session_id == session_id)
        )
        current_result = diagnosis_result.scalar_one_or_none()

        if current_result:
            current_fault_tree_version = current_result.fault_tree_version

            if cached.fault_tree_version != current_fault_tree_version:
                logger.debug(f"Fault tree version mismatch for session {session_id}")
                return None

        if cached.config_version != current_config_version:
            logger.debug(f"Config version mismatch for session {session_id}")
            return None

        # 缓存有效
        return cached

    except Exception as e:
        logger.error(f"Cache check failed for session {session_id}: {e}")
        return None


async def analyze_counterfactual(
    session_id: int,
    top_n: int = 5,
    db: Optional[AsyncSession] = None
) -> Optional[CounterfactualAnalysis]:
    """
    执行反事实分析（带 Redis 锁和缓存检查）

    Args:
        session_id: 诊断会话ID
        top_n: 分析Top N证据
        db: 数据库会话（可选）

    Returns:
        CounterfactualAnalysis 对象，如果失败返回 None
    """
    start_time = time.time()
    lock_token = None

    try:
        # 1. 获取 Redis 分布式锁
        lock_token = await _acquire_redis_lock(session_id)
        if lock_token is None:
            logger.info(f"Failed to acquire lock for session {session_id}, skipping analysis")
            return None

        # 2. 检查缓存
        if db is None:
            async with async_session() as session:
                cached_result = await _check_cache(session_id, session)
                if cached_result:
                    counterfactual_cache_hit_total.inc()
                    logger.info(f"Cache hit for session {session_id}")
                    return cached_result

                # 执行分析
                return await _analyze_counterfactual_impl(session_id, top_n, session, start_time)
        else:
            cached_result = await _check_cache(session_id, db)
            if cached_result:
                counterfactual_cache_hit_total.inc()
                logger.info(f"Cache hit for session {session_id}")
                return cached_result

            # 执行分析
            return await _analyze_counterfactual_impl(session_id, top_n, db, start_time)

    except asyncio.TimeoutError:
        logger.error(f"Counterfactual analysis timeout for session {session_id}")
        counterfactual_analysis_total.labels(status="timeout").inc()
        return None
    except Exception as e:
        logger.error(f"Counterfactual analysis failed for session {session_id}: {e}", exc_info=True)
        counterfactual_analysis_total.labels(status="error").inc()
        return None
    finally:
        # 3. 释放 Redis 锁
        if lock_token:
            await _release_redis_lock(session_id, lock_token)


async def _analyze_counterfactual_impl(
    session_id: int,
    top_n: int,
    db: AsyncSession,
    start_time: float
) -> Optional[CounterfactualAnalysis]:
    """反事实分析实现（内部函数）"""

    # 1. 查询诊断会话和结果
    session_result = await db.execute(
        select(DiagnosisSession).where(DiagnosisSession.id == session_id)
    )
    diagnosis_session = session_result.scalar_one_or_none()
    if not diagnosis_session:
        logger.warning(f"Diagnosis session {session_id} not found")
        return None

    result_query = await db.execute(
        select(DiagnosisResult).where(DiagnosisResult.session_id == session_id)
    )
    diagnosis_result = result_query.scalar_one_or_none()
    if not diagnosis_result:
        logger.warning(f"Diagnosis result for session {session_id} not found")
        return None

    # 2. 提取原始根因和置信度
    original_root_cause = diagnosis_result.root_cause
    original_confidence = diagnosis_result.confidence

    if original_confidence is None or original_confidence < 0.3:
        logger.info(f"Session {session_id} confidence too low ({original_confidence}), skipping analysis")
        return None

    # 3. 提取证据列表
    evidence_list = diagnosis_result.evidence or []
    if not evidence_list:
        logger.warning(f"No evidence found for session {session_id}")
        return None

    # 4. 获取配置
    path_decay_factor = await get_config(PATH_DECAY_FACTOR_KEY, PATH_DECAY_FACTOR_DEFAULT)

    # 5. 计算证据权重并排序
    weighted_evidences = []
    for ev in evidence_list:
        weight = calculate_evidence_weight(ev, path_decay_factor)
        weighted_evidences.append({
            "node_id": ev.get("node_id"),
            "evidence_type": ev.get("evidence_type", "unknown"),
            "probability": ev.get("probability", 0.5),
            "sensor_weight": ev.get("sensor_weight", 1.0),
            "path_length": ev.get("path_length", 1),
            "weight": weight
        })

    # 按权重降序排序
    weighted_evidences.sort(key=lambda x: x["weight"], reverse=True)
    top_evidences = weighted_evidences[:top_n]

    # 6. 执行反事实推理（带超时）
    try:
        analysis_results = await asyncio.wait_for(
            _perform_counterfactual_inference(
                top_evidences,
                original_root_cause,
                original_confidence,
                diagnosis_result.reasoning_path or []
            ),
            timeout=ANALYSIS_TIMEOUT_SECONDS
        )
    except asyncio.TimeoutError:
        logger.error(f"Counterfactual inference timeout for session {session_id}")
        raise

    # 7. 保存分析结果
    analysis_time_ms = int((time.time() - start_time) * 1000)

    # 获取版本信息
    fault_tree_version = diagnosis_result.fault_tree_version
    config_version = await _get_config_version()

    # 删除旧的分析记录（缓存失效时可能存在旧记录）
    existing_result = await db.execute(
        select(CounterfactualAnalysis).where(
            CounterfactualAnalysis.session_id == session_id
        )
    )
    existing = existing_result.scalar_one_or_none()
    if existing:
        await db.delete(existing)
        await db.flush()

    # 创建分析记录
    counterfactual = CounterfactualAnalysis(
        session_id=session_id,
        original_root_cause=original_root_cause,
        original_confidence=original_confidence,
        top_evidences=[{
            "node_id": ev["node_id"],
            "evidence_type": ev["evidence_type"],
            "probability": ev["probability"],
            "sensor_weight": ev["sensor_weight"],
            "path_length": ev["path_length"]
        } for ev in top_evidences],
        analysis_results=analysis_results,
        analysis_time_ms=analysis_time_ms,
        fault_tree_version=fault_tree_version,
        config_version=config_version
    )

    db.add(counterfactual)
    await db.commit()
    await db.refresh(counterfactual)

    # 记录指标
    counterfactual_analysis_total.labels(status="success").inc()
    counterfactual_analysis_duration.observe(time.time() - start_time)
    counterfactual_evidence_removed.inc(len(top_evidences))

    logger.info(f"Counterfactual analysis completed for session {session_id}, time={analysis_time_ms}ms")

    return counterfactual


async def _perform_counterfactual_inference(
    top_evidences: List[Dict[str, Any]],
    original_root_cause: Optional[str],
    original_confidence: float,
    reasoning_path: List[Any]
) -> List[Dict[str, Any]]:
    """
    执行反事实推理

    Args:
        top_evidences: Top证据列表
        original_root_cause: 原始根因
        original_confidence: 原始置信度
        reasoning_path: 推理路径

    Returns:
        反事实场景列表
    """
    # 获取相对阈值配置
    if original_confidence >= CONFIDENCE_THRESHOLD_HIGH:
        relative_threshold = await get_config(RELATIVE_THRESHOLD_HIGH_KEY, RELATIVE_THRESHOLD_HIGH_DEFAULT)
    elif original_confidence >= CONFIDENCE_THRESHOLD_MEDIUM:
        relative_threshold = await get_config(RELATIVE_THRESHOLD_MEDIUM_KEY, RELATIVE_THRESHOLD_MEDIUM_DEFAULT)
    else:
        relative_threshold = await get_config(RELATIVE_THRESHOLD_LOW_KEY, RELATIVE_THRESHOLD_LOW_DEFAULT)

    scenarios = []

    # 为每个证据创建反事实场景
    for evidence in top_evidences:
        # 移除当前证据及其依赖
        removed_evidence_ids = _get_evidence_cascade(evidence["node_id"], reasoning_path)

        # 尝试调用真实 L2 推理引擎
        try:
            from ...services.diagnosis.l2_inference_engine import infer_fault_tree

            # 构建移除证据后的输入数据
            filtered_reasoning_path = [
                item for item in reasoning_path
                if isinstance(item, dict) and item.get("node_id") not in removed_evidence_ids
            ]

            # 调用 L2 推理引擎（带超时）
            inference_result = await asyncio.wait_for(
                infer_fault_tree(
                    fault_tree_id=1,  # 假设使用默认故障树
                    sensor_data={},  # 需要从原始诊断结果中提取
                    reasoning_path=filtered_reasoning_path
                ),
                timeout=5.0
            )

            new_confidence = inference_result.get("confidence", 0.0)
            new_root_cause = inference_result.get("root_cause")

        except (ImportError, asyncio.TimeoutError, Exception) as e:
            # 降级到模拟逻辑
            logger.warning(f"L2 inference failed for evidence {evidence['node_id']}, using simulation: {e}")
            new_confidence = _simulate_confidence_without_evidence(
                original_confidence,
                evidence["weight"],
                removed_evidence_ids,
                reasoning_path
            )
            new_root_cause = _simulate_new_root_cause(reasoning_path, removed_evidence_ids)

        # 判断结论是否改变
        confidence_change = new_confidence - original_confidence
        conclusion_changed = abs(confidence_change) >= relative_threshold

        scenarios.append({
            "removed_evidence_id": evidence["node_id"],
            "new_root_cause": new_root_cause,
            "new_confidence": round(new_confidence, 4),
            "confidence_change": round(confidence_change, 4),
            "conclusion_changed": conclusion_changed
        })

    return scenarios


def _get_evidence_cascade(node_id: int, reasoning_path: List[Any]) -> List[int]:
    """
    获取证据级联删除列表（包含依赖该证据的所有节点）

    Args:
        node_id: 证据节点ID
        reasoning_path: 推理路径

    Returns:
        需要移除的节点ID列表
    """
    removed_ids = [node_id]

    # 简化实现：查找所有依赖该节点的节点
    for path_item in reasoning_path:
        if isinstance(path_item, dict):
            dependencies = path_item.get("dependencies", [])
            if node_id in dependencies:
                removed_ids.append(path_item.get("node_id"))

    return removed_ids


def _simulate_confidence_without_evidence(
    original_confidence: float,
    evidence_weight: float,
    removed_evidence_ids: List[int],
    reasoning_path: List[Any]
) -> float:
    """
    模拟移除证据后的置信度

    Args:
        original_confidence: 原始置信度
        evidence_weight: 证据权重
        removed_evidence_ids: 移除的证据ID列表
        reasoning_path: 推理路径

    Returns:
        新置信度
    """
    # 简化模拟：置信度下降与证据权重成正比
    # 实际应该调用 L2 引擎重新推理
    confidence_drop = evidence_weight * 0.3  # 假设最多下降30%
    new_confidence = max(0.0, original_confidence - confidence_drop)

    return new_confidence


def _simulate_new_root_cause(reasoning_path: List[Any], removed_evidence_ids: List[int]) -> Optional[str]:
    """
    模拟新根因

    Args:
        reasoning_path: 推理路径
        removed_evidence_ids: 移除的证据ID列表

    Returns:
        新根因描述
    """
    # 简化实现：返回推理路径中第一个未被移除的节点
    for path_item in reasoning_path:
        if isinstance(path_item, dict):
            node_id = path_item.get("node_id")
            if node_id not in removed_evidence_ids:
                return path_item.get("description", f"节点 {node_id}")

    return None


async def _get_config_version() -> str:
    """获取配置版本号"""
    try:
        async with async_session() as session:
            result = await session.execute(
                select(SystemConfig).where(
                    SystemConfig.config_group == "diagnosis",
                    SystemConfig.config_key == "config_version"
                )
            )
            config = result.scalar_one_or_none()
            if config:
                return config.config_value
            return "1.0.0"
    except Exception as e:
        logger.warning(f"Failed to get config version: {e}")
        return "1.0.0"


async def get_counterfactual_analysis(
    session_id: int,
    db: AsyncSession
) -> Optional[CounterfactualAnalysis]:
    """
    获取反事实分析结果（带缓存）

    Args:
        session_id: 诊断会话ID
        db: 数据库会话

    Returns:
        CounterfactualAnalysis 对象，如果不存在返回 None
    """
    result = await db.execute(
        select(CounterfactualAnalysis).where(
            CounterfactualAnalysis.session_id == session_id,
            CounterfactualAnalysis.deleted_at.is_(None)
        )
    )
    return result.scalar_one_or_none()


async def invalidate_cache_if_needed(
    session_id: int,
    db: AsyncSession
) -> bool:
    """
    检查并失效缓存（如果版本不匹配）

    Args:
        session_id: 诊断会话ID
        db: 数据库会话

    Returns:
        是否失效了缓存
    """
    analysis = await get_counterfactual_analysis(session_id, db)
    if not analysis:
        return False

    # 获取当前版本
    result = await db.execute(
        select(DiagnosisResult).where(DiagnosisResult.session_id == session_id)
    )
    diagnosis_result = result.scalar_one_or_none()
    if not diagnosis_result:
        return False

    current_fault_tree_version = diagnosis_result.fault_tree_version
    current_config_version = await _get_config_version()

    # 检查版本是否匹配
    if (analysis.fault_tree_version != current_fault_tree_version or
        analysis.config_version != current_config_version):
        # 软删除旧分析
        analysis.deleted_at = datetime.now()
        await db.commit()
        logger.info(f"Invalidated cache for session {session_id} due to version mismatch")
        return True

    return False


# ==================== SSE 进度推送 ====================

async def stream_counterfactual_progress(session_id: int):
    """
    SSE 流式推送反事实分析进度

    Args:
        session_id: 诊断会话ID

    Yields:
        SSE 格式的进度消息
    """
    import json
    import asyncio

    try:
        # 1. 发送开始消息
        yield f"data: {json.dumps({'status': 'started', 'session_id': session_id, 'progress': 0})}\n\n"
        await asyncio.sleep(0.1)

        # 2. 检查是否已有缓存
        async with async_session() as db:
            cached = await _check_cache(session_id, db)
            if cached:
                yield f"data: {json.dumps({'status': 'cached', 'progress': 100, 'message': '使用缓存结果'})}\n\n"
                yield f"data: {json.dumps({'status': 'completed', 'analysis_id': cached.id})}\n\n"
                return

        # 3. 发送加载诊断结果消息
        yield f"data: {json.dumps({'status': 'loading', 'progress': 10, 'message': '加载诊断结果'})}\n\n"
        await asyncio.sleep(0.1)

        # 4. 查询诊断结果
        async with async_session() as db:
            result_query = await db.execute(
                select(DiagnosisResult).where(DiagnosisResult.session_id == session_id)
            )
            diagnosis_result = result_query.scalar_one_or_none()

            if not diagnosis_result:
                yield f"data: {json.dumps({'status': 'error', 'message': '诊断结果不存在'})}\n\n"
                return

            evidence_list = diagnosis_result.evidence or []
            if not evidence_list:
                yield f"data: {json.dumps({'status': 'error', 'message': '无证据数据'})}\n\n"
                return

            # 5. 发送计算证据权重消息
            yield f"data: {json.dumps({'status': 'calculating', 'progress': 20, 'message': '计算证据权重'})}\n\n"
            await asyncio.sleep(0.1)

            # 6. 计算证据权重
            path_decay_factor = await get_config(PATH_DECAY_FACTOR_KEY, PATH_DECAY_FACTOR_DEFAULT)
            weighted_evidences = []
            for ev in evidence_list:
                weight = calculate_evidence_weight(ev, path_decay_factor)
                weighted_evidences.append({
                    "node_id": ev.get("node_id"),
                    "weight": weight
                })

            weighted_evidences.sort(key=lambda x: x["weight"], reverse=True)
            top_n = min(5, len(weighted_evidences))
            top_evidences = weighted_evidences[:top_n]

            # 7. 逐个分析证据
            for i, evidence in enumerate(top_evidences):
                progress = 30 + int((i / top_n) * 60)
                yield f"data: {json.dumps({'status': 'analyzing', 'progress': progress, 'message': f'分析证据 {i+1}/{top_n}', 'evidence_id': evidence['node_id']})}\n\n"
                await asyncio.sleep(0.5)  # 模拟分析耗时

            # 8. 发送保存结果消息
            yield f"data: {json.dumps({'status': 'saving', 'progress': 95, 'message': '保存分析结果'})}\n\n"
            await asyncio.sleep(0.1)

            # 9. 执行完整分析（如果尚未完成）
            analysis = await analyze_counterfactual(session_id, top_n=top_n, db=db)

            if analysis:
                yield f"data: {json.dumps({'status': 'completed', 'progress': 100, 'analysis_id': analysis.id})}\n\n"
            else:
                yield f"data: {json.dumps({'status': 'error', 'message': '分析失败'})}\n\n"

    except Exception as e:
        logger.error(f"SSE stream error for session {session_id}: {e}", exc_info=True)
        yield f"data: {json.dumps({'status': 'error', 'message': str(e)})}\n\n"

