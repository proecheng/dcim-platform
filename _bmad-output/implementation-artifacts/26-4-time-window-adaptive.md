# Story 26.4: 时间窗口自适应

**Epic**: Epic 26 - 智能诊断高级功能 (Phase 3)
**Story ID**: 26.4
**Story Key**: 26-4-time-window-adaptive
**优先级**: P2 (推广阶段)
**估算**: 3 天
**状态**: ready-for-dev
**创建日期**: 2026-03-08

---

## 1. Story 概述

### 1.1 业务价值

为智能诊断系统添加"时间窗口自适应"功能，系统基于历史故障持续时间数据自动优化不同设备类型的诊断时间窗口参数，使证据收集窗口更精准。

**用户故事**: 作为管理员，我希望系统自动优化诊断时间窗口参数，以便不同类型故障的证据收集窗口更精准。

**业务价值**:
- 自动化时间窗口优化，减少人工调参工作量
- 基于真实故障持续时间数据优化证据收集窗口
- 不同设备类型使用不同时间窗口，提高诊断准确性
- 提供审批机制，确保参数调整可控可追溯
- 为智能诊断系统持续优化提供数据支撑

### 1.2 前置条件

**必须完成的 Story**:
- Story 24.6: 诊断结果存储与分级推送（已完成）
- Story 24.8: 诊断结果标注与RBAC（已完成）
- Story 26.2: 误诊反馈报告（已完成）

**数据要求**:
- 至少有 30 条针对同一设备类型的"准确"标注的诊断记录
  - 30 样本阈值基于统计学最小样本量要求（P90 百分位数计算需要足够样本）
  - 实际业务中，30 样本可提供合理的 P50/P90 估计
- 标注数据必须是"准确"类型（annotation='accurate'）
- 诊断对应的源告警必须已恢复（alarm.recovered_at IS NOT NULL）

**技术要求**:
- APScheduler 定时任务已配置
- PostgreSQL 数据库已配置（需要 percentile_cont 函数）
- system_configs 表已存在并包含 diagnosis_time_windows 配置
  - 表结构: id (SERIAL PRIMARY KEY), config_key (VARCHAR(100) UNIQUE), config_value (JSONB/JSON), description (TEXT), created_at, updated_at
  - PostgreSQL 使用 JSONB 类型，SQLite 使用 JSON 类型（TEXT 存储）
  - diagnosis_time_windows 配置必须包含 "default" 键作为默认值
- diagnosis_results 表必须有 alarm_id 字段（外键关联 alarms 表）
- Python 标准库 statistics 模块（Python 3.8+，用于 P50/P90 计算）

### 1.3 验收标准

**功能验收**:
- [ ] APScheduler 每月定时任务执行时间窗口分析
- [ ] 统计每个设备类型的故障持续时间 P50（中位数）和 P90
- [ ] 建议时间窗口 = P90 × 1.2（留 20% 裕度）
- [ ] 调整范围限制：最小 1 分钟，最大 120 分钟
- [ ] 生成"时间窗口调整建议"存储到 `time_window_adjustment_logs` 表
- [ ] 通知管理员审批（通过邮件/WebSocket 推送，失败时记录日志）
- [ ] 管理员审批确认后，更新 `system_configs` 中的 `diagnosis_time_windows` 配置
- [ ] 调整记录可追溯（包含调整前后时间窗口、样本数、P50/P90 统计值、审批人、审批时间）

**性能验收**:
- [ ] 单次时间窗口分析耗时 < 30 秒（基于 1000 条标注数据）
- [ ] 时间窗口分析不影响正常诊断流程（异步执行）

**安全验收**:
- [ ] 时间窗口调整审批按 RBAC 权限控制（仅管理员可审批）
- [ ] 调整操作记录审计日志（满足 ISO 27001/SOC 2 要求）

**测试验收**:
- [ ] 单元测试覆盖率 ≥ 80%
- [ ] 集成测试覆盖核心场景（时间窗口分析、审批流程、配置更新）

---

## 2. 技术设计

### 2.1 架构设计

**模块位置**: `backend/app/services/diagnosis/time_window_tuning_service.py`

**依赖关系**:
```
TimeWindowTuningService
  ├── DiagnosisResult (读取诊断结果)
  ├── DiagnosisAnnotation (读取标注数据，筛选 annotation='accurate')
  ├── Alarm (读取告警数据，计算持续时间 recovered_at - created_at)
  ├── Device (读取设备类型)
  ├── TimeWindowAdjustmentLog (存储调整记录)
  └── SystemConfig (读取/更新 diagnosis_time_windows 配置)

注意: 持续时间来源于告警表，需要 JOIN diagnosis_results → alarms 获取
```

