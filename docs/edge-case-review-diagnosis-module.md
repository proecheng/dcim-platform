# 智能诊断模块 — 边缘用例审查报告

**审查范围**: 58 个 Python 文件（API/Models/Schemas/Services/Engines）
**审查日期**: 2026-03-15
**发现总数**: 225 个未处理边缘用例

---

## 一、安全类问题（Security）— 6 项

| # | 位置 | 触发条件 | 潜在后果 | 修复建议 |
|---|------|---------|---------|---------|
| S1 | diagnosis.py:903 | acknowledged_by 为用户提供的字符串，无身份验证 | 任何用户可冒充他人确认告警 | 使用 current_user.username 替代请求体字段 |
| S2 | diagnosis.py:1295 | report.content 含 XSS 载荷注入 HTML 模板 | 生成 PDF 存在存储型 XSS | 使用 bleach.clean() 清理 Markdown 内容 |
| S3 | misdiagnosis_reports.py:130 | report.file_path 含路径遍历如 '../../etc/passwd' | 任意文件读取 | 验证 file_path 以预期报告目录开头 |
| S4 | condition_parser.py:249 | 右操作数字符串匹配上下文键名导致变量注入 | 字符串字面量 'admin' 被解析为 context['admin'] | 仅对 IDENTIFIER token 解析变量，STRING 不解析 |
| S5 | hmac_manager.py:18 | FAULT_TREE_HMAC_KEY 为空字符串或 None | 空密钥生成的签名仍有效但不安全 | 启动时校验密钥非空，否则 raise ValueError |
| S6 | hmac_key_service.py:57 | new_key 全为空白字符但长度 >= 32 | 弱密钥被接受 | `if len(new_key.strip()) < 32: raise ValueError` |

---

## 二、数据完整性问题（Data Integrity）— 12 项

| # | 位置 | 触发条件 | 潜在后果 | 修复建议 |
|---|------|---------|---------|---------|
| D1 | probability_tuning.py:211 | node.prior_probability 在乐观锁检查前已被修改 | 并发冲突时节点概率已被错误修改 | 将节点更新移到锁获取成功之后 |
| D2 | diagnosis.py:1554 | reject 无乐观锁，与并发 approve 冲突 | 同一条记录同时被批准和拒绝 | 添加 `.with_for_update()` 锁 |
| D3 | ab_testing_service.py:236 | 并发请求同一 device_id 创建重复分配 | 重复的 ABTestDeviceAssignment 行 | 使用 `INSERT ... ON CONFLICT` 或 `SELECT FOR UPDATE` |
| D4 | battery_soh_service.py:286 | 并发调用通过幂等性检查 | 同一设备同天插入重复 SOH 记录 | 添加 (device_id, date) 唯一约束 |
| D5 | ab_testing_service.py:665 | _promote_version 内部 commit 与调用方二次 commit | 双重提交导致中间态可见 | 移除内部 commit，由调用方统一提交 |
| D6 | diagnosis.py:1648 | 两次独立 commit，崩溃导致审计日志丢失 | 配置已更新但审计日志缺失 | 合并为单次 commit |
| D7 | counterfactual_service.py:471 | db.commit 失败后旧记录已删除 | 旧记录删除但新记录未保存 | 添加 `try/except` 回滚 |
| D8 | fallback_store.py:249 | 多个异步任务并发写入同一本地文件 | JSON 行交错产生损坏日志 | 使用 aiofiles 或文件锁 |
| D9 | schemas/diagnosis.py:173 | annotation='inaccurate' 但 actual_root_cause 为 None | 不准确标注缺少根因，破坏分析管道 | 添加 model_validator 交叉校验 |
| D10 | schemas/probability_tuning.py:21 | accurate_count + inaccurate_count > sample_count | 不一致计数被接受 | 添加 model_validator 校验总和 |
| D11 | diagnosis.py:219 | update_data 含 'is_system' 键允许权限提升 | 自定义规则标记为系统规则后无法删除 | `update_data.pop('is_system', None)` |
| D12 | diagnosis.py:219 | update_data 含 'rule_code' 改为已存在编码 | 业务约束违反：重复的 rule_code | 修改前检查唯一性 |

