# Story 29.5: 模型精度验证与记录

Status: done

## Story

As a 系统运维人员,
I want 系统自动对比预测温度与实际温度并记录精度指标,
So that 我能评估模型可靠性并在精度退化时收到预警。

## 依赖

- Story 29.2（RC 模型）— done
- Story 29.4（预测 API）— done

## Acceptance Criteria

1. Given 温度预测摘要已记录到 `temperature_prediction_logs` 表
   When 预测时间窗口到期后实际温度数据可用
   Then 系统通过 APScheduler 定时任务（每 5 分钟执行一次）自动回填:
   - 查询 `temperature_prediction_logs` 表中 `actual_temp IS NULL` 的记录
   - 对每条记录，根据 `created_at + prediction_horizon_min` 计算预测目标时间
   - 如果当前时间已超过预测目标时间（即预测时间窗口已到期），查询该时刻的实际温度
   - 实际温度获取: 查询 `created_at + prediction_horizon_min` 时间点前后 2.5 分钟内的最大进风温度（复用 CoolingZoneCabinet(zone_id) → Cabinet → CabinetTemperatureSensor(inlet, point_id) → Point → PointHistory(recorded_at) 链路）
   - 如果实际温度可用，回填 `actual_temp` 和 `deviation = actual_temp - predicted_temp`
   - 如果预测目标时间已过去超过 1 小时仍无实际温度数据，标记 `actual_temp = -999.0`（哨兵值，表示数据不可用），`deviation = NULL`
   - 每次定时任务最多处理 100 条待回填记录，避免单次执行时间过长

2. And **精度验证标准**（与架构一致）:
   - MAE ≤ 1.0°C（1h 内预测）— 优秀
   - MAE ≤ 2.0°C（3h 内预测）— 合格
   - 最大偏差 ≤ 3.0°C — 安全
   - 这些阈值作为常量定义在 `accuracy_monitor.py` 中

3. And **连续误差自动回退**:
   - 每次回填后检查: 该 zone 最近连续 3 条有效预测记录（`actual_temp > 0 AND deviation IS NOT NULL`）的 `abs(deviation)` 是否全部 > 2.0°C
   - 如果连续 3 次误差 > 2°C，执行自动回退:
     - 将该 zone 的 `thermal_parameters` 表中 `is_active=True` 的记录设为 `is_active=False`
     - **注意**: `thermal_parameters` 表存在 `UniqueConstraint("cooling_zone_id", "is_active")`，因此回退时需要先删除该 zone 已有的 `is_active=False` 记录（如有），再将 active 记录设为 `is_active=False`，以避免违反唯一约束
     - 记录警告日志: `"Zone {zone_id} 连续 3 次预测误差 > 2°C，已自动回退到 THM 模式"`
     - 下次调用 `calculate_shiftable_power_for_zone` 时因无 active 参数将自动使用 THM 方法
   - 回退操作是幂等的: 如果已经没有 active 参数，不重复操作

4. And **每日精度统计**:
   - 通过 APScheduler 定时任务（每日凌晨 1:00）自动计算过去 24 小时的预测 MAE
   - 对每个有预测记录的 zone 分别计算 mae_1h 和 mae_3h
   - 仅使用有效记录（`actual_temp > 0 AND deviation IS NOT NULL`），排除哨兵值 -999.0
   - 如果 mae_1h > 1.5°C 或 mae_3h > 3.0°C，记录错误日志: `"Zone {zone_id} 精度退化: mae_1h={mae_1h}°C, mae_3h={mae_3h}°C，建议重新校准"`
   - 精度统计结果通过 Story 29.4 已实现的 `GET /api/v1/precool/zones/{zone_id}/validation` 端点查询（无需新增 API）

5. And **定时任务注册**:
   - 在 `app/main.py` 的 `lifespan` 事件中注册两个定时任务:
     - `accuracy_backfill`: 每 5 分钟执行，回填实际温度
     - `accuracy_daily_report`: 每日凌晨 1:00 执行，每日精度统计
   - 注册到现有的 `scheduler` (APScheduler AsyncIOScheduler) 实例（在 `try: from apscheduler...` 块内，`scheduler.start()` 之前添加）
   - 如果 APScheduler 不可用（ImportError 降级分支），使用 `asyncio.create_task` 降级方案
   - 定时任务失败时记录错误日志但不影响其他任务

6. And **修复 validation 端点哨兵值兼容**:
   - 修改 Story 29.4 已实现的 `GET /api/v1/precool/zones/{zone_id}/validation` 端点
   - 在查询条件中增加 `actual_temp > 0`（排除哨兵值 -999.0），并增加 `deviation IS NOT NULL` 过滤
   - 使用存储的 `deviation` 字段计算 `abs(deviation)` 而非重新计算 `abs(actual_temp - predicted_temp)`
   - 这样确保哨兵值记录不会产生虚假的巨大偏差

## 涉及文件

- 新建 `backend/app/services/precool/accuracy_monitor.py` — 精度监控服务
- 修改 `backend/app/main.py` — 注册定时任务
- 修改 `backend/app/api/v1/precool.py` — 修复 validation 端点哨兵值兼容
- 新建 `backend/tests/services/test_accuracy_monitor.py` — 测试

## 技术说明

- 定时任务使用 APScheduler（项目已有依赖 `apscheduler==3.10.4`），注册到 `main.py` 中已存在的 `scheduler` 实例
- 回填逻辑需要自己创建 `async_session()` 数据库会话（与现有定时任务模式一致）
- 自动回退通过修改 `thermal_parameters.is_active` 实现，需注意 UniqueConstraint 限制
- `temperature_prediction_logs` 表已有 `actual_temp`, `deviation` 字段（Story 29.1 创建）
- 哨兵值 `-999.0` 用于区分 "未回填" (`NULL`) 和 "数据不可用" (`-999.0`)
- 回填查询温度链路: `CoolingZoneCabinet.zone_id` → `Cabinet.id` → `CabinetTemperatureSensor(inlet).point_id` → `Point.id` → `PointHistory(recorded_at, value)`
- `PointHistory` 时间字段为 `recorded_at`（不是 `timestamp`）

## Tasks

- [x] 1. 创建精度监控服务 (`backend/app/services/precool/accuracy_monitor.py`)
- [x] 2. 修复 validation 端点哨兵值兼容 (`backend/app/api/v1/precool.py`)
- [x] 3. 在 `app/main.py` 注册定时任务
- [x] 4. 编写测试 (`backend/tests/services/precool/test_accuracy_monitor.py`)
- [x] 5. 运行测试验证 — 20/20 通过
