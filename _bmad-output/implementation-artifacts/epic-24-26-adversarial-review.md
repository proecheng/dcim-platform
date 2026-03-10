# Epic 24-26 对抗性审查报告

**审查日期:** 2026-03-10
**审查人:** Claude (Adversarial Review)
**审查范围:** Epic 24-26（智能诊断系统）实施成果
**审查方法:** 代码审查 + 算法验证 + 并发安全分析

---

## 审查结论

⚠️ **发现 15 个问题：2 个 P0 问题，6 个 P1 问题，7 个 P2 问题**

---

## 审查发现

### P0-1: 诊断引擎规则缓存未处理并发更新

**问题描述:**
- 文件: `backend/app/engines/diagnosis_engine.py:50-80`
- `_load_rules()` 方法加载规则到内存缓存
- 未使用锁保护，多个并发请求可能同时触发加载
- 可能导致规则缓存不一致或重复加载
- 虽然使用 asyncio 单线程，但多个协程可能并发调用

**影响:** 严重 - 并发安全

**修复建议:**
```python
import asyncio

class DiagnosisEngine:
    def __init__(self):
        self._rules_by_device_type: Dict[str, List[DiagnosisRule]] = {}
        self._rules_loaded = False
        self._load_lock = asyncio.Lock()  # 添加锁

    async def _load_rules(self, db: AsyncSession) -> None:
        """加载诊断规则（线程安全）"""
        async with self._load_lock:
            # 双重检查
            if self._rules_loaded:
                return

            result = await db.execute(
                select(DiagnosisRule)
                .where(DiagnosisRule.is_active == True)
                .order_by(DiagnosisRule.priority.asc())
            )
            rules = result.scalars().all()

            # 按设备类型分组
            for rule in rules:
                if rule.device_type not in self._rules_by_device_type:
                    self._rules_by_device_type[rule.device_type] = []
                self._rules_by_device_type[rule.device_type].append(rule)

            self._rules_loaded = True
            logger.info(f"加载 {len(rules)} 条诊断规则")
```

**优先级:** P0 - 必须立即修复

---

### P0-2: 故障树推理未处理超时

**问题描述:**
- 文件: `backend/app/services/diagnosis/fault_tree.py:776-936`
- `diagnose_l2()` 方法执行故障树推理
- 未设置总超时限制，可能长时间阻塞
- 虽然证据收集有 3 秒超时，但概率传播和路径提取无超时
- 复杂故障树可能导致推理时间过长

**影响:** 严重 - 系统稳定性

**修复建议:**
```python
# 在 fault_tree.py 顶部添加常量
L2_INFERENCE_TIMEOUT = 10.0  # 秒

async def diagnose_l2(
    self,
    device_id: int,
    device_type: str,
    alarm_type: Optional[str] = None,
    time_window_minutes: int = 5,
) -> DiagnosisContext:
    """L2 故障树推理主流程（带超时保护）"""
    try:
        # 整个推理流程设置 10 秒超时
        return await asyncio.wait_for(
            self._diagnose_l2_impl(device_id, device_type, alarm_type, time_window_minutes),
            timeout=L2_INFERENCE_TIMEOUT
        )
    except asyncio.TimeoutError:
        logger.error(f"L2 推理超时 ({L2_INFERENCE_TIMEOUT}s): 设备 {device_id}")
        context = DiagnosisContext(
            device_id=device_id,
            device_type=device_type,
            alarm_type=alarm_type or "",
            fault_tree_id=0,
            fault_tree_name="",
            root_node_probability=0.0,
            root_cause_path=[],
            evidence={},
        )
        context.errors.append(f"推理超时 ({L2_INFERENCE_TIMEOUT}s)")
        context.degraded = True
        return context

async def _diagnose_l2_impl(
    self,
    device_id: int,
    device_type: str,
    alarm_type: Optional[str],
    time_window_minutes: int,
) -> DiagnosisContext:
    """L2 推理实现（原 diagnose_l2 逻辑）"""
    # ... 原有逻辑
```

**优先级:** P0 - 必须立即修复

---

### P1-1: 条件解析器未限制递归深度