**执行流程**:
```
1. APScheduler 每月1日 03:00 触发时间窗口分析任务
   - 如果上次任务仍在执行，跳过本次任务（使用 APScheduler coalesce=True, max_instances=1）
2. 查询所有有诊断记录的设备类型（从 devices 表 JOIN diagnosis_results 和 diagnosis_annotations，筛选 annotation='accurate' 且 alarm.recovered_at IS NOT NULL 的记录，DISTINCT device_type）
   - 如果查询结果为空（没有任何设备类型有准确标注的诊断记录），记录日志并正常结束任务
3. 对每个设备类型：
   a. 从 system_configs 获取当前时间窗口（config_value.{device_type}，若不存在则使用 config_value.default）
   b. 查询该设备类型的"准确"标注诊断记录
   c. JOIN alarm 表获取故障持续时间（recovered_at - created_at）
   d. 筛选已恢复且持续时间 > 0 的告警（recovered_at IS NOT NULL AND recovered_at > created_at）
   e. 统计样本数，若 < 30 则跳过
   f. 使用 SQL percentile_cont(0.5) 和 percentile_cont(0.9) 计算 P50 和 P90（单位：秒）
   g. 建议时间窗口 = ROUND(P90 × 1.2 / 60)，四舍五入到整数分钟，限制在 [1, 120] 分钟范围内
      - 如果 P90 × 1.2 < 60 秒，建议时间窗口 = 1 分钟（最小值）
   h. 若建议值与当前值相同，则跳过（不生成调整记录）
   i. 若调整百分比 > 500%，记录警告日志（可能数据异常）
   j. 生成调整建议记录（time_window_adjustment_logs 表）
4. 通知管理员审批（邮件 + WebSocket 推送，失败时记录日志但不阻塞流程）
5. 管理员审批后：
   a. 使用数据库事务确保原子性（更新调整记录状态 + 更新 system_configs + 记录审计日志）
   b. 使用乐观锁防止并发审批冲突（UPDATE ... WHERE id=? AND version=? AND status='pending'）
   c. 更新调整记录状态为 'approved'，记录 approved_by 和 approved_at
   d. 使用 JSONB/JSON 操作更新 system_configs.config_value[device_type] = new_window_minutes
      - PostgreSQL: jsonb_set 函数
      - SQLite: json_set 函数（需要 JSON1 扩展）
   e. 记录审计日志到 audit_logs 表（操作类型、操作人、操作时间、变更前后值）
   f. 配置更新后，新的诊断任务立即使用新配置，正在运行的诊断任务不受影响（使用启动时的配置）
6. 如果定时任务执行失败，下次任务会重新分析所有设备类型（不保留上次失败状态）
```

### 2.2 数据库设计

**新增表**: `time_window_adjustment_logs`

```sql
CREATE TABLE time_window_adjustment_logs (
    id SERIAL PRIMARY KEY,
    device_type VARCHAR(100) NOT NULL,
    current_window_minutes INTEGER NOT NULL,
    proposed_window_minutes INTEGER NOT NULL,
    adjustment_percent FLOAT NOT NULL,  -- 调整百分比 = ((proposed - current) / current) * 100
    sample_count INTEGER NOT NULL,  -- 样本数
    p50_duration_seconds FLOAT NOT NULL,  -- P50 持续时间（秒）
    p90_duration_seconds FLOAT NOT NULL,  -- P90 持续时间（秒）
    status VARCHAR(20) NOT NULL DEFAULT 'pending',  -- 'pending', 'approved', 'rejected'
    reason TEXT,  -- 审批理由或拒绝原因
    approved_by INTEGER REFERENCES users(id) ON DELETE SET NULL,
    approved_at TIMESTAMP,
    version INTEGER NOT NULL DEFAULT 1,  -- 乐观锁版本号，每次更新 +1
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    INDEX idx_adjustment_logs_device_type (device_type),
    INDEX idx_adjustment_logs_status (status),
    INDEX idx_adjustment_logs_created (created_at),
    INDEX idx_adjustment_logs_approved_by (approved_by)
);

-- 注意: SQLite 不支持 ON DELETE SET NULL 语法，需在应用层处理
-- 生产环境使用 PostgreSQL，开发/测试环境使用 SQLite 时需注意兼容性

-- 自动更新 updated_at 和 version 触发器
CREATE OR REPLACE FUNCTION update_time_window_adjustment_logs_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    NEW.version = OLD.version + 1;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_update_time_window_adjustment_logs_updated_at
BEFORE UPDATE ON time_window_adjustment_logs
FOR EACH ROW
EXECUTE FUNCTION update_time_window_adjustment_logs_updated_at();
```

**system_configs 表结构**:

```sql
-- system_configs 表定义（如果不存在则需要在迁移脚本中创建）
-- 注意: 此表可能已在其他 Story 中创建，需要检查是否存在
CREATE TABLE IF NOT EXISTS system_configs (
    id SERIAL PRIMARY KEY,
    config_key VARCHAR(100) UNIQUE NOT NULL,
    config_value JSONB NOT NULL,  -- PostgreSQL 使用 JSONB，SQLite 使用 TEXT
    description TEXT,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    INDEX idx_system_configs_key (config_key)
);

-- SQLite 兼容版本（使用 TEXT 存储 JSON）
-- CREATE TABLE IF NOT EXISTS system_configs (
--     id INTEGER PRIMARY KEY AUTOINCREMENT,
--     config_key VARCHAR(100) UNIQUE NOT NULL,
--     config_value TEXT NOT NULL,  -- JSON 格式的 TEXT
--     description TEXT,
--     created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
--     updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
-- );
-- CREATE INDEX IF NOT EXISTS idx_system_configs_key ON system_configs(config_key);

-- diagnosis_time_windows 配置示例
INSERT INTO system_configs (config_key, config_value, description)
VALUES (
    'diagnosis_time_windows',
    '{"UPS": 5, "空调": 10, "配电柜": 3, "default": 5}'::jsonb,  -- PostgreSQL
    -- '{"UPS": 5, "空调": 10, "配电柜": 3, "default": 5}',  -- SQLite
    '诊断时间窗口配置（分钟），按设备类型区分'
)
ON CONFLICT (config_key) DO NOTHING;
```

