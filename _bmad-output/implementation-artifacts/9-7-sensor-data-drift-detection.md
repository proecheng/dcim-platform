# Story 9.7: 传感器数据漂移检测

Status: ready-for-dev

## Story

As a 运维工程师,
I want 系统自动检测传感器数据漂移,
So that 我可以及时发现传感器老化或故障，避免基于错误数据做出误判。

## FR 追溯

- FR35: 检测传感器数据漂移（3σ 统计偏差、相邻传感器交叉验证）

## Acceptance Criteria

1. Given 系统已积累至少 48 小时的点位历史数据
   When 数据质量检测模块运行
   Then 对每个 AI 点位计算 3σ 统计偏差，偏差超过阈值标记为"疑似漂移"

2. Given 某点位被标记为"疑似漂移"
   When 对同区域（area_code）相邻传感器执行交叉验证
   Then 偏差持续扩大时确认漂移

3. Given 漂移点位已被标记
   Then 在数据质量 API 中返回漂移信息，前端用黄色标记提示"数据可信度：低"

4. Given 漂移点位已被标记
   Then 系统生成诊断建议（如"建议现场校验或更换"）

5. Given 传感器更换后（点位值恢复正常范围）
   When 下次检测运行
   Then 系统自动解除漂移标记

## 现有代码分析

### 已有实现（直接复用）

| 组件 | 文件 | 说明 |
|------|------|------|
| 点位模型 | models/point.py | Point(area_code, point_type, device_type), PointRealtime(quality: 0/1/2) |
| 历史数据模型 | models/history.py | PointHistory(point_id, value, recorded_at) — 有 idx_history_point_time 索引 |
| 数据质量 API | api/v1/data_quality.py | GET /data-quality/status, GET /data-quality/points — 已有质量查询 |
| 数据质量 Schema | schemas/data_quality.py | DataQualityPointInfo, DataQualityStatus |
| 诊断规则 | config/diagnosis_rules.yaml | 已有"传感器漂移"规则定义 |
| 依赖注入 | api/deps.py | require_operator, require_admin, require_viewer |

### 需要新增

| 组件 | 文件 | 说明 |
|------|------|------|
| 漂移检测模型 | models/drift.py | DriftDetectionResult 表（漂移检测结果记录） |
| 漂移检测 Schema | schemas/drift.py | 漂移检测结果、诊断建议的请求/响应 Schema |
| 漂移检测服务 | services/drift_detection.py | 3σ 计算、交叉验证、漂移标记/解除 |
| 漂移检测 API | api/v1/drift.py | 漂移检测触发、结果查询、手动解除 |
| 前端漂移 API | api/modules/drift.ts | 漂移检测 API 函数 |
| 前端漂移页面 | views/linkage/drift.vue | 漂移检测结果页面 |
| 路由配置 | router/index.ts | 添加 drift 子路由 |
| 后端测试 | tests/test_drift.py | 漂移检测 API 测试 |

## Technical Implementation Notes

### 1. 数据模型设计

DriftDetectionResult（漂移检测结果表）字段：
- id: int — 主键
- point_id: int (FK points.id) — 点位ID
- point_code: str — 点位编码（冗余，方便查询）
- point_name: str — 点位名称（冗余）
- area_code: str — 区域代码
- status: str — suspected / confirmed / resolved
- mean_value: float — 检测期间均值
- std_value: float — 检测期间标准差
- current_value: float — 当前值
- deviation_sigma: float — 偏差倍数（当前值偏离均值的 σ 倍数）
- cross_validation_result: str (nullable) — 交叉验证结果: pass / fail
- diagnosis: str — 诊断建议
- detected_at: datetime — 检测时间
- resolved_at: datetime (nullable) — 解除时间
- created_at: datetime — 记录创建时间

### 2. 漂移检测算法

drift_detection.py 中的 run_drift_detection(db):