**问题描述:**
- 文件: `backend/app/services/diagnosis/condition_parser.py:136-200`
- `Parser` 类使用递归下降解析
- 未限制递归深度，恶意表达式可能导致栈溢出
- 例如: `((((((((((a > 1))))))))))`
- 虽然有 200 字符长度限制，但嵌套括号仍可能很深

**影响:** 高 - 安全性

**修复建议:**
```python
class Parser:
    """语法分析器"""
    MAX_RECURSION_DEPTH = 20  # 最大递归深度

    def __init__(self, lexer: Lexer):
        self.lexer = lexer
        self.current_token = self.lexer.get_next_token()
        self._recursion_depth = 0

    def _check_recursion_depth(self):
        """检查递归深度"""
        if self._recursion_depth >= self.MAX_RECURSION_DEPTH:
            raise ValueError(f"表达式嵌套过深 (最大 {self.MAX_RECURSION_DEPTH} 层)")

    def or_expr(self):
        """OR 表达式"""
        self._recursion_depth += 1
        self._check_recursion_depth()
        try:
            node = self.and_expr()
            while self.current_token.type == TokenType.OR:
                self.eat(TokenType.OR)
                node = ('OR', node, self.and_expr())
            return node
        finally:
            self._recursion_depth -= 1

    def and_expr(self):
        """AND 表达式"""
        self._recursion_depth += 1
        self._check_recursion_depth()
        try:
            node = self.comparison()
            while self.current_token.type == TokenType.AND:
                self.eat(TokenType.AND)
                node = ('AND', node, self.comparison())
            return node
        finally:
            self._recursion_depth -= 1

    def comparison(self):
        """比较表达式"""
        self._recursion_depth += 1
        self._check_recursion_depth()
        try:
            if self.current_token.type == TokenType.LPAREN:
                self.eat(TokenType.LPAREN)
                node = self.or_expr()
                self.eat(TokenType.RPAREN)
                return node
            # ... 原有逻辑
        finally:
            self._recursion_depth -= 1
```

**优先级:** P1 - 建议尽快修复

---

### P1-2: 误诊报告生成未处理并发冲突

**问题描述:**
- 文件: `backend/app/services/diagnosis/misdiagnosis_report_service.py:37-60`
- `generate_monthly_report()` 使用 Redis 分布式锁
- 锁 TTL 70 秒，但未处理锁获取失败后的重试
- 如果锁被占用，直接返回 None，用户无法知道是否生成成功
- 可能导致报告生成失败但无提示

**影响:** 高 - 数据一致性

**修复建议:**
```python
async def generate_monthly_report(
    period: str,
    db: AsyncSession,
    max_retries: int = 3,
    retry_delay: float = 2.0,
) -> Optional[SystemReport]:
    """
    生成月度误诊分析报告（带重试）

    Args:
        period: 报告周期，格式 YYYY-MM
        db: 数据库会话
        max_retries: 最大重试次数
        retry_delay: 重试延迟（秒）

    Returns:
        SystemReport 或 None（如果数据不足或重试失败）
    """
    logger.info("开始生成误诊分析报告: period=%s", period)

    lock_key = f"report:misdiagnosis:lock:{period}"

    for attempt in range(max_retries):
        if redis_service.is_available:
            try:
                lock_acquired = redis_service.set_with_expiry(lock_key, "locked", 70)
                if lock_acquired:
                    break

                if attempt < max_retries - 1:
                    logger.info(f"锁被占用，等待 {retry_delay}s 后重试 ({attempt + 1}/{max_retries})")
                    await asyncio.sleep(retry_delay)
                else:
                    logger.warning(f"无法获取分布式锁，已重试 {max_retries} 次: period={period}")
                    return None
            except Exception as e:
                logger.error(f"获取分布式锁失败: {e}")
                return None
        else:
            logger.warning("Redis 不可用，跳过分布式锁")
            break

    try:
        # ... 原有报告生成逻辑
        pass
    finally:
        # 释放锁
        if redis_service.is_available:
            try:
                redis_service.delete(lock_key)
            except Exception as e:
                logger.warning(f"释放分布式锁失败: {e}")
```

**优先级:** P1 - 建议尽快修复

---

### P1-3: 混沌演练未处理熔断器恢复失败