**audit_logs 表结构**（用于记录审计日志）:

```sql
-- audit_logs 表定义（如果不存在则需要在迁移脚本中创建）
CREATE TABLE IF NOT EXISTS audit_logs (
    id SERIAL PRIMARY KEY,
    operation_type VARCHAR(50) NOT NULL,  -- 'time_window_adjustment_approved', 'time_window_adjustment_rejected'
    operation_user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
    operation_user_name VARCHAR(100),
    operation_time TIMESTAMP DEFAULT NOW(),
    resource_type VARCHAR(50),  -- 'time_window_adjustment'
    resource_id INTEGER,  -- time_window_adjustment_logs.id
    old_value TEXT,  -- JSON 格式，记录变更前的值
    new_value TEXT,  -- JSON 格式，记录变更后的值
    description TEXT,
    INDEX idx_audit_logs_type (operation_type),
    INDEX idx_audit_logs_user (operation_user_id),
    INDEX idx_audit_logs_time (operation_time)
);
```

**配置 JSON 格式**:
```json
{
  "config_key": "diagnosis_time_windows",
  "config_value": {
    "UPS": 5,
    "空调": 10,
    "配电柜": 3,
    "default": 5
  },
  "description": "诊断时间窗口配置（分钟），按设备类型区分"
}
```

**注意事项**:
- config_value 使用 JSONB 类型（PostgreSQL）或 TEXT 类型（SQLite）
- 必须包含 "default" 键，用于未配置的设备类型
- 设备类型名称作为 JSON key，需要转义特殊字符：
  - 双引号 " → \"
  - 反斜杠 \ → \\
  - 换行符 \n → \\n
  - 制表符 \t → \\t
  - 使用 Python json.dumps() 自动处理转义

### 2.3 API 设计

**时间窗口分析 API**:
```
POST /api/v1/diagnosis/time-window-tuning/analyze
权限: admin
描述: 手动触发时间窗口分析（也可由定时任务自动触发）
请求体: { "device_type": "UPS" }  # 可选，不指定则分析所有设备类型
响应: {
  "analyzed_device_types": 3,
  "total_adjustments": 2,
  "pending_approvals": 2
}
错误响应:
  - 403 Forbidden: { "detail": "权限不足" }
  - 500 Internal Server Error: { "detail": "时间窗口分析失败: {error_message}" }
```

**查询调整记录 API**:
```
GET /api/v1/diagnosis/time-window-tuning/adjustments
权限: admin
描述: 查询时间窗口调整记录列表
查询参数:
  - device_type: 设备类型（可选）
  - status: 状态筛选（pending/approved/rejected，可选）
  - page: 页码（默认1）
  - page_size: 每页数量（默认20）
响应: {
  "items": [
    {
      "id": 1,
      "device_type": "UPS",
      "current_window_minutes": 5,
      "proposed_window_minutes": 6,
      "adjustment_percent": 20.0,
      "sample_count": 45,
      "p50_duration_seconds": 180.5,
      "p90_duration_seconds": 300.2,
      "status": "pending",
      "created_at": "2026-03-08T03:00:00Z"
    }
  ],
  "total": 2,
  "page": 1,
  "page_size": 20
}
```

**审批调整 API**:
```
POST /api/v1/diagnosis/time-window-tuning/adjustments/{id}/approve
权限: admin
描述: 审批时间窗口调整建议
请求体: { "reason": "审批理由（可选）" }
响应: {
  "message": "时间窗口调整已审批，配置已更新",
  "adjustment_id": 1,
  "device_type": "UPS",
  "new_window_minutes": 6
}
错误响应:
  - 403 Forbidden: { "detail": "权限不足" }
  - 404 Not Found: { "detail": "调整记录不存在" }
  - 409 Conflict: { "detail": "调整记录已被其他管理员处理" }
  - 500 Internal Server Error: { "detail": "审批失败: {error_message}" }
```

**拒绝调整 API**:
```
POST /api/v1/diagnosis/time-window-tuning/adjustments/{id}/reject
权限: admin
描述: 拒绝时间窗口调整建议
请求体: { "reason": "拒绝理由" }
响应: {
  "message": "时间窗口调整已拒绝",
  "adjustment_id": 1
}
错误响应:
  - 400 Bad Request: { "detail": "拒绝理由不能为空" }
  - 403 Forbidden: { "detail": "权限不足" }
  - 404 Not Found: { "detail": "调整记录不存在" }
  - 409 Conflict: { "detail": "调整记录已被其他管理员处理" }
  - 500 Internal Server Error: { "detail": "拒绝失败: {error_message}" }
```