Step 1: 筛选 AI 类型点位（point_type in ['AI', 'measurement']），且 is_enabled=True
Step 2: 对每个点位查询最近 48 小时的 PointHistory 数据
Step 3: 计算均值(mean)和标准差(std)
Step 4: 获取当前值（PointRealtime.value）
Step 5: 计算偏差 deviation_sigma = abs(current - mean) / std
Step 6: 如果 deviation_sigma > 3.0 → 标记为 suspected
Step 7: 交叉验证 — 查询同 area_code 同 device_type 的其他点位，计算它们的均值，如果目标点位偏离区域均值也超过 3σ → 标记为 confirmed
Step 8: 对已有 suspected/confirmed 记录但当前值恢复正常（deviation_sigma <= 2.0）→ 标记为 resolved
Step 9: 更新 PointRealtime.quality（suspected→1, confirmed→2, resolved→0）

### 3. API 端点设计

漂移检测：
- POST /drift/detect — 触发漂移检测（operator 权限）
- GET /drift/results — 漂移检测结果列表（分页+筛选）
- GET /drift/results/{id} — 漂移检测结果详情
- POST /drift/results/{id}/resolve — 手动解除漂移标记（operator 权限）
- GET /drift/summary — 漂移检测概览（总数、各状态数量）

### 4. 诊断建议生成

根据 deviation_sigma 和 cross_validation_result 生成建议：
- suspected + cross_validation=pass: "该点位读数偏离历史均值 {n}σ，但同区域传感器正常。建议观察 24 小时。"
- confirmed + cross_validation=fail: "该点位读数持续偏离，同区域交叉验证失败。建议现场校验或更换传感器。"
- deviation_sigma > 5.0: "该点位读数严重偏离（{n}σ），数据可信度极低。建议立即现场检查。"

### 5. 前端页面设计

views/linkage/drift.vue:
- 顶部：漂移概览卡片（总检测点位数、疑似漂移、确认漂移、已解除）
- 中部：漂移结果表格（点位编码、名称、区域、状态、偏差σ、交叉验证、诊断建议、检测时间）
- 状态标签颜色：suspected=warning, confirmed=danger, resolved=success
- 操作按钮：手动解除（仅 suspected/confirmed 状态）
- 触发检测按钮（调用 POST /drift/detect）

### 6. 最小数据要求

如果点位历史数据不足 48 小时（样本数 < 100），跳过该点位检测。
如果同区域同类型点位不足 2 个，跳过交叉验证步骤（仅做单点 3σ 检测）。

## Adversarial Review Findings

| ID | 级别 | 问题 | 解决方案 |
|----|------|------|----------|
| M1 | Medium | 标准差为 0 时（所有历史值相同），deviation_sigma 计算会除以零 | 当 std == 0 时，如果 current == mean 则 deviation=0（正常），否则 deviation=inf（标记为漂移） |
| M2 | Medium | 漂移检测路由放在 /drift 前缀下，但功能上属于联动/数据质量模块 | 可接受 — /drift 是独立功能模块，与 /data-quality 互补 |
| L1 | Low | resolved_at 更新后，如果传感器再次漂移，需要创建新记录而非复用旧记录 | 每次检测对已 resolved 的点位创建新记录，不复用 |

## Dev Notes

- 漂移检测是按需触发（POST /drift/detect），不是后台定时任务
- PointRealtime.quality 字段已有：0=好, 1=不确定, 2=坏 — 漂移 suspected 设为 1, confirmed 设为 2
- 使用 Python 标准库 statistics 模块计算 mean/stdev，不需要 numpy
- 交叉验证只对同 area_code + 同 device_type 的点位进行
- 解除漂移时同时更新 PointRealtime.quality 回 0
- 前端自动导入：ref, computed, onMounted 等无需 import
- Element Plus 组件自动导入

## Tasks

- [ ] Task 1: 创建漂移检测模型 (models/drift.py — DriftDetectionResult)
- [ ] Task 2: 创建漂移检测 Schema (schemas/drift.py)
- [ ] Task 3: 创建漂移检测服务 (services/drift_detection.py — 3σ 计算、交叉验证、标记/解除)
- [ ] Task 4: 创建漂移检测 API (api/v1/drift.py)
- [ ] Task 5: 注册路由 (api/v1/__init__.py)
- [ ] Task 6: 前端漂移 API (api/modules/drift.ts)
- [ ] Task 7: 前端漂移检测页面 (views/linkage/drift.vue)
- [ ] Task 8: 前端路由配置 (router/index.ts)
- [ ] Task 9: 后端测试 (tests/test_drift.py)