---

## 三、崩溃/异常类问题（Crash/Error）— 35 项

| # | 位置 | 触发条件 | 潜在后果 |
|---|------|---------|---------|
| C1 | fault_tree.py:712 | 子节点缺少 'probability' 属性（悬挂边创建的节点） | KeyError 导致 propagate_probabilities 崩溃 |
| C2 | fault_tree.py:738 | 图含环路；extract_root_cause_path 进入无限 while 循环 | 协程挂起直到 L2 超时 |
| C3 | scheduler.py:94 | get_redis_client() 返回 None 或抛异常 | self.redis.pubsub() 上的 NoneType 错误 |
| C4 | scheduler.py:302 | queue.get() 在 self.running=False 后永久阻塞 | Worker 挂起无法优雅退出 |
| C5 | sensor_fusion_service.py:109 | s.value 为 None（DB JOIN 结果中的 NULL） | np.average 在 None 值列表上崩溃 |
| C6 | sensor_fusion_service.py:113 | 所有权重为零 | np.average 中 ZeroDivisionError |
| C7 | sensor_fusion_service.py:194 | s.updated_at 为 None | TypeError：datetime 减 NoneType |
| C8 | trend_analysis_service.py:76 | row.avg_value 为 None（视图中 NULL 聚合） | float(None) 引发 TypeError |
| C9 | environment_context_service.py:94 | Redis 返回非数字字符串作为温度时间 | ValueError 导致 _load_context 崩溃 |
| C10 | battery_soh_service.py:347 | prev_cycle_count 为 0 | cycle_change_rate 中 ZeroDivisionError |
| C11 | battery_soh_service.py:375 | rated_cycle_count 为 0 | cycle_factor 计算中 ZeroDivisionError |
| C12 | dag_validator.py:36 | 节点字典缺少 'id' 键 | KeyError 导致 validate() 崩溃 |
| C13 | dag_validator.py:55 | 边字典缺少 parent_node_id 或 child_node_id | KeyError 导致 validate() 崩溃 |
| C14 | hmac_key_service.py:74 | old_key 为 None，对 None 切片 old_key[:4] | TypeError: 'NoneType' is not subscriptable |
| C15 | hmac_key_service.py:104 | v.snapshot 为 None（活动版本） | hmac.new 收到 None.encode()，AttributeError |
| C16 | misdiagnosis_report_service.py:841 | fetchone() 返回 None（空表） | 对 None 访问 row.total_diagnosis_count 的 AttributeError |
| C17 | misdiagnosis_report_service.py:656 | db.bind 为 None（会话未绑定引擎） | AttributeError: NoneType.dialect |
| C18 | chaos_drill_service.py:357 | get_redis_client 是异步但未 await | redis 是协程对象，.exists() 抛 TypeError |
| C19 | chaos_drill_service.py:359 | redis.exists/delete 同步调用异步客户端 | 协程未被 await，数据完整性检查失效 |
| C20 | chaos_drill_service.py:160 | trigger_drill 用请求作用域 db session 创建后台任务 | Session 关闭后后台任务报错 |
| C21 | probability_tuning_service.py:183 | FaultTreeNode 未导入 | NameError：_analyze_tree 调用时崩溃 |
| C22 | probability_tuning_service.py:396 | result 字典无 'analyzed_nodes' 键但通知 HTML 引用 | notify_admins 中 KeyError |
| C23 | l2_inference_engine.py:200 | Alarm.level vs Alarm.alarm_level 字段名不匹配 | AttributeError 导致断路器检查崩溃 |
| C24 | l2_inference_engine.py:73 | PointHistory.timestamp vs recorded_at 字段不一致 | AttributeError 或返回空结果 |
| C25 | misdiagnosis_reports.py:135 | report.start_time 为 None（可空字段） | NoneType.year 的 AttributeError |
| C26 | dynamic_threshold_service.py:87 | calculate_dynamic_threshold_sync 在运行事件循环中调用 | 死锁：run_coroutine_threadsafe 在同线程阻塞 |
| C27 | dynamic_threshold_service.py:341 | redis_service._pool 为 None | AttributeError：None.incr |
| C28 | power_topology_service.py:290 | 下游节点缺少 'name' 键 | KeyError 导致 analyze_downstream_impact 崩溃 |
| C29 | trend_analysis_service.py:43 | point_info.unit 为 None（可空列） | 'in' 操作符在 NoneType 上失败 |
| C30 | ab_testing.py:64 | request.strategy_params 为 None | NoneType.model_dump() 的 AttributeError |
| C31 | time_window_tuning_service.py:140 | 过滤后仅 1 个数据点调用 quantiles(n=10) | statistics.StatisticsError |
| C32 | counterfactual_service.py:29 | 模块级 get_settings() 在导入时调用 | 环境变量未设置时 ImportError |
| C33 | fallback_store.py:113 | recover_pending 中 get_redis_client() 失败无 try-except | 未处理异常导致后台恢复任务崩溃 |
| C34 | l1_engine.py:29 | REGISTRY._names_to_collectors 是内部 API | prometheus_client 升级后 AttributeError |
| C35 | environment_context_service.py:32 | ENVIRONMENT_CONTEXT_CACHE_TTL 环境变量为非整数字符串 | 类定义时 ValueError 导致导入崩溃 |