### 2.4 核心算法

**时间窗口计算逻辑**:
```python
def calculate_time_window_adjustment(
    device_type: str,
    current_window_minutes: int,
    fault_durations_seconds: list[float]
) -> tuple[int, float, float, float]:
    """
    计算时间窗口调整建议

    Args:
        device_type: 设备类型
        current_window_minutes: 当前时间窗口（分钟）
        fault_durations_seconds: 故障持续时间列表（秒）

    Returns:
        (proposed_window_minutes, adjustment_percent, p50_seconds, p90_seconds)
    """
    # 防止空列表
    if not fault_durations_seconds:
        logger.warning(f"设备类型 {device_type} 无故障持续时间数据，跳过调整")
        return current_window_minutes, 0.0, 0.0, 0.0

    # 过滤负值和零值（数据错误）
    valid_durations = [d for d in fault_durations_seconds if d > 0]
    if not valid_durations:
        logger.warning(f"设备类型 {device_type} 无有效故障持续时间数据（所有值 <= 0），跳过调整")
        return current_window_minutes, 0.0, 0.0, 0.0

    # 计算 P50 和 P90（使用 SQL percentile_cont 结果，不使用 numpy）
    # 注意: 此函数接收的是已经通过 SQL 计算好的持续时间列表
    # 如果需要在 Python 中计算，使用 statistics.quantiles (Python 3.8+)
    import statistics

    # 检查样本数是否足够（quantiles 需要至少 2 个数据点）
    if len(valid_durations) < 2:
        logger.warning(f"设备类型 {device_type} 有效样本数不足（{len(valid_durations)} < 2），跳过调整")
        return current_window_minutes, 0.0, 0.0, 0.0

    p50_seconds = float(statistics.median(valid_durations))

    # quantiles(data, n=10) 返回 9 个分位点: [P10, P20, ..., P90]
    # 索引 8 对应 P90（第 9 个分位点）
    # 注意: 需要至少 10 个数据点才能计算 10 分位数，否则使用 max 值
    if len(valid_durations) >= 10:
        quantiles = statistics.quantiles(valid_durations, n=10)
        p90_seconds = float(quantiles[8])  # 索引 8 是 P90
    else:
        # 样本数不足 10，使用最大值作为 P90 的近似
        p90_seconds = float(max(valid_durations))
        logger.warning(f"设备类型 {device_type} 样本数不足 10（{len(valid_durations)}），使用最大值作为 P90 近似")

    # 建议时间窗口 = P90 × 1.2（留 20% 裕度），四舍五入到整数分钟
    proposed_window_seconds = p90_seconds * 1.2
    proposed_window_minutes = round(proposed_window_seconds / 60)

    # 限制范围：[1, 120] 分钟
    # 如果 P90 × 1.2 < 60 秒，四舍五入后为 0，强制设为 1 分钟
    if proposed_window_minutes < 1:
        proposed_window_minutes = 1
        logger.info(f"设备类型 {device_type} 计算的时间窗口 < 1 分钟，设为最小值 1 分钟")
    elif proposed_window_minutes > 120:
        proposed_window_minutes = 120
        logger.info(f"设备类型 {device_type} 计算的时间窗口 > 120 分钟，截断到最大值 120 分钟")

    # 如果建议值与当前值相同，返回 0% 调整（调用方应跳过生成记录）
    if proposed_window_minutes == current_window_minutes:
        return current_window_minutes, 0.0, p50_seconds, p90_seconds

    # 计算调整百分比
    if current_window_minutes == 0:
        # 如果当前值为 0（配置错误），使用 default 值或跳过
        logger.error(f"设备类型 {device_type} 当前时间窗口为 0，配置错误")
        adjustment_percent = 0.0
    else:
        adjustment_percent = ((proposed_window_minutes - current_window_minutes) / current_window_minutes) * 100

    # 如果调整百分比 > 500%，记录警告（可能数据异常）
    if abs(adjustment_percent) > 500:
        logger.warning(f"设备类型 {device_type} 调整百分比过大（{adjustment_percent:.1f}%），可能数据异常")

    return proposed_window_minutes, adjustment_percent, p50_seconds, p90_seconds
```

**注意事项**:
- 优先使用 SQL percentile_cont 计算 P50/P90（性能更好，结果一致）
- Python 中使用 statistics.quantiles 而非 numpy（避免额外依赖）
- statistics.quantiles(data, n=10) 需要至少 10 个数据点，否则使用 max 值作为 P90 近似
- 四舍五入到整数分钟（round 函数）
- 过滤持续时间 <= 0 的数据（数据错误）
- 如果建议值与当前值相同，不生成调整记录
- 如果调整百分比 > 500%，记录警告日志