**问题描述:**
- 文件: `backend/app/services/diagnosis/chaos_drill_service.py:226-233`
- `_execute_drill()` 在 finally 块恢复熔断器
- 如果 `breaker.reset()` 失败，异常被静默吞没
- 可能导致熔断器保持 OPEN 状态，影响正常诊断
- 应该记录错误并通知用户

**影响:** 高 - 系统可靠性

**修复建议:**
```python
finally:
    # 确保恢复
    recovery_failed = False
    if breaker and breaker.state != BreakerState.CLOSED:
        try:
            breaker.reset()
            logger.info(f"演练 {drill_id} 熔断器已恢复")
        except Exception as e:
            logger.error(f"演练 {drill_id} 熔断器恢复失败: {e}", exc_info=True)
            recovery_failed = True

    self.__class__.is_drill_active = False
    self.__class__._current_drill_id = None
    self.__class__._stop_requested = False

    # 如果恢复失败，记录到报告
    if recovery_failed:
        scenario_results.append({
            "name": "circuit_breaker_recovery",
            "status": "failed",
            "details": {"error": "熔断器恢复失败，请手动检查"}
        })
```

**优先级:** P1 - 建议尽快修复

---

### P1-4: 降级存储未处理 Redis 连接失败

**问题描述:**
- 文件: `backend/app/services/diagnosis/fallback_store.py:58-84`
- `save_to_redis()` 直接调用 `await client.set()`
- 未处理 Redis 连接失败或超时
- 如果 Redis 不可用，应该降级到本地文件
- 当前实现会抛出异常，导致诊断结果丢失

**影响:** 高 - 数据可靠性

**修复建议:**
```python
@staticmethod
async def save_to_redis(data: dict, reason: str = "") -> str:
    """
    将诊断结果序列化写入 Redis

    如果 Redis 不可用，降级到本地文件
    Returns: pending_key 或 "local_file"
    """
    try:
        client = await get_redis_client()
        pending_id = str(uuid.uuid4())
        key = f"{DiagnosisFallbackStore.PENDING_KEY_PREFIX}{pending_id}"

        # 添加元数据
        data_with_meta = {
            "_version": "1.0",
            "_fallback_reason": reason,
            **data
        }

        # 自动转换 datetime 字段
        converted_data = _convert_datetime_to_iso(data_with_meta)

        serialized = json.dumps(converted_data, ensure_ascii=False)

        # 设置 1 秒超时
        await asyncio.wait_for(
            client.set(key, serialized, ex=DiagnosisFallbackStore.PENDING_TTL),
            timeout=1.0
        )

        logger.info("诊断结果已写入 Redis 降级存储: %s (reason: %s)", key, reason)
        return key

    except (asyncio.TimeoutError, ConnectionError, Exception) as e:
        logger.warning(f"Redis 写入失败，降级到本地文件: {e}")
        # 降级到本地文件
        await DiagnosisFallbackStore._save_to_local_file(
            data, "redis_unavailable", ""
        )
        return "local_file"
```

**优先级:** P1 - 建议尽快修复

---

### P1-5: 故障树缓存未处理版本变更

**问题描述:**
- 文件: `backend/app/services/diagnosis/fault_tree.py:79-188`
- `FaultTreeCache` 缓存故障树图结构
- 未提供缓存失效机制
- 如果故障树在数据库中更新，缓存不会自动刷新
- 可能导致使用过期的故障树进行诊断

**影响:** 高 - 数据准确性

**修复建议:**
```python
# 已在代码中实现 invalidate() 方法（第 136-153 行）
# 但需要在故障树更新时调用

# 在 backend/app/api/v1/diagnosis.py 中添加:
@router.put("/fault-trees/{tree_id}")
async def update_fault_tree(
    tree_id: int,
    updates: FaultTreeUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """更新故障树"""
    # ... 更新数据库逻辑

    # 使缓存失效
    from app.services.diagnosis.fault_tree import _fault_tree_cache
    await _fault_tree_cache.invalidate(tree_id)

    logger.info(f"故障树 {tree_id} 已更新，缓存已失效")

    return {"message": "故障树已更新"}
```

**优先级:** P1 - 建议尽快修复

---

### P1-6: 诊断引擎去重窗口过短