---

## 四、逻辑/语义错误（Logic）— 28 项

| # | 位置 | 触发条件 | 潜在后果 |
|---|------|---------|---------|
| L1 | diagnosis_engine.py:224 | top_confidence_int 恰好为 1；`> 1` 为 False | 置信度 1 被当作 100% 而非 1% |
| L2 | diagnosis_engine.py:99 | reload_rules 但 _loaded=True 返回缓存计数 | 数据库中的规则变更永远不会被重新加载 |
| L3 | l1_engine.py:216 | 字符串比较 '9' > '10' 为 True（字典序） | 产生错误的规则匹配结果 |
| L4 | fault_tree.py:496 | 阈值为负且值为负（温度传感器） | 负值被错误分类为"正常" |
| L5 | fault_tree.py:884 | 多个根节点存在；仅使用第一个无日志 | 静默非确定性根选择 |
| L6 | probability_tuning_service.py:281 | current_prior 为 0.0；max_adjustment 为 0 | 零先验概率永远无法向上调整 |
| L7 | ab_testing_service.py:96 | old_percentage 为 0；任何 new > 0 都触发拒绝 | 无法从 0% 灰度扩展，A/B 测试卡住 |
| L8 | diagnosis.py:600 | GET /battery-soh/latest 被 /{device_id} 路由遮蔽 | 'latest' 被解析为 device_id |
| L9 | probability_tuning.py:82 | tree_id=0 绕过 'if tree_id:' 守卫 | 分析所有树而非 id=0 的树 |
| L10 | battery_soh_service.py:87 | rated_resistance=0（有效数字）被视为缺失 | 有效零值被拒绝 |
| L11 | trend_analysis_service.py:219 | zone_id=0 是假值但是有效整数 | 跳过区域过滤，返回所有警告 |
| L12 | diagnosis_engine.py:347 | sensor_weight 为 0 | 零权重将置信度折叠到先验值 |
| L13 | l2_inference_engine.py:148 | node.sigmoid_k 为 0 | sigmoid 始终返回 0.5 |
| L14 | l2_inference_engine.py:112 | time_window 为 0 或负数 | 截止时间在未来，查询无结果 |
| L15 | condition_parser.py:126 | 单个 '=' 字符产生的操作符不匹配任何比较分支 | 本意等式检查静默返回 False |
| L16 | condition_parser.py:157 | parse() 不检查表达式后的尾随 token | 静默忽略畸形输入如 'a > 1 GARBAGE' |
| L17 | battery_soh_service.py:553 | 多个 UPS 共享同一 FaultTreeNode | 一个坏电池提升所有 UPS 故障节点的先验概率 |
| L18 | battery_soh_service.py:566 | 日志读取已更新的 new_prior 两次 | 日志中新旧值显示相同 |
| L19 | misdiagnosis_report_service.py:137 | false_positive_count > annotated_count 时准确率为负 | 报告中显示负准确率 |
| L20 | misdiagnosis_report_service.py:397 | 1月做 month-3 时月份计算错误 | 月份为负值导致错误统计 |
| L21 | misdiagnosis_report_service.py:1246 | os.chmod 在 Windows 平台调用 | OSError 或静默失败 |
| L22 | diagnosis.py:1182 | soft delete 用 naive datetime.now() 而非 UTC | 时区不一致 |
| L23 | diagnosis.py:1461 | approved_at 用 naive datetime.now() 而非 UTC | 跨服务器排序 bug |
| L24 | ab_testing_service.py:486 | float 乘法后 int() 丢失精度 | 卡方检验使用四舍五入计数，降低统计功效 |
| L25 | power_topology_service.py:326 | 循环变量 'node_id' 覆盖参数 'node_id' | 循环后 node_id 变成最后一个上游节点 |
| L26 | power_topology_service.py:176 | 删除节点但下游孤儿节点保留 | 图中出现带悬挂边的孤儿节点 |
| L27 | push_service.py:204 | 低置信度重试返回 'skipped' 而非 'pushed' | 低置信度重试无限循环直到最大重试次数 |
| L28 | priority_queue.py:39 | _cancelled_count 超过 len(_queue) 导致 active_size 为负 | 负 active_size 绕过 maxsize 检查，队列无限增长 |