**SQL 查询示例**（使用 PostgreSQL percentile_cont）:
```sql
-- 查询某设备类型的故障持续时间统计
SELECT
    d.device_type,
    COUNT(*) as sample_count,
    PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY EXTRACT(EPOCH FROM (a.recovered_at - a.created_at))) as p50_seconds,
    PERCENTILE_CONT(0.9) WITHIN GROUP (ORDER BY EXTRACT(EPOCH FROM (a.recovered_at - a.created_at))) as p90_seconds
FROM diagnosis_results dr
JOIN diagnosis_annotations da ON dr.id = da.result_id
JOIN alarms a ON dr.alarm_id = a.id
JOIN devices d ON a.device_id = d.id
WHERE da.annotation = 'accurate'
  AND a.recovered_at IS NOT NULL
  AND a.recovered_at > a.created_at  -- 过滤持续时间 <= 0 的数据
  AND d.device_type = 'UPS'
GROUP BY d.device_type
HAVING COUNT(*) >= 30;
```

**获取当前时间窗口配置**:
```sql
-- 从 system_configs 获取设备类型的时间窗口配置
SELECT
    COALESCE(
        (config_value->>:device_type)::integer,
        (config_value->>'default')::integer,
        5  -- 硬编码默认值（如果 default 也不存在）
    ) as current_window_minutes
FROM system_configs
WHERE config_key = 'diagnosis_time_windows';
```

**更新时间窗口配置**（使用 JSONB/JSON 操作）:
```sql
-- PostgreSQL: 使用 jsonb_set 函数
UPDATE system_configs
SET config_value = jsonb_set(
    config_value,
    ARRAY[:device_type],
    to_jsonb(:new_window_minutes)
),
updated_at = NOW()
WHERE config_key = 'diagnosis_time_windows';

-- SQLite: 使用 json_set 函数（需要 JSON1 扩展）
UPDATE system_configs
SET config_value = json_set(
    config_value,
    '$.' || :device_type,
    :new_window_minutes
),
updated_at = CURRENT_TIMESTAMP
WHERE config_key = 'diagnosis_time_windows';
```

**注意事项**:
- 设备类型名称需要参数化（:device_type），防止 SQL 注入
- 使用 COALESCE 提供多级默认值（设备类型 → default → 硬编码）
- PostgreSQL 使用 jsonb_set，SQLite 使用 json_set
- SQLite 需要启用 JSON1 扩展（编译时选项）
- EXTRACT(EPOCH FROM ...) 将时间间隔转换为秒数
- 设备类型名称使用 json.dumps() 自动转义特殊字符

### 2.5 定时任务配置

```python
# backend/app/main.py

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from app.services.diagnosis.time_window_tuning_service import TimeWindowTuningService

scheduler = AsyncIOScheduler()

@scheduler.scheduled_job('cron', day=1, hour=3, minute=0, misfire_grace_time=300, coalesce=True, max_instances=1)
async def monthly_time_window_tuning():
    """每月1日凌晨3点执行时间窗口分析

    misfire_grace_time=300: 如果任务错过执行时间（如服务重启），
    在 300 秒内仍会执行，超过则跳过本次任务

    coalesce=True: 如果有多个任务堆积，合并为一个任务执行

    max_instances=1: 同时只允许一个实例运行，防止并发执行
    """
    logger.info("开始执行每月时间窗口分析")

    tuning_service = TimeWindowTuningService()

    try:
        result = await tuning_service.analyze_all_device_types()
        logger.info(f"时间窗口分析完成: {result}")

        # 如果有待审批的调整建议，发送通知
        if result['pending_approvals'] > 0:
            try:
                await tuning_service.notify_admins(result)
            except Exception as notify_error:
                logger.error(f"通知管理员失败: {notify_error}", exc_info=True)
                # 通知失败不阻塞流程，调整记录已保存
    except Exception as e:
        logger.error(f"时间窗口分析失败: {e}", exc_info=True)
```

---

## 3. 实现任务

### Task 1: 数据库迁移
- [ ] 检查 system_configs 表是否已存在（查询 information_schema.tables）
  - 如果不存在，在迁移脚本中创建（包含 PostgreSQL 和 SQLite 兼容版本）
- [ ] 检查 audit_logs 表是否已存在
  - 如果不存在，在迁移脚本中创建
- [ ] 创建 `time_window_adjustment_logs` 表（包含 version 字段用于乐观锁）
- [ ] 添加索引和触发器（自动更新 updated_at 和 version）
- [ ] 创建回滚脚本（`alembic downgrade -1`）
  - 回滚内容: DROP TABLE time_window_adjustment_logs, DROP TRIGGER, DROP FUNCTION
  - 不删除 system_configs 和 audit_logs 表（可能被其他功能使用）

### Task 2: 后端服务实现
- [ ] 实现 `TimeWindowTuningService` 核心逻辑
- [ ] 实现时间窗口计算算法（使用 statistics.quantiles，处理样本数 < 10 的情况）
- [ ] 实现 SQL 查询（使用 percentile_cont，过滤持续时间 <= 0 的数据）
- [ ] 实现从 system_configs 获取当前时间窗口配置（使用 COALESCE 多级默认值）
- [ ] 实现调整记录生成和存储（跳过建议值与当前值相同的情况）
- [ ] 实现审批流程（approve/reject），包含审计日志记录
- [ ] 实现 system_configs 更新逻辑（PostgreSQL 使用 jsonb_set，SQLite 使用 json_set）
- [ ] 实现设备类型名称转义（使用 json.dumps() 自动处理）
- [ ] 实现空设备类型列表的处理（记录日志并正常结束）
- [ ] 实现调整百分比 > 500% 的警告日志