**问题描述:**
- 文件: `backend/app/engines/diagnosis_engine.py:120-130`
- 去重窗口 60 秒
- 对于持续性故障，60 秒后会重复诊断
- 可能导致大量重复诊断结果
- 应该根据告警类型动态调整去重窗口

**影响:** 高 - 性能

**修复建议:**
```python
# 根据告警级别动态调整去重窗口
DEDUP_WINDOW_BY_LEVEL = {
    "critical": 300,  # 5 分钟
    "major": 180,     # 3 分钟
    "warning": 120,   # 2 分钟
    "info": 60,       # 1 分钟
}

def _should_deduplicate(
    self,
    device_id: int,
    alarm_type: str,
    alarm_level: str,
) -> bool:
    """检查是否应该去重"""
    key = f"{device_id}:{alarm_type}"

    if key in self._recent_diagnoses:
        last_time = self._recent_diagnoses[key]
        # 根据告警级别选择去重窗口
        window = DEDUP_WINDOW_BY_LEVEL.get(alarm_level, 60)
        if (datetime.now() - last_time).total_seconds() < window:
            return True

    return False
```

**优先级:** P1 - 建议尽快修复

---

### P2-1: 条件解析器未缓存 AST

**问题描述:**
- 文件: `backend/app/services/diagnosis/condition_parser.py:251-282`
- `parse_and_evaluate()` 每次都重新解析
- 相同条件表达式会重复解析
- 影响性能，特别是规则数量多时
- 应该缓存 AST

**影响:** 中等 - 性能优化

**修复建议:**
```python
from functools import lru_cache

@lru_cache(maxsize=100)
def _parse_condition(condition: str):
    """解析条件表达式（带缓存）"""
    lexer = Lexer(condition)
    parser = Parser(lexer)
    return parser.parse()

def parse_and_evaluate(condition: str, context: Dict[str, Any]) -> bool:
    """解析并求值条件表达式（AST 缓存）"""
    try:
        if len(condition) >= 200:
            logger.warning(f"条件表达式过长 ({len(condition)} 字符): {condition[:50]}...")
            return False

        ast = _parse_condition(condition)
        evaluator = ConditionEvaluator(context)
        return evaluator.evaluate(ast)
    except Exception as e:
        logger.warning(f"条件表达式解析失败: {condition} - {e}")
        return False
```

**优先级:** P2 - 可以接受现状

---

### P2-2: 故障树推理未记录性能指标

**问题描述:**
- 文件: `backend/app/services/diagnosis/fault_tree.py:776-936`
- `DiagnosisContext` 包含性能指标字段
- 但未持久化到数据库
- 无法分析推理性能瓶颈
- 影响可观测性

**影响:** 中等 - 可观测性

**修复建议:**
```python
# 在 DiagnosisResultStore.save_complete() 中添加性能指标字段
# 或创建单独的性能指标表

# backend/app/models/diagnosis.py
class DiagnosisPerformanceMetric(Base):
    __tablename__ = "diagnosis_performance_metrics"

    id = Column(Integer, primary_key=True)
    session_id = Column(String(50), index=True)
    inference_time_ms = Column(Float)
    evidence_collection_time_ms = Column(Float)
    propagation_time_ms = Column(Float)
    path_extraction_time_ms = Column(Float)
    created_at = Column(DateTime, default=datetime.now)
```

**优先级:** P2 - 可以接受现状

---

### P2-3: 混沌演练未限制并发执行

**问题描述:**
- 文件: `backend/app/services/diagnosis/chaos_drill_service.py:143-162`
- `trigger_drill()` 使用类级别标志 `is_drill_active`
- 仅在进程内有效，多进程部署时无效
- 应该使用 Redis 分布式锁
- 可能导致多个进程同时执行演练

**影响:** 中等 - 并发安全