---

## 五、输入验证缺失（Validation）— 25 项

| # | 位置 | 触发条件 | 修复建议 |
|---|------|---------|---------|
| V1 | diagnosis.py:317-328 | 无效 ISO 日期字符串被静默忽略 | raise HTTPException(400) |
| V2 | diagnosis.py:430-440 | 无效 start/end_time 被静默忽略 | raise HTTPException(400) |
| V3 | diagnosis.py:1137-1148 | 反事实列表中无效日期被静默忽略 | raise HTTPException(400) |
| V4 | diagnosis.py:1231 | period 参数无格式验证 | 正则校验 `^\d{4}-\d{2}$` |
| V5 | diagnosis.py:1347 | device_type 无长度限制 | `Query(None, max_length=50)` |
| V6 | diagnosis.py:1712 | body: dict 接受任意 JSON 无 schema 验证 | 使用 Pydantic 模型 |
| V7 | diagnosis.py:98 | device_type 含 SQL 通配符 % 或 _ | 转义通配符字符 |
| V8 | probability_tuning.py:100 | skip 为负数（无 ge=0 约束） | `Query(0, ge=0)` |
| V9 | probability_tuning.py:101 | limit 无上限（如 limit=999999） | `Query(20, ge=1, le=100)` |
| V10 | probability_tuning.py:118 | status 接受任意字符串无枚举验证 | 使用 `Literal['pending','approved','rejected']` |
| V11 | fault_tree_versions.py:146 | status 接受任意字符串 | 使用 `Literal[...]` 枚举 |
| V12 | hmac_key_service.py:209 | page <= 0 传入 | `page = max(1, page)` |
| V13 | training_data_audit_service.py:264 | page/page_size <= 0 | 同上 |
| V14 | misdiagnosis_report_service.py:85 | period 格式如 '2024-13' 月份越界 | 正则验证 + 范围检查 |
| V15 | misdiagnosis_reports.py:156 | start_date > end_date | raise HTTPException(400) |
| V16 | schemas/ab_testing.py:31 | strategy 与 strategy_params 类型不匹配 | 添加 model_validator 交叉校验 |
| V17 | schemas/probability_tuning.py:20 | adjustment_percent 无边界约束 | `Field(..., ge=-100.0, le=1000.0)` |
| V18 | condition_parser.py:294 | 空字符串作为条件表达式 | `if not condition.strip(): return False` |
| V19 | condition_parser.py:70 | 字符串字面量无结束引号（EOF） | raise ValueError('Unterminated string') |
| V20 | diagnosis.py:1534 | reject 的 reason 为空字符串 | `if not reason: raise HTTPException(400)` |
| V21 | ab_testing.py:91 | A/B 测试列表无分页支持 | 添加 skip/limit 参数 |
| V22 | diagnosis.py:1259 | format 参数无枚举约束 | `Query('pdf', pattern='^pdf$')` |
| V23 | annotation_anomaly.py:70 | annotator_id 为 NULL | `if row.annotator_id is None: continue` |
| V24 | training_data_audit_service.py:67 | features 数组含 NaN 或 Inf | `np.nan_to_num()` 处理 |
| V25 | training_data_audit_service.py:178 | naive 与 aware datetime 混合比较 | 统一时区处理 |