### Task 3: 后端 API 实现
- [ ] 实现 POST `/diagnosis/time-window-tuning/analyze` 手动触发分析
- [ ] 实现 GET `/diagnosis/time-window-tuning/adjustments` 查询调整记录
- [ ] 实现 POST `/diagnosis/time-window-tuning/adjustments/{id}/approve` 审批
- [ ] 实现 POST `/diagnosis/time-window-tuning/adjustments/{id}/reject` 拒绝
- [ ] 添加权限控制装饰器（仅管理员）
- [ ] 添加错误处理和 HTTP 状态码（403, 404, 409, 500）

### Task 4: APScheduler 定时任务
- [ ] 配置每月定时任务（每月1日凌晨3点，coalesce=True, max_instances=1）
- [ ] 实现时间窗口分析任务逻辑
- [ ] 实现管理员通知逻辑（邮件 + WebSocket）
  - 邮件主题: "智能诊断系统 - 时间窗口调整审批通知"
  - 邮件正文: 包含待审批调整数量、设备类型、当前窗口、建议窗口、统计依据
  - WebSocket 消息: { "type": "time_window_tuning_approval", "pending_count": 2 }
  - 通知对象: 所有 role='admin' 的用户
- [ ] 添加任务失败重试机制（APScheduler misfire_grace_time=300 秒）
- [ ] 添加任务并发控制（防止上次任务未完成时启动新任务）

### Task 5: 后端测试
- [ ] 单元测试：时间窗口计算算法
- [ ] 单元测试：P50/P90 统计计算（使用 statistics.quantiles）
- [ ] 单元测试：调整记录生成
- [ ] 单元测试：持续时间 <= 0 的数据过滤
- [ ] 单元测试：设备类型名称转义
- [ ] 集成测试：完整调整流程（分析→审批→配置更新）
- [ ] 集成测试：审批拒绝流程
- [ ] 集成测试：并发审批场景（两个管理员同时审批同一调整记录，验证乐观锁）
- [ ] 集成测试：一个管理员审批、另一个管理员拒绝同一记录（验证乐观锁）
- [ ] 边界测试：样本数不足场景
- [ ] 边界测试：时间窗口范围限制（四舍五入）
- [ ] 边界测试：当前时间窗口为 0 的场景
- [ ] 边界测试：建议值与当前值相同的场景（不生成记录）

### Task 6: 前端页面
- [ ] 创建时间窗口管理页面（`frontend/src/views/diagnosis/TimeWindowTuning.vue`）
  - 如果 ProbabilityTuning.vue 不存在，参考 Reports.vue 或其他诊断页面的布局模式
  - 路由路径: `/diagnosis/time-window-tuning`
  - 权限要求: admin only（在路由 meta 中配置 `requiresRole: ['admin']`）
- [ ] 实现调整记录列表展示
  - 表格列: 设备类型、当前窗口、建议窗口、调整百分比、样本数、P50、P90、状态、创建时间
  - 筛选条件: 设备类型、状态（pending/approved/rejected）
- [ ] 实现调整详情查看（对比调整前后窗口、统计数据）
  - 使用 el-dialog 弹窗展示详情
- [ ] 实现审批/拒绝操作
  - 审批按钮: 二次确认对话框（el-message-box.confirm）
  - 拒绝按钮: 输入拒绝理由（el-message-box.prompt）
- [ ] 实现手动触发分析按钮
- [ ] 添加路由配置到 `frontend/src/router/index.ts`
  - 添加菜单项到侧边栏（在"智能诊断"分组下）
- [ ] 实现列表自动刷新（可选，使用 WebSocket 或定时轮询）
  - 当收到 WebSocket 消息时自动刷新列表
  - 或每 30 秒轮询一次（如果 WebSocket 不可用）

### Task 7: 文档更新
- [ ] API 文档更新
- [ ] 用户手册更新（时间窗口调整审批流程说明）
- [ ] 运维手册更新（定时任务配置说明）

---

## 4. 测试用例

### 测试用例 1: 时间窗口计算 - 正常场景

**前置条件**:
- 设备类型 "UPS" 当前时间窗口 = 5 分钟
- 标注数据: 45 条"准确"标注，故障持续时间分布: P50=180秒, P90=300秒

**执行步骤**:
1. 触发时间窗口分析: `POST /api/v1/diagnosis/time-window-tuning/analyze`

**预期结果**:
- P50 = 180 秒 = 3 分钟
- P90 = 300 秒 = 5 分钟
- 建议时间窗口 = 300 × 1.2 = 360 秒 = 6 分钟
- 调整百分比 = (6 - 5) / 5 × 100 = 20.0%
- 生成调整记录，status='pending'

---

### 测试用例 2: 时间窗口计算 - 边界截断

**前置条件**:
- 设备类型 "空调" 当前时间窗口 = 10 分钟
- 标注数据: 50 条"准确"标注，故障持续时间分布: P50=3600秒, P90=7200秒