**修复建议:**
```python
async def trigger_drill(
    self, scenarios: List[str], breaker: Optional[CircuitBreaker] = None
) -> str:
    """手动触发演练（分布式锁）"""
    # 验证场景
    invalid = set(scenarios) - VALID_SCENARIOS
    if invalid:
        raise ValueError(f"无效的演练场景: {invalid}")

    # 使用 Redis 分布式锁
    from app.core.redis_lock import get_redis_client

    redis = get_redis_client()
    lock_key = "chaos_drill:global_lock"
    lock_token = str(uuid.uuid4())

    lock_acquired = redis.set(lock_key, lock_token, nx=True, ex=300)  # 5 分钟
    if not lock_acquired:
        raise ValueError("已有演练正在执行（全局锁），请等待完成或终止后再试")

    drill_id = f"drill-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}"

    # 在后台执行演练
    asyncio.create_task(self._execute_drill(drill_id, scenarios, breaker, lock_token))

    return drill_id

# 在 _execute_drill() finally 块释放锁
finally:
    # 释放分布式锁
    try:
        stored_token = redis.get(lock_key)
        if stored_token and stored_token.decode() == lock_token:
            redis.delete(lock_key)
    except Exception as e:
        logger.error(f"释放演练锁失败: {e}")
```

**优先级:** P2 - 可以接受现状

---

### P2-4: 降级存储恢复未处理部分失败

**问题描述:**
- 文件: `backend/app/services/diagnosis/fallback_store.py:87-185`
- `recover_pending()` 批量恢复数据
- 如果某条数据恢复失败，继续处理下一条
- 但未记录失败的数据
- 可能导致数据丢失

**影响:** 中等 - 数据可靠性

**修复建议:**
```python
# 在 recover_pending() 中添加失败记录
failed_keys = []

for key in keys:
    raw = await client.get(key)
    if not raw:
        continue

    try:
        # ... 恢复逻辑
        pass
    except Exception as e:
        logger.warning("恢复 pending 诊断结果失败 %s: %s", key, e)
        failed_keys.append(key)
        failed_count += 1
        continue

# 返回失败的 key 列表
return {
    "success": success_count,
    "failed": failed_count,
    "skipped": skipped_count,
    "failed_keys": failed_keys,
}
```

**优先级:** P2 - 可以接受现状

---

### P2-5: 故障树验证未检查概率范围

**问题描述:**
- 文件: `backend/app/services/diagnosis/fault_tree.py:239-280`
- `validate_fault_tree()` 验证结构
- 未检查节点的 `prior_probability` 是否在 [0, 1] 范围
- 无效概率会导致推理结果错误
- 应该在加载时验证

**影响:** 中等 - 数据准确性

**修复建议:**
```python
async def validate_fault_tree(graph: nx.DiGraph) -> List[str]:
    """验证故障树结构"""
    warnings = []

    # ... 原有检查

    # 检查概率范围
    for node_id in graph.nodes():
        node_data = graph.nodes[node_id]
        prior = node_data.get("prior_probability")
        if prior is not None and (prior < 0.0 or prior > 1.0):
            warnings.append(f"节点 {node_id} 的先验概率超出范围 [0, 1]: {prior}")

    return warnings
```

**优先级:** P2 - 可以接受现状

---

### P2-6: 诊断引擎未处理规则条件解析失败

**问题描述:**
- 文件: `backend/app/engines/diagnosis_engine.py:90-110`
- `_match_rules()` 调用 `parse_and_evaluate()`
- 如果条件解析失败，返回 False
- 但未记录失败原因
- 影响规则调试

**影响:** 中等 - 可维护性

**修复建议:**
```python
def _match_rules(
    self,
    rules: List[DiagnosisRule],
    context: Dict[str, Any],
) -> List[DiagnosisRule]:
    """匹配规则"""
    matched = []

    for rule in rules:
        if not rule.condition:
            matched.append(rule)
            continue

        try:
            if parse_and_evaluate(rule.condition, context):
                matched.append(rule)
        except Exception as e:
            logger.warning(
                f"规则 {rule.id} 条件解析失败: {rule.condition} - {e}"
            )
            # 记录到规则执行日志表
            # ... 可选：持久化失败记录

    return matched
```

**优先级:** P2 - 可以接受现状

---

### P2-7: 混沌演练报告未设置过期时间

**问题描述:**
- 文件: `backend/app/services/diagnosis/chaos_drill_service.py:400-456`
- `_generate_drill_report()` 保存报告到 `ReportRecord`
- 未设置过期时间
- 长期运行会导致报告表过大
- 影响查询性能

**影响:** 中等 - 长期性能