---

## 六、资源/性能问题（Resource）— 10 项

| # | 位置 | 触发条件 | 潜在后果 |
|---|------|---------|---------|
| R1 | diagnosis_engine.py:111 | _alarm_counter 无限增长无上限 | 持续运行多天后内存泄漏 |
| R2 | l2_inference_engine.py:57 | 每次调用创建 Redis 连接无连接池 | 高并发下 Redis 'max clients' 错误 |
| R3 | fault_tree.py:158 | 所有缓存条目 ref_count > 0 时 LRU 驱逐失败 | 缓存超出 max_size 无限增长 |
| R4 | diagnosis_engine.py:114 | create_task 无引用导致异常静默丢失 | Python 3.12+ 警告 'Task exception never retrieved' |
| R5 | sensor_metadata_service.py:26 | 类级可变 _cache 跨异步上下文共享无锁 | 竞态条件：get() 读到过期/部分数据 |
| R6 | dynamic_threshold_service.py:61 | 类级可变 _rules_cache 跨请求共享 | 一个请求修改列表时另一个正在迭代 |
| R7 | environment_context_service.py:30 | _cache 字典无锁保护的 TOCTOU 竞态 | 缓存失效检查与返回之间被刷新 |
| R8 | power_topology_service.py:159 | deepcopy 含 DB 模型引用的大型 DiGraph | 深拷贝失败或拷贝已分离的 SQLAlchemy 对象 |
| R9 | circuit_breaker.py:50 | Lock 在一个事件循环中创建但在另一个中使用 | RuntimeError: Task got Future attached to different loop |
| R10 | chaos_drill_service.py:50 | asyncio.Lock 在导入时创建（事件循环外） | Lock 绑定错误的事件循环 |

---

## 七、SQL 注入风险（SQLi）— 1 项

| # | 位置 | 触发条件 | 潜在后果 | 修复建议 |
|---|------|---------|---------|---------|
| Q1 | trend_analysis_service.py:52 | view_name 通过 f-string 拼入 raw text() SQL | SQL 注入 | 使用白名单校验 view_name |

---

## 优先级建议

### P0 — 立即修复（安全 + 数据完整性 + 崩溃高频）
- S1-S6（安全类全部）
- Q1（SQL 注入）
- D1-D3（并发数据竞态）
- C1-C5（高频崩溃路径）
- C18-C19（chaos_drill 异步调用错误）
- C21-C22（NameError/KeyError 导致功能不可用）

### P1 — 尽快修复（逻辑错误 + 中频崩溃）
- L1-L9（影响诊断准确性的逻辑错误）
- C6-C17（中频崩溃路径）
- D4-D12（数据一致性问题）
- R1-R2（内存泄漏和连接耗尽）

### P2 — 计划修复（验证 + 性能 + 低频问题）
- V1-V25（输入验证缺失）
- L10-L28（低频逻辑问题）
- R3-R10（性能和竞态条件）
- C23-C35（低频崩溃路径）