**执行步骤**:
1. 触发时间窗口分析

**预期结果**:
- P90 = 7200 秒 = 120 分钟
- 建议时间窗口 = 7200 × 1.2 = 8640 秒 = 144 分钟
- 截断到最大值 = 120 分钟
- 调整百分比 = (120 - 10) / 10 × 100 = 1100.0%
- 生成调整记录

---

### 测试用例 3: 审批流程 - 更新配置

**前置条件**:
- 调整记录 ID=1，status='pending'，device_type='UPS'，proposed_window_minutes=6
- system_configs 中 diagnosis_time_windows.UPS = 5

**执行步骤**:
1. 审批调整: `POST /api/v1/diagnosis/time-window-tuning/adjustments/1/approve`
2. 查询配置: `GET /api/v1/system-configs?config_key=diagnosis_time_windows`

**预期结果**:
- 调整记录 status 更新为 'approved'
- system_configs 中 diagnosis_time_windows.UPS 更新为 6
- 审计日志记录审批操作

---

### 测试用例 4: 样本数不足场景

**前置条件**:
- 设备类型 "配电柜" 标注数据仅 20 条

**执行步骤**:
1. 触发时间窗口分析

**预期结果**:
- 该设备类型不生成调整建议（样本数 < 30）
- 分析日志记录: "设备类型 配电柜 样本数不足（20 < 30），跳过调整"

---

### 测试用例 5: 并发审批场景

**前置条件**:
- 调整记录 ID=1，status='pending'，version=1

**执行步骤**:
1. 管理员A 审批: `POST /api/v1/diagnosis/time-window-tuning/adjustments/1/approve`
2. 管理员B 同时审批: `POST /api/v1/diagnosis/time-window-tuning/adjustments/1/approve`

**预期结果**:
- 第一个请求成功，status='approved'，version=2
- 第二个请求失败，返回 409 Conflict 错误: "调整记录已被其他管理员审批"

---

### 测试用例 6: 并发审批场景 - 审批与拒绝冲突

**前置条件**:
- 调整记录 ID=1，status='pending'，version=1

**执行步骤**:
1. 管理员A 审批: `POST /api/v1/diagnosis/time-window-tuning/adjustments/1/approve`
2. 管理员B 同时拒绝: `POST /api/v1/diagnosis/time-window-tuning/adjustments/1/reject`

**预期结果**:
- 第一个请求成功（假设是审批），status='approved'，version=2
- 第二个请求失败，返回 409 Conflict 错误: "调整记录已被其他管理员处理"

---

### 测试用例 7: 建议值与当前值相同

**前置条件**:
- 设备类型 "UPS" 当前时间窗口 = 6 分钟
- 标注数据: 40 条"准确"标注，故障持续时间分布: P50=180秒, P90=300秒

**执行步骤**:
1. 触发时间窗口分析

**预期结果**:
- P90 = 300 秒 = 5 分钟
- 建议时间窗口 = 300 × 1.2 = 360 秒 = 6 分钟（四舍五入）
- 建议值 = 当前值 = 6 分钟
- 不生成调整记录（跳过）
- 分析日志记录: "设备类型 UPS 建议时间窗口与当前值相同（6 分钟），跳过调整"

---

### 测试用例 8: 持续时间数据异常

**前置条件**:
- 设备类型 "配电柜" 标注数据 35 条，其中 5 条 recovered_at < created_at（数据错误）

**执行步骤**:
1. 触发时间窗口分析

**预期结果**:
- SQL 查询过滤掉 5 条异常数据（WHERE recovered_at > created_at）
- 有效样本数 = 30 条（满足最小样本量）
- 基于 30 条有效数据计算 P50/P90
- 生成调整记录

---

## 5. 开发者上下文

### 5.1 架构约束

**来源**: docs/intelligent-diagnosis-upgrade-plan.md

- 时间窗口必须基于 ≥30 条标注数据（统计学最小样本量）
- 调整范围限制：最小 1 分钟，最大 120 分钟
- 使用 P90 × 1.2 作为建议值（留 20% 裕度）
- 审批流程必须记录审计日志（满足 ISO 27001/SOC 2）
- 审批操作使用数据库事务 + 乐观锁（version 字段）防止并发冲突

### 5.2 技术栈约束

**来源**: project-context.md

- Python 3.11+, FastAPI 0.109.0
- SQLAlchemy 2.0.25 异步模式
- APScheduler 3.10.4 定时任务
- PostgreSQL + asyncpg 异步驱动
- Pydantic 2.5.3 数据验证
- 不依赖 numpy（使用 Python 标准库 statistics 模块）

### 5.3 代码规范

**来源**: project-context.md

- 使用 `async/await` 异步模式
- 数据库操作使用 `async with async_session() as session`
- 配置通过 `get_settings()` 单例获取
- 日志使用 `logger.info/warning/error`
- 异常处理使用 `try/except` 并记录日志

### 5.4 前置 Story 学习

**来源**: Story 26-3 实现经验

- APScheduler 定时任务配置模式：
  ```python
  @scheduler.scheduled_job('cron', day=1, hour=3, minute=0)
  async def monthly_task():
      pass
  ```