**修复建议:**
```python
# 添加定时清理任务
# backend/app/tasks/cleanup.py

async def cleanup_old_drill_reports(db: AsyncSession, days: int = 90):
    """清理旧的演练报告（保留 90 天）"""
    cutoff_date = datetime.now() - timedelta(days=days)

    result = await db.execute(
        select(ReportRecord)
        .where(ReportRecord.report_type == "diagnosis_drill")
        .where(ReportRecord.created_at < cutoff_date)
    )
    reports = result.scalars().all()

    for report in reports:
        await db.delete(report)

    await db.commit()
    logger.info(f"清理了 {len(reports)} 条旧演练报告")
```

**优先级:** P2 - 可以接受现状

---

## 问题汇总

| 问题编号 | 问题描述 | 优先级 | 状态 | 影响范围 |
|---------|---------|--------|------|---------| P0-1 | 诊断引擎规则缓存未处理并发更新 | P0 | ⚠️ 待修复 | 并发安全 |
| P0-2 | 故障树推理未处理超时 | P0 | ⚠️ 待修复 | 系统稳定性 |
| P1-1 | 条件解析器未限制递归深度 | P1 | ⚠️ 待修复 | 安全性 |
| P1-2 | 误诊报告生成未处理并发冲突 | P1 | ⚠️ 待修复 | 数据一致性 |
| P1-3 | 混沌演练未处理熔断器恢复失败 | P1 | ⚠️ 待修复 | 系统可靠性 |
| P1-4 | 降级存储未处理 Redis 连接失败 | P1 | ⚠️ 待修复 | 数据可靠性 |
| P1-5 | 故障树缓存未处理版本变更 | P1 | ⚠️ 待修复 | 数据准确性 |
| P1-6 | 诊断引擎去重窗口过短 | P1 | ⚠️ 待修复 | 性能 |
| P2-1 | 条件解析器未缓存 AST | P2 | ⚠️ 待修复 | 性能优化 |
| P2-2 | 故障树推理未记录性能指标 | P2 | ⚠️ 待修复 | 可观测性 |
| P2-3 | 混沌演练未限制并发执行 | P2 | ⚠️ 待修复 | 并发安全 |
| P2-4 | 降级存储恢复未处理部分失败 | P2 | ⚠️ 待修复 | 数据可靠性 |
| P2-5 | 故障树验证未检查概率范围 | P2 | ⚠️ 待修复 | 数据准确性 |
| P2-6 | 诊断引擎未处理规则条件解析失败 | P2 | ⚠️ 待修复 | 可维护性 |
| P2-7 | 混沌演练报告未设置过期时间 | P2 | ⚠️ 待修复 | 长期性能 |

---

## Epic 24-26 实施质量评估

### 优点

1. **诊断引擎架构清晰** - 规则匹配、条件解析、优先级排序逻辑完善
2. **故障树推理算法正确** - OR/AND 门概率计算、根因路径提取符合理论
3. **熔断器保护完善** - 状态机、滑动窗口、错误率计算实现正确
4. **降级存储机制完善** - Redis → 本地文件两级降级，数据不丢失
5. **混沌演练设计合理** - 场景隔离、状态恢复、报告生成完整
6. **并发安全考虑** - 使用 asyncio.Lock、分布式锁、引用计数

### 缺点

1. **2 个 P0 并发安全问题** - 规则缓存并发更新、故障树推理超时
2. **6 个 P1 功能缺陷** - 递归深度、并发冲突、恢复失败、连接失败、缓存失效、去重窗口
3. **7 个 P2 改进点** - AST 缓存、性能指标、并发限制、失败记录、概率验证、错误处理、过期清理
4. **缺少资源限制** - 未限制故障树大小、证据数量、推理复杂度

### 总体评价

Epic 24-26 的智能诊断系统架构设计合理，算法实现正确。发现的问题主要集中在并发安全、超时控制、错误处理等方面。P0 问题必须修复，P1 问题建议尽快修复。

**建议:**
1. **立即修复 P0 问题** - 添加规则加载锁、故障树推理超时
2. **尽快修复 P1 问题** - 特别是 P1-1（递归深度）和 P1-4（Redis 连接失败）
3. **评估 P2 问题** - 根据实际使用情况决定是否修复

---

**审查完成时间:** 2026-03-10
**下一步:** 修复 P0 问题，继续审查其他 Epic