- 邮件通知模式：
  ```python
  from app.services.email_service import email_service
  if email_service.is_available:
      await email_service.send_html_email(...)
  ```

- 审计日志记录模式：
  ```python
  logger.info(f"操作: {action}, 用户: {user_id}, 时间: {datetime.now()}")
  ```

- 权限控制装饰器：
  ```python
  # backend/app/core/security.py
  from functools import wraps
  from fastapi import HTTPException

  def require_role(*allowed_roles):
      """权限控制装饰器，限制只有特定角色可访问"""
      def decorator(func):
          @wraps(func)
          async def wrapper(*args, current_user: User, **kwargs):
              if current_user.role not in allowed_roles:
                  raise HTTPException(status_code=403, detail="权限不足")
              return await func(*args, current_user=current_user, **kwargs)
          return wrapper
      return decorator

  # 使用示例
  @router.post("/adjustments/{id}/approve")
  @require_role('admin')
  async def approve_adjustment(
      id: int,
      current_user: User = Depends(get_current_active_user)
  ):
      pass
  ```

### 5.5 数据库查询优化

**来源**: Story 26-3 实现经验

- 使用 JOIN 减少查询次数
- 使用 GROUP BY 聚合统计
- 添加索引加速查询（device_type, status, created_at）
- 大数据量查询使用分页
- PostgreSQL percentile_cont 函数用于百分位数计算

### 5.6 测试模式

**来源**: Story 26-3 测试经验

- 单元测试使用 pytest + pytest-asyncio
- 集成测试使用 TestClient
- 测试数据库使用 SQLite 内存模式
- 测试覆盖率目标 ≥ 80%

---

## 6. 文件清单

**后端文件**:
- `backend/alembic/versions/20260308_0200_create_time_window_adjustment_logs.py` - 数据库迁移脚本
- `backend/app/models/diagnosis.py` - 添加 TimeWindowAdjustmentLog 模型
- `backend/app/models/__init__.py` - 导出新模型
- `backend/app/schemas/time_window_tuning.py` - 时间窗口调整 Schema
- `backend/app/services/diagnosis/time_window_tuning_service.py` - 核心服务
- `backend/app/api/v1/diagnosis.py` - 添加时间窗口调整 API 端点
- `backend/app/main.py` - 添加 APScheduler 定时任务
- `backend/tests/services/diagnosis/test_time_window_tuning_service.py` - 服务测试
- `backend/tests/api/test_time_window_tuning.py` - API 集成测试

**前端文件**:
- `frontend/src/views/diagnosis/TimeWindowTuning.vue` - 时间窗口管理页面
- `frontend/src/api/modules/diagnosis.ts` - 添加时间窗口调整 API 接口定义
- `frontend/src/router/index.ts` - 添加路由配置

---

## Dev Agent Record

### Agent Model Used

Claude Opus 4.6 (claude-opus-4-6)

### Tasks/Subtasks

**待完成**:
- Task 1: 数据库迁移
- Task 2: 后端服务实现
- Task 3: 后端 API 实现
- Task 4: APScheduler 定时任务配置
- Task 5: 后端测试
- Task 6: 前端页面
- Task 7: 文档更新

### File List

（待实现后填写）

### Change Log

（待实现后填写）

### Implementation Notes

**技术决策**:
1. 使用乐观锁（version 字段）防止并发审批冲突
2. 时间窗口范围限制在 [1, 120] 分钟
3. 使用 P90 × 1.2 作为建议值（留 20% 裕度），四舍五入到整数分钟
4. 数据库迁移脚本兼容 SQLite 和 PostgreSQL
5. API 使用 require_admin 装饰器限制权限
6. 使用 statistics.quantiles 而非 numpy（避免额外依赖）
7. 使用 JSONB 操作（jsonb_set）更新配置，避免整体替换
8. 过滤持续时间 <= 0 的数据（数据错误）
9. 建议值与当前值相同时不生成调整记录
10. 配置更新后，新诊断任务立即使用新配置，正在运行的任务不受影响

**待解决问题**:
1. 需要确认 diagnosis_results 表是否有 alarm_id 字段（如果字段名不同需要调整 SQL）
2. 需要确认 system_configs 表是否已存在（如果不存在需要在迁移脚本中创建）
3. 需要确认 audit_logs 表是否已存在（如果不存在需要在迁移脚本中创建）
4. 邮件和 WebSocket 通知服务需要集成
5. 前端页面和路由配置待实现
6. 需要确认设备类型名称中是否包含特殊字符（如引号、反斜杠），使用 json.dumps() 自动转义
7. 需要确认 SQLite 是否启用 JSON1 扩展（json_set 函数依赖）
8. 需要确认是否需要设备类型重命名的迁移工具（如果设备类型名称在 devices 表中被修改）

**测试策略**:
- 单元测试：时间窗口计算算法、P50/P90 统计
- 集成测试：完整审批流程、并发审批
- 边界测试：样本数不足、时间窗口范围限制

---

**Story 创建日期**: 2026-03-08
**Story 创建者**: Bob (Scrum Master)
**Story 状态**: ready-for-dev
**最后更新**: 2026-03-08
