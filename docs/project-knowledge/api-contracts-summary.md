# 后端 API 接口文档

生成时间: 2026-03-17
项目版本: V4.2.0

## 概览

- 总端点数: 817
- 模块数: 57
- 认证方式: JWT Bearer Token (OAuth2)
- 基础路径: /api/v1
- 角色: admin / operator / viewer

## 认证说明

| 标记 | 含义 |
|------|------|
| viewer | 需要 viewer 及以上角色 |
| operator | 需要 operator 及以上角色 |
| admin | 需要 admin 角色 |
| 公开 | 无需认证 |
| 登录 | 需要登录（任意角色） |

---

## 1. 认证 (auth)

前缀: `/api/v1/auth`

| 方法 | 路径 | 认证 | 描述 |
|------|------|------|------|
| POST | /login | 公开 | 用户登录获取令牌 |
| POST | /logout | 登录 | 用户登出 |
| POST | /refresh | 登录 | 刷新访问令牌 |
| GET | /me | 登录 | 获取当前用户信息 |
| PUT | /password | 登录 | 修改密码 |
| GET | /permissions | 登录 | 获取当前用户权限 |
| GET | /password-policy | 登录 | 获取密码策略 |
| PUT | /password-policy | admin | 更新密码策略 |

## 2. 用户管理 (users)

前缀: `/api/v1/users`

| 方法 | 路径 | 认证 | 描述 |
|------|------|------|------|
| GET | / | admin | 获取用户列表 |
| POST | / | admin | 创建用户 |
| GET | /sites/{site_id}/users | admin | 获取站点下的用户列表 |
| GET | /{user_id} | admin | 获取用户详情 |
| PUT | /{user_id} | admin | 更新用户 |
| DELETE | /{user_id} | admin | 删除用户 |
| POST | /batch-delete | admin | 批量删除用户 |
| PUT | /{user_id}/status | admin | 启用/禁用用户 |
| PUT | /{user_id}/reset-password | admin | 重置密码 |
| GET | /{user_id}/login-history | admin | 获取登录历史 |
| GET | /{user_id}/sites | admin | 获取用户站点列表 |
| PUT | /{user_id}/sites | admin | 设置用户站点权限 |

## 3. 设备管理 (devices)

前缀: `/api/v1/devices`

| 方法 | 路径 | 认证 | 描述 |
|------|------|------|------|
| GET | / | viewer | 获取设备列表 |
| GET | /tree | viewer | 获取设备树结构 |
| GET | /status-summary | viewer | 获取设备状态汇总 |
| GET | /status-board | viewer | 获取设备状态看板 |
| GET | /{device_id} | viewer | 获取设备详情 |
| GET | /{device_id}/points | viewer | 获取设备下的点位 |
| GET | /{device_id}/detail | viewer | 获取设备详情（聚合） |
| POST | / | operator | 创建设备 |
| PUT | /{device_id} | operator | 更新设备 |
| GET | /{device_id}/delete-impact | viewer | 删除影响分析 |
| DELETE | /{device_id} | admin | 删除设备 |

## 4. 点位管理 (points)

前缀: `/api/v1/points`

| 方法 | 路径 | 认证 | 描述 |
|------|------|------|------|
| GET | / | viewer | 获取点位列表 |
| GET | /types-summary | viewer | 获取点位类型统计 |
| GET | /groups | viewer | 获取点位分组 |
| POST | /groups | operator | 创建点位分组 |
| GET | /export | operator | 导出点位配置CSV |
| POST | /batch-import | operator | 批量导入点位 |
| GET | /{point_id} | viewer | 获取点位详情 |
| POST | / | operator | 创建点位 |
| PUT | /{point_id} | operator | 更新点位 |
| DELETE | /{point_id} | admin | 删除点位 |
| PUT | /{point_id}/enable | operator | 启用点位 |
| PUT | /{point_id}/disable | operator | 禁用点位 |
| PUT | /{point_id}/link-device | operator | 关联点位到用能设备 |
| DELETE | /{point_id}/link-device | operator | 取消点位与用能设备关联 |

## 5. 实时数据 (realtime)

前缀: `/api/v1/realtime`

| 方法 | 路径 | 认证 | 描述 |
|------|------|------|------|
| GET | / | viewer | 获取所有点位实时数据 |
| GET | /summary | viewer | 获取实时数据汇总 |
| GET | /dashboard | viewer | 获取仪表盘数据 |
| GET | /energy-dashboard | viewer | 获取能源仪表盘数据 |
| GET | /{point_id} | viewer | 获取单个点位实时数据 |
| GET | /by-type/{point_type} | viewer | 按类型获取实时数据 |
| GET | /by-area/{area_code} | viewer | 按区域获取实时数据 |
| POST | /control/{point_id} | operator | 下发控制指令 |

## 6. 告警管理 (alarms)

前缀: `/api/v1/alarms`

| 方法 | 路径 | 认证 | 描述 |
|------|------|------|------|
| GET | / | viewer | 获取告警列表 |
| GET | /active | viewer | 获取活动告警 |
| GET | /count | viewer | 获取各级别告警数量 |
| GET | /statistics | viewer | 获取告警统计 |
| GET | /trend | viewer | 获取告警趋势 |
| GET | /top-points | viewer | 获取高频告警点位 |
| GET | /export | operator | 导出告警记录CSV |
| PUT | /batch-acknowledge | operator | 批量确认告警 |
| GET | /rules | viewer | 获取告警规则列表 |
| POST | /rules | operator | 创建告警规则 |
| GET | /rules/{rule_id} | viewer | 获取告警规则详情 |
| PUT | /rules/{rule_id} | operator | 更新告警规则 |
| DELETE | /rules/{rule_id} | operator | 删除告警规则 |
| PUT | /rules/{rule_id}/toggle | operator | 切换告警规则启用状态 |
| GET | /shields | viewer | 获取告警屏蔽列表 |
| POST | /shields | operator | 创建告警屏蔽 |
| DELETE | /shields/{shield_id} | operator | 删除告警屏蔽 |
| GET | /{alarm_id} | viewer | 获取告警详情 |
| PUT | /{alarm_id}/acknowledge | operator | 确认告警 |
| PUT | /{alarm_id}/resolve | operator | 解决告警 |
| PUT | /{alarm_id}/process | operator | 处理告警 |

## 7. 阈值配置 (thresholds)

前缀: `/api/v1/thresholds`

| 方法 | 路径 | 认证 | 描述 |
|------|------|------|------|
| GET | / | viewer | 获取阈值配置列表 |
| GET | /point/{point_id} | viewer | 获取点位阈值配置 |
| POST | / | operator | 创建阈值配置 |
| POST | /batch | operator | 批量配置阈值 |
| POST | /copy | operator | 复制阈值配置到其他点位 |
| GET | /version | 公开 | 获取阈值配置版本号 |
| PUT | /point/{point_id}/four-level | operator | 4级阈值一体化配置 |
| POST | /batch-by-device-type | operator | 按设备类型批量配置阈值 |
| PUT | /{threshold_id} | operator | 更新阈值配置 |
| DELETE | /{threshold_id} | operator | 删除阈值配置 |

## 8. 历史数据 (history)

前缀: `/api/v1/history`

| 方法 | 路径 | 认证 | 描述 |
|------|------|------|------|
| GET | /{point_id} | viewer | 获取点位历史数据 |
| GET | /{point_id}/trend | viewer | 获取趋势数据 |
| GET | /{point_id}/statistics | viewer | 获取统计数据 |
| GET | /compare | viewer | 多点位对比查询 |
| GET | /changes/{point_id} | viewer | 获取DI点位变化记录 |
| GET | /export | operator | 导出历史数据 |
| DELETE | /cleanup | admin | 清理过期数据 |

## 9. 能源管理 (energy)

前缀: `/api/v1/energy`

| 方法 | 路径 | 认证 | 描述 |
|------|------|------|------|
| GET | /devices | viewer | 获取用电设备列表 |
| GET | /devices/tree | viewer | 获取用电设备树 |
| POST | /devices | operator | 创建用电设备 |
| GET | /devices/shift-ratio/recommendations | viewer | 获取设备转移比例推荐值 |
| POST | /devices/shift-ratio/accept-all | operator | 接受全部推荐值 |
| POST | /devices/shift-ratio/batch-update | operator | 批量更新设备转移比例 |
| GET | /devices/shiftable | viewer | 获取可转移负荷设备列表 |
| GET | /devices/adjustable | viewer | 获取可调节参数设备列表 |
| POST | /devices/generate-configs | operator | 批量生成设备配置 |
| PUT | /devices/{device_id}/shift-ratio | operator | 更新单个设备转移比例 |
| GET | /devices/{device_id} | viewer | 获取用电设备详情 |
| PUT | /devices/{device_id} | operator | 更新用电设备 |
| DELETE | /devices/{device_id} | admin | 删除用电设备 |
| GET | /realtime | viewer | 获取实时电力数据 |
| GET | /realtime/summary | viewer | 获取电力汇总 |
| GET | /realtime/{device_id} | viewer | 获取设备实时电力 |
| GET | /pue | viewer | 获取当前PUE |
| GET | /pue/trend | viewer | 获取PUE趋势 |
| GET | /statistics/daily | viewer | 获取日能耗统计 |
| GET | /statistics/monthly | viewer | 获取月能耗统计 |
| GET | /statistics/summary | viewer | 获取能耗汇总 |
| GET | /statistics/trend | viewer | 获取能耗趋势 |
| GET | /statistics/comparison | viewer | 获取能耗对比 |
| GET | /cost/daily | viewer | 获取日电费统计 |
| GET | /cost/monthly | viewer | 获取月电费统计 |
| GET | /pricing | viewer | 获取电价配置 |
| POST | /pricing | operator | 创建电价配置 |
| PUT | /pricing/{pricing_id} | operator | 更新电价配置 |
| DELETE | /pricing/{pricing_id} | operator | 删除电价配置 |
| GET | /pricing/current | viewer | 获取当前电价配置 |
| GET | /suggestions | viewer | 获取节能建议 |
| GET | /suggestions/templates | viewer | 获取建议模板列表 |
| POST | /suggestions/analyze | operator | 触发建议分析 |
| GET | /suggestions/enhanced | viewer | 获取增强建议列表 |
| GET | /suggestions/summary | viewer | 获取建议汇总统计 |
| GET | /suggestions/enhanced/{id} | viewer | 获取增强建议详情 |
| GET | /suggestions/detail/{id} | viewer | 获取建议完整详情 |
| POST | /suggestions/{id}/recalculate | operator | 调整参数并重算 |
| GET | /saving/potential | viewer | 获取节能潜力 |
| GET | /distribution | viewer | 获取配电图数据 |
| GET | /export/daily | operator | 导出日能耗数据 |
| GET | /export/monthly | operator | 导出月能耗数据 |
| GET | /transformers | viewer | 获取变压器列表 |
| POST | /transformers | operator | 创建变压器 |
| PUT | /transformers/{id} | operator | 更新变压器 |
| DELETE | /transformers/{id} | operator | 删除变压器 |
| GET | /meter-points | viewer | 获取计量点列表 |
| POST | /meter-points | operator | 创建计量点 |
| GET | /meter-points/{id} | viewer | 获取计量点详情 |
| PUT | /meter-points/{id} | operator | 更新计量点 |
| DELETE | /meter-points/{id} | operator | 删除计量点 |
| GET | /panels | viewer | 获取配电柜列表 |
| GET | /panels/{panel_id} | viewer | 获取配电柜详情 |
| POST | /panels | operator | 创建配电柜 |
| PUT | /panels/{panel_id} | operator | 更新配电柜 |
| DELETE | /panels/{panel_id} | operator | 删除配电柜 |
| GET | /circuits | viewer | 获取配电回路列表 |
| POST | /circuits | operator | 创建配电回路 |
| PUT | /circuits/{circuit_id} | operator | 更新配电回路 |
| DELETE | /circuits/{circuit_id} | operator | 删除配电回路 |
| GET | /topology | viewer | 获取配电系统拓扑 |
| GET | /power-curve | viewer | 获取功率曲线 |
| GET | /analysis/plugins | viewer | 获取分析插件列表 |
| POST | /analysis/plugins/{id}/enable | operator | 启用插件 |
| POST | /analysis/plugins/{id}/disable | operator | 禁用插件 |
| POST | /analysis/run | operator | 执行节能分析 |
| POST | /analysis/run/{plugin_id} | operator | 执行单个分析插件 |
| GET | /analysis/summary | viewer | 获取分析汇总 |
| GET | /demand/15min-curve | viewer | 获取15分钟需量曲线 |
| GET | /demand/aggregated-curve | viewer | 获取聚合需量曲线 |
| GET | /demand/peak-analysis | viewer | 需量峰值分析 |
| GET | /demand/optimization-plan | viewer | 需量优化方案 |
| POST | /demand/forecast | operator | 需量预测 |
| GET | /report/preview | viewer | 能效报告预览 |
| GET | /report/export | operator | 导出能效报告 |
| POST | /ocr/bill | operator | 电费单OCR识别 |
| GET | /pricing-schemes | viewer | 获取电价方案列表 |
| GET | /pricing-schemes/{id} | viewer | 获取电价方案详情 |
| POST | /pricing-schemes | operator | 创建电价方案 |
| PUT | /pricing-schemes/{id} | operator | 更新电价方案 |
| DELETE | /pricing-schemes/{id} | operator | 删除电价方案 |
| POST | /pricing-schemes/{id}/validate | operator | 验证电价方案 |
| POST | /pricing-schemes/{id}/activate | operator | 激活电价方案 |
| POST | /pricing-schemes/{id}/deactivate | operator | 停用电价方案 |
| GET | /pricing-schemes/{id}/audit-logs | viewer | 获取电价方案审计日志 |

## 10. 制冷系统 (cooling)

前缀: `/api/v1/cooling`

| 方法 | 路径 | 认证 | 描述 |
|------|------|------|------|
| GET | /overview | viewer | 制冷系统总览 |
| GET | /units | viewer | 获取空调列表 |
| GET | /units/{unit_id} | viewer | 获取空调详情 |
| POST | /units | operator | 创建空调 |
| PUT | /units/{unit_id} | operator | 更新空调 |
| DELETE | /units/{unit_id} | admin | 删除空调 |
| GET | /groups | viewer | 获取群控组列表 |
| GET | /groups/{group_id} | viewer | 获取群控组详情 |
| POST | /groups | operator | 创建群控组 |
| PUT | /groups/{group_id} | operator | 更新群控组 |
| DELETE | /groups/{group_id} | admin | 删除群控组 |
| GET | /cold-aisles | viewer | 获取冷通道列表 |
| GET | /cold-aisles/{aisle_id} | viewer | 获取冷通道详情 |
| POST | /cold-aisles | operator | 创建冷通道 |
| PUT | /cold-aisles/{aisle_id} | operator | 更新冷通道 |
| DELETE | /cold-aisles/{aisle_id} | admin | 删除冷通道 |

## 11. 智能诊断 (diagnosis)

前缀: `/api/v1/diagnosis`

| 方法 | 路径 | 认证 | 描述 |
|------|------|------|------|
| GET | /categories | viewer | 获取诊断分类 |
| GET | /fault-trees | viewer | 获取故障树列表 |
| POST | /rules/reload | admin | 重载诊断规则 |
| GET | /rules | viewer | 获取诊断规则列表 |
| GET | /rules/{rule_id} | viewer | 获取诊断规则详情 |
| POST | /rules | admin | 创建诊断规则 |
| PUT | /rules/{rule_id} | admin | 更新诊断规则 |
| DELETE | /rules/{rule_id} | admin | 删除诊断规则 |
| PUT | /rules/{rule_id}/toggle | admin | 切换规则启用状态 |
| GET | /health | viewer | 获取诊断引擎健康状态 |
| GET | /sessions | viewer | 获取诊断会话列表 |
| GET | /sessions/{session_id} | viewer | 获取诊断会话详情 |
| GET | /sessions/{session_id}/audit-log | viewer | 获取会话审计日志 |
| GET | /results/by-alarm/{alarm_id} | viewer | 按告警查询诊断结果 |
| GET | /results | viewer | 获取诊断结果列表 |
| GET | /results/{result_id} | viewer | 获取诊断结果详情 |
| POST | /analyze/{alarm_id} | operator | 触发告警诊断分析 |
| POST | /annotations | operator | 创建诊断标注 |
| GET | /annotations | viewer | 获取诊断标注列表 |
| DELETE | /annotations/{id} | operator | 删除诊断标注 |
| GET | /annotations/stats | viewer | 获取标注统计 |
| GET | /battery-soh/latest | viewer | 获取最新电池SOH |
| GET | /battery-soh/{device_id} | viewer | 获取设备电池SOH |
| POST | /battery-soh/calculate/{device_id} | operator | 计算设备电池SOH |
| GET | /config/soh-weights | viewer | 获取SOH权重配置 |
| PUT | /config/soh-weights | admin | 更新SOH权重配置 |
| POST | /breaker-profiles | admin | 创建断路器档案 |
| GET | /breaker-profiles | viewer | 获取断路器档案列表 |
| GET | /breaker-profiles/{id} | viewer | 获取断路器档案详情 |
| PUT | /breaker-profiles/{id} | admin | 更新断路器档案 |
| DELETE | /breaker-profiles/{id} | admin | 删除断路器档案 |
| GET | /trend-warnings | viewer | 获取趋势预警列表 |
| POST | /trend-warnings/{id}/acknowledge | operator | 确认趋势预警 |
| GET | /sensor-fusion | viewer | 获取传感器融合记录 |
| GET | /trend-config | viewer | 获取趋势配置 |
| PUT | /trend-config | admin | 更新趋势配置 |
| POST | /counterfactual/{session_id} | operator | 触发反事实分析 |
| GET | /counterfactual/{session_id} | viewer | 获取反事实分析结果 |
| GET | /counterfactual/{session_id}/progress | viewer | 获取分析进度 |
| GET | /counterfactual | viewer | 获取反事实分析列表 |
| DELETE | /counterfactual/{session_id} | admin | 删除反事实分析 |
| GET | /reports/misdiagnosis | viewer | 获取误判报告列表 |
| POST | /reports/misdiagnosis/generate | admin | 生成误判报告 |
| GET | /reports/misdiagnosis/export | admin | 导出误判报告 |
| POST | /time-window-tuning/analyze | admin | 触发时间窗口调参分析 |
| GET | /time-window-tuning/adjustments | viewer | 获取调参建议列表 |
| POST | /time-window-tuning/adjustments/{id}/approve | admin | 批准调参建议 |
| POST | /time-window-tuning/adjustments/{id}/reject | admin | 拒绝调参建议 |
| GET | /time-window-tuning/config | viewer | 获取调参配置 |
| PUT | /time-window-tuning/config | admin | 更新调参配置 |
| GET | /training-audit | admin | 查询训练数据异常检测历史 |
| GET | /hmac-key/status | admin | 查询HMAC密钥状态 |
| POST | /hmac-key/rotate | admin | 执行HMAC密钥轮换 |
| POST | /hmac-key/verify-all | admin | 批量验证签名完整性 |
| GET | /hmac-key/rotation-logs | admin | 查询密钥轮换历史 |

## 12. 负荷转移 (shift)

前缀: `/api/v1/energy/shift`

| 方法 | 路径 | 认证 | 描述 |
|------|------|------|------|
| GET | /plans | 登录 | 获取转移计划列表 |
| POST | /plans | operator | 创建转移计划 |
| GET | /plans/{plan_id} | 登录 | 获取转移计划详情 |
| PUT | /plans/{plan_id} | operator | 更新转移计划 |
| DELETE | /plans/{plan_id} | operator | 删除转移计划 |
| POST | /plans/{plan_id}/submit | operator | 提交计划审批 |
| POST | /plans/{plan_id}/approve | operator | 审批计划 |
| POST | /plans/{plan_id}/execute | operator | 开始执行计划 |
| POST | /opportunities/analyze | operator | 触发机会分析 |
| GET | /opportunities | 登录 | 获取机会列表 |
| GET | /opportunities/{opp_id} | 登录 | 获取机会详情 |
| POST | /opportunities/{opp_id}/convert | operator | 将机会转换为计划 |
| POST | /analysis/feasibility | 登录 | 分析转移可行性 |
| POST | /analysis/constraints | 登录 | 检查约束条件 |
| POST | /analysis/benefit | 登录 | 计算收益 |
| POST | /analysis/risk | 登录 | 评估转移风险 |
| GET | /devices/shiftable | 登录 | 获取可转移设备及潜力 |
| GET | /devices/{device_id}/potential | 登录 | 获取设备转移潜力 |
| GET | /dashboard/overview | 登录 | 获取仪表盘概览 |
| GET | /dashboard/realtime | 登录 | 获取实时转移数据 |
| GET | /dashboard/trends | 登录 | 获取转移趋势 |
| GET | /statistics/summary | 登录 | 获取转移统计汇总 |
| GET | /cooling/config | 登录 | 获取制冷联动配置 |
| PUT | /cooling/config | 登录 | 更新制冷联动配置 |
| GET | /cooling/status | 登录 | 获取制冷联动状态 |
| GET | /cooling/history | 登录 | 获取制冷联动历史 |
| GET | /reports/{report_type} | 登录 | 获取负荷转移报表 |
| POST | /reports/export | 登录 | 导出负荷转移报表 |
| GET | /constraints | 登录 | 获取所有约束配置 |
| POST | /constraints | 登录 | 创建约束配置 |
| PUT | /constraints/{constraint_id} | 登录 | 更新约束配置 |
| DELETE | /constraints/{constraint_id} | 登录 | 删除约束配置 |

## 13. 预冷系统 (precool)

前缀: `/api/v1/precool`

| 方法 | 路径 | 认证 | 描述 |
|------|------|------|------|
| POST | /zones/{zone_id}/predict | operator | 温度轨迹预测 |
| GET | /zones/{zone_id}/parameters | viewer | 查询RC标定参数历史 |
| GET | /zones/{zone_id}/validation | viewer | 模型验证报告 |
| GET | /dashboard | viewer | 预冷仪表盘聚合数据 |
| GET | /zones/{zone_id}/rollback-status | viewer | 查询zone回退保护状态 |
| GET | /zones/{zone_id}/rollback-history | viewer | 查询回退历史事件 |
| GET | /rollback-overview | viewer | 全局回退状态概览 |
| POST | /zones/{zone_id}/schedule | operator | 生成预冷计划 |
| GET | /zones/{zone_id}/schedule | viewer | 查询预冷计划列表 |
| GET | /schedules/{schedule_id} | viewer | 查询预冷计划详情 |
| POST | /schedules/{schedule_id}/abort | operator | 中止预冷计划 |
| GET | /zones/{zone_id}/config | viewer | 查询预冷配置 |
| PUT | /zones/{zone_id}/config | operator | 更新预冷配置 |
| POST | /zones/{zone_id}/calibrate | operator | 触发手动RC校准 |
| GET | /zones/{zone_id}/calibration-history | viewer | 查询校准历史 |
| GET | /deployment-phase | viewer | 查询当前部署阶段 |
| PUT | /deployment-phase | admin | 切换部署阶段 |
| GET | /vpp/capacity | viewer | 查询VPP可调容量 |
| POST | /vpp/dispatch | operator | 接收VPP调控指令 |
| GET | /vpp/dispatches | viewer | 查询VPP调控指令列表 |
| GET | /vpp/statistics | viewer | 查询VPP需求响应统计 |

## 14. VPP方案分析 (vpp)

前缀: `/api/v1/vpp`

| 方法 | 路径 | 认证 | 描述 |
|------|------|------|------|
| POST | /analysis | 公开 | 生成VPP方案完整分析 |
| GET | /load-metrics | 公开 | 获取负荷特性指标 |
| GET | /cost-structure/{month} | 公开 | 获取电费结构分析 |
| GET | /transfer-potential | 公开 | 获取峰谷转移潜力 |
| GET | /vpp-revenue | 公开 | 获取VPP收益测算 |
| GET | /roi | 公开 | 获取投资回报分析 |
| GET | /formula-reference | 公开 | 获取所有计算公式参考 |

## 15. 空间拓扑 (spatial)

前缀: `/api/v1/spatial`

| 方法 | 路径 | 认证 | 描述 |
|------|------|------|------|
| GET | /sites | viewer | 获取站点列表 |
| GET | /sites/summary | viewer | 跨站点汇总数据 |
| POST | /sites | operator | 创建站点 |
| PUT | /sites/{site_id} | operator | 更新站点 |
| DELETE | /sites/{site_id} | operator | 删除站点 |
| PUT | /sites/{site_id}/status | operator | 更新站点状态 |
| GET | /sites/{site_id}/acl-rules | viewer | 获取站点MQTT ACL规则 |
| GET | /floors | viewer | 获取楼层列表 |
| POST | /floors | operator | 创建楼层 |
| PUT | /floors/{floor_id} | operator | 更新楼层 |
| DELETE | /floors/{floor_id} | operator | 删除楼层 |
| GET | /rooms | viewer | 获取房间列表 |
| POST | /rooms | operator | 创建房间 |
| PUT | /rooms/{room_id} | operator | 更新房间 |
| DELETE | /rooms/{room_id} | operator | 删除房间 |
| GET | /rows | viewer | 获取行列表 |
| POST | /rows | operator | 创建行 |
| PUT | /rows/{row_id} | operator | 更新行 |
| DELETE | /rows/{row_id} | operator | 删除行 |
| GET | /tree | viewer | 获取完整空间拓扑树 |
| PUT | /cabinets/{cabinet_id}/position | operator | 更新机柜空间位置 |
| POST | /import | operator | Excel导入空间拓扑 |
| GET | /export | viewer | 导出空间拓扑Excel |
| GET | /templates | viewer | 获取布局模板列表 |
| POST | /templates/{template_id}/apply | operator | 应用模板到房间 |

## 16. 联动管理 (linkage)

前缀: `/api/v1/linkage`

| 方法 | 路径 | 认证 | 描述 |
|------|------|------|------|
| POST | /fire-protection/reload | admin | 重载YAML消防策略 |
| GET | /fire-protection/status | viewer | 获取消防策略加载状态 |
| GET | /policies | viewer | 获取联动策略列表 |
| GET | /policies/{policy_id} | viewer | 获取联动策略详情 |
| POST | /policies | admin | 创建联动策略 |
| PUT | /policies/{policy_id} | admin | 更新联动策略 |
| DELETE | /policies/{policy_id} | admin | 删除联动策略 |
| PUT | /policies/{policy_id}/toggle | operator | 切换策略启用状态 |
| POST | /policies/{policy_id}/test | operator | 测试联动策略 |
| GET | /executions | viewer | 获取联动执行记录列表 |
| GET | /executions/recoverable | operator | 获取可恢复的执行记录 |
| GET | /executions/{execution_id} | viewer | 获取执行记录详情 |
| POST | /executions/{execution_id}/recover | operator | 发起联动恢复 |
| GET | /timeline/{execution_id} | viewer | 获取事件时间线报告 |
| GET | /timeline/{execution_id}/export | operator | 导出时间线报告Excel |
| GET | /recoveries | viewer | 获取恢复记录列表 |
| GET | /recoveries/{recovery_id} | viewer | 获取恢复记录详情 |
| POST | /recoveries/{id}/step/{order}/execute | operator | 手动执行恢复步骤 |
| POST | /recoveries/{id}/step/{order}/skip | operator | 跳过恢复步骤 |
| GET | /action-types | viewer | 获取所有支持的动作类型 |

## 17. 报表 (reports)

前缀: `/api/v1/reports`

| 方法 | 路径 | 认证 | 描述 |
|------|------|------|------|
| GET | /templates | viewer | 获取报表模板 |
| POST | /templates | operator | 创建报表模板 |
| PUT | /templates/{template_id} | operator | 更新报表模板 |
| DELETE | /templates/{template_id} | operator | 删除报表模板 |
| POST | /generate | operator | 生成报表 |
| GET | /records | viewer | 获取报表记录 |
| GET | /download/{record_id} | viewer | 下载报表 |
| GET | /daily | viewer | 获取日报数据 |
| GET | /weekly | viewer | 获取周报数据 |
| GET | /monthly | viewer | 获取月报数据 |
| POST | /auto-generate | operator | 自动生成运行报表 |
| GET | /schedules | viewer | 获取报表调度列表 |
| POST | /schedules | operator | 创建报表调度 |
| PUT | /schedules/{schedule_id} | operator | 更新报表调度 |
| DELETE | /schedules/{schedule_id} | operator | 删除报表调度 |
| GET | /summary-panel | viewer | 获取智能摘要面板 |
| GET | /auto-report-pdf/{record_id} | viewer | 导出自动报表为PDF |
| POST | /device-health/calculate | operator | 计算设备健康度 |
| GET | /device-health | viewer | 获取设备健康度列表 |
| GET | /device-health/{device_id} | viewer | 获取单个设备健康度 |

## 18. 日志 (logs)

前缀: `/api/v1/logs`

| 方法 | 路径 | 认证 | 描述 |
|------|------|------|------|
| GET | /operations | admin | 获取操作日志 |
| GET | /systems | admin | 获取系统日志 |
| GET | /communications | admin | 获取通讯日志 |
| GET | /export | admin | 导出日志CSV |
| GET | /statistics | admin | 获取日志统计 |

## 19. 系统配置 (configs)

前缀: `/api/v1/configs`

| 方法 | 路径 | 认证 | 描述 |
|------|------|------|------|
| GET | / | admin | 获取系统配置 |
| PUT | / | admin | 批量更新系统配置 |
| GET | /dictionaries | viewer | 获取数据字典 |
| GET | /license | viewer | 获取授权信息 |
| POST | /license/activate | admin | 激活授权 |
| GET | /backup | admin | 导出系统配置备份 |
| POST | /restore | admin | 从备份恢复系统配置 |
| GET | /dynamic-threshold-rules | viewer | 查询动态阈值规则 |
| PUT | /dynamic-threshold-rules | admin | 更新动态阈值规则 |
| GET | /dynamic-threshold-status | viewer | 查询动态阈值特性状态 |
| POST | /dynamic-threshold-toggle | admin | 切换动态阈值特性开关 |
| POST | /dynamic-threshold-rules/test | admin | 测试动态阈值规则 |
| GET | /dynamic-threshold-rules/history | admin | 查询规则修改历史 |
| POST | /dynamic-threshold-rules/rollback | admin | 回滚到历史版本 |
| GET | /dynamic-threshold-metrics | admin | 查询动态阈值监控指标 |

## 20. 网关管理 (gateways)

前缀: `/api/v1/gateways`

| 方法 | 路径 | 认证 | 描述 |
|------|------|------|------|
| GET | / | viewer | 获取网关列表 |
| POST | / | operator | 创建网关 |
| GET | /summary | viewer | 网关状态汇总 |
| GET | /{gateway_id} | viewer | 获取网关详情 |
| GET | /{gateway_id}/events | viewer | 网关事件历史 |
| POST | /{gateway_id}/push-config | operator | 下发配置到网关 |
| GET | /{gateway_id}/config-history | viewer | 配置下发历史 |
| PUT | /{gateway_id} | operator | 更新网关 |
| PUT | /{gateway_id}/site | admin | 分配网关到站点 |
| DELETE | /{gateway_id} | admin | 删除网关 |

## 21. 统计分析 (`/statistics`)

> 文件: `backend/app/api/v1/statistics.py`

| 方法 | 路径 | 认证 | 描述 |
|------|------|------|------|
| GET | /overview | viewer | 获取系统概览统计 |
| GET | /points | viewer | 获取点位统计 |
| GET | /alarms | viewer | 获取告警统计 |
| GET | /energy | viewer | 获取能耗统计 |
| GET | /availability | viewer | 获取可用性统计 |
| GET | /comparison | viewer | 获取同比/环比数据 |

## 22. 供配电管理 (`/power`)

> 文件: `backend/app/api/v1/power.py`

| 方法 | 路径 | 认证 | 描述 |
|------|------|------|------|
| GET | /overview | viewer | 供配电总览 |
| GET | /ups | viewer | UPS设备列表 |
| GET | /ups/{ups_id} | viewer | UPS设备详情 |
| POST | /ups | operator | 创建UPS设备 |
| PUT | /ups/{ups_id} | operator | 更新UPS设备 |
| DELETE | /ups/{ups_id} | admin | 删除UPS设备 |
| GET | /batteries | viewer | 电池组列表 |
| GET | /batteries/{bg_id} | viewer | 电池组详情 |
| POST | /batteries | operator | 创建电池组 |
| PUT | /batteries/{bg_id} | operator | 更新电池组 |
| DELETE | /batteries/{bg_id} | admin | 删除电池组 |
| GET | /cabinets | viewer | 配电柜列表 |
| GET | /cabinets/{device_id}/branches | viewer | 配电柜支路详情 |
| GET | /pdus | viewer | PDU列表 |

## 23. 电力冗余 (`/power`)

> 文件: `backend/app/api/v1/power_redundancy.py`

| 方法 | 路径 | 认证 | 描述 |
|------|------|------|------|
| GET | /devices/{device_id}/redundancy | viewer | 查询设备冗余配置 |
| PUT | /devices/{device_id}/redundancy | operator | 更新设备冗余配置 |

## 24. 负荷调控 (`/regulation`)

> 文件: `backend/app/api/v1/regulation.py`

| 方法 | 路径 | 认证 | 描述 |
|------|------|------|------|
| GET | /configs | viewer | 获取调控配置列表 |
| GET | /configs/{config_id} | viewer | 获取调控配置详情 |
| POST | /configs | operator | 创建调控配置 |
| PUT | /configs/{config_id} | operator | 更新调控配置 |
| DELETE | /configs/{config_id} | admin | 删除调控配置 |
| POST | /simulate | operator | 模拟调控效果 |
| POST | /apply | operator | 应用调控方案 |
| GET | /history | viewer | 获取调控历史 |
| GET | /recommendations | viewer | 获取调控建议 |

## 25. 资产管理 (`/asset`)

> 文件: `backend/app/api/v1/asset.py`

| 方法 | 路径 | 认证 | 描述 |
|------|------|------|------|
| GET | /cabinets | viewer | 获取机柜列表 |
| GET | /cabinets/{cabinet_id} | viewer | 获取机柜详情 |
| GET | /cabinets/{cabinet_id}/usage | viewer | 获取机柜U位使用情况 |
| PUT | /cabinets/{cabinet_id}/move-asset | operator | 拖拽移动资产U位 |
| POST | /cabinets | operator | 创建机柜 |
| PUT | /cabinets/{cabinet_id} | operator | 更新机柜 |
| DELETE | /cabinets/{cabinet_id} | admin | 删除机柜 |
| GET | /assets | viewer | 获取资产列表 |
| POST | /assets/import | operator | 批量导入资产 |
| GET | /assets/export | viewer | 导出资产列表 |
| GET | /assets/{asset_id} | viewer | 获取资产详情 |
| POST | /assets | operator | 创建资产 |
| PUT | /assets/{asset_id} | operator | 更新资产 |
| DELETE | /assets/{asset_id} | admin | 删除资产 |
| GET | /assets/{asset_id}/lifecycle | viewer | 获取资产生命周期记录 |
| POST | /maintenance | operator | 创建维护记录 |
| PUT | /maintenance/{record_id}/complete | operator | 完成维护 |
| GET | /maintenance | viewer | 获取维护记录列表 |
| POST | /inventory | operator | 创建资产盘点 |
| GET | /inventory | viewer | 获取盘点列表 |
| GET | /inventory/{inventory_id}/items | viewer | 获取盘点明细 |
| PUT | /inventory/items/{item_id} | operator | 更新盘点明细 |
| GET | /statistics | viewer | 获取资产统计信息 |
| GET | /warranty-alerts | viewer | 获取保修预警汇总 |
| GET | /warranty-expiring | viewer | 获取即将过保资产 |

## 26. 容量管理 (`/capacity`)

> 文件: `backend/app/api/v1/capacity.py`

| 方法 | 路径 | 认证 | 描述 |
|------|------|------|------|
| GET | /space | viewer | 获取空间容量列表 |
| POST | /space | operator | 创建空间容量 |
| GET | /space/{id} | viewer | 获取空间容量详情 |
| PUT | /space/{id} | operator | 更新空间容量 |
| DELETE | /space/{id} | admin | 删除空间容量 |
| GET | /power | viewer | 获取电力容量列表 |
| POST | /power | operator | 创建电力容量 |
| GET | /power/{id} | viewer | 获取电力容量详情 |
| PUT | /power/{id} | operator | 更新电力容量 |
| DELETE | /power/{id} | admin | 删除电力容量 |
| GET | /cooling | viewer | 获取制冷容量列表 |
| POST | /cooling | operator | 创建制冷容量 |
| GET | /cooling/{id} | viewer | 获取制冷容量详情 |
| PUT | /cooling/{id} | operator | 更新制冷容量 |
| DELETE | /cooling/{id} | admin | 删除制冷容量 |
| GET | /weight | viewer | 获取承重容量列表 |
| POST | /weight | operator | 创建承重容量 |
| GET | /weight/{id} | viewer | 获取承重容量详情 |
| PUT | /weight/{id} | operator | 更新承重容量 |
| DELETE | /weight/{id} | admin | 删除承重容量 |
| POST | /recommend | operator | 智能上架推荐 |
| GET | /plans | viewer | 获取容量规划列表 |
| POST | /plans | operator | 创建容量规划 |
| GET | /plans/{id} | viewer | 获取容量规划详情 |
| PUT | /plans/{id}/override-cabinet | operator | 覆盖推荐机柜 |
| DELETE | /plans/{id} | admin | 删除容量规划 |
| GET | /trend | viewer | 获取容量趋势数据 |
| GET | /forecast | viewer | 获取容量预测数据 |
| GET | /statistics | viewer | 获取容量统计信息 |
| GET | /statistics/by-location | viewer | 按区域维度聚合容量统计 |

## 27. 运维管理 (`/operation`)

> 文件: `backend/app/api/v1/operation.py`

| 方法 | 路径 | 认证 | 描述 |
|------|------|------|------|
| GET | /workorders | viewer | 获取工单列表 |
| POST | /workorders | operator | 创建工单 |
| GET | /workorders/{id} | viewer | 获取工单详情 |
| PUT | /workorders/{id} | operator | 更新工单 |
| DELETE | /workorders/{id} | admin | 删除工单 |
| POST | /workorders/{id}/assign | operator | 派单 |
| POST | /workorders/{id}/accept | operator | 接单 |
| POST | /workorders/{id}/start | operator | 开始处理工单 |
| POST | /workorders/{id}/complete | operator | 完成工单 |
| POST | /workorders/{id}/close | operator | 关闭工单 |
| GET | /workorders/{id}/logs | viewer | 获取工单日志 |
| POST | /workorders/{id}/logs | operator | 添加工单日志 |
| POST | /workorders/{id}/submit-approval | operator | 提交工单审批 |
| GET | /approvals | viewer | 获取审批列表 |
| GET | /approvals/{id} | viewer | 获取审批详情 |
| POST | /approvals/{id}/approve | admin | 批准审批 |
| POST | /approvals/{id}/reject | admin | 驳回审批 |
| GET | /plans | viewer | 获取巡检计划列表 |
| POST | /plans | operator | 创建巡检计划 |
| GET | /plans/{id} | viewer | 获取巡检计划详情 |
| PUT | /plans/{id} | operator | 更新巡检计划 |
| DELETE | /plans/{id} | admin | 删除巡检计划 |
| GET | /tasks | viewer | 获取巡检任务列表 |
| POST | /tasks | operator | 创建巡检任务 |
| GET | /tasks/{id} | viewer | 获取巡检任务详情 |
| PUT | /tasks/{id} | operator | 更新巡检任务 |
| POST | /tasks/{id}/start | operator | 开始巡检任务 |
| POST | /tasks/{id}/complete | operator | 完成巡检任务 |
| DELETE | /tasks/{id} | admin | 删除巡检任务 |
| POST | /plans/{id}/generate-tasks | operator | 从计划生成巡检任务 |
| GET | /alarm-rules | viewer | 获取告警工单规则列表 |
| POST | /alarm-rules/check | operator | 检查告警并自动创建工单 |
| POST | /alarm-rules | operator | 创建告警工单规则 |
| PUT | /alarm-rules/{id} | operator | 更新告警工单规则 |
| DELETE | /alarm-rules/{id} | admin | 删除告警工单规则 |
| GET | /knowledge | viewer | 获取知识库列表 |
| POST | /knowledge | operator | 创建知识库文章 |
| GET | /knowledge/{id} | viewer | 获取知识库文章详情 |
| PUT | /knowledge/{id} | operator | 更新知识库文章 |
| DELETE | /knowledge/{id} | admin | 删除知识库文章 |

## 28. 楼层地图 (`/floor-map`)

> 文件: `backend/app/api/v1/floor_map.py`

| 方法 | 路径 | 认证 | 描述 |
|------|------|------|------|
| GET | /floors | viewer | 获取楼层列表 |
| GET | /{floor_code}/{map_type} | viewer | 获取楼层图 |
| GET | /default | viewer | 获取默认楼层图 |

## 29. 节能方案 (`/proposals`)

> 文件: `backend/app/api/v1/proposal.py`

| 方法 | 路径 | 认证 | 描述 |
|------|------|------|------|
| GET | /templates | viewer | 获取模板列表 |
| POST | /analyze | operator | 智能分析并生成方案 |
| GET | /as-suggestions | viewer | 获取方案列表（建议格式） |
| GET | /saving-potential | viewer | 获取节能潜力统计 |
| POST | /generate | operator | 生成节能方案 |
| POST | /generate-ml-enhanced | operator | ML增强方案生成 |
| GET | /{proposal_id}/ml-analysis | viewer | 获取ML分析详情 |
| GET | /{proposal_id}/enhanced | viewer | 获取方案增强详情（含电价和设备数据） |
| POST | /rl/train | admin | 执行RL在线训练 |
| GET | /rl/model-info | viewer | 获取RL模型信息 |
| PUT | /rl/exploration-rate | admin | 更新探索率 |
| POST | /rl/save-checkpoint | admin | 保存模型检查点 |
| GET | /{proposal_id} | viewer | 获取方案详情 |
| GET | / | viewer | 获取方案列表 |
| POST | /{proposal_id}/accept | operator | 接受方案 |
| POST | /{proposal_id}/execute | operator | 执行方案 |
| GET | /{proposal_id}/execution-summary | viewer | 获取执行摘要 |
| GET | /{proposal_id}/monitoring | viewer | 获取监控数据 |
| DELETE | /{proposal_id} | admin | 删除方案 |
| GET | /{proposal_id}/measures/{measure_id}/detail | viewer | 获取措施详情（含ML和追溯） |
| PATCH | /{proposal_id}/measures/{measure_id}/status | operator | 更新措施状态 |
| POST | /{proposal_id}/measures/batch-status | operator | 批量更新措施状态 |
| POST | /{proposal_id}/monitoring/start | operator | 启动效果监测 |
| POST | /{proposal_id}/monitoring/stop | operator | 停止效果监测 |
| GET | /{proposal_id}/monitoring/status | viewer | 获取监测状态 |
| GET | /{proposal_id}/effect-report | viewer | 获取效果达成率报告 |
| GET | /{proposal_id}/effect-summary | viewer | 获取效果汇总 |
| POST | /{proposal_id}/rl-feedback | operator | 触发RL反馈 |
| POST | /{proposal_id}/rl/optimize | operator | 执行RL优化 |
| GET | /{proposal_id}/rl/status | viewer | 获取方案RL优化状态 |
| GET | /{proposal_id}/rl/history | viewer | 获取RL优化历史 |
| POST | /{proposal_id}/rl/apply/{optimization_id} | operator | 应用RL优化建议 |
| POST | /{proposal_id}/rl/train-from-monitoring | admin | 从监测数据训练 |

## 30. 电价管理 (`/pricing`)

> 文件: `backend/app/api/v1/pricing.py`

| 方法 | 路径 | 认证 | 描述 |
|------|------|------|------|
| GET | /full-config | viewer | 获取完整电价配置 |
| GET | /global-config | viewer | 获取全局电价配置 |
| POST | /global-config | admin | 创建全局电价配置 |
| PUT | /global-config/{config_id} | admin | 更新全局电价配置 |
| POST | /calculate-bill | operator | 计算电费账单 |
| POST | /estimate-savings | operator | 估算优化节省 |
| GET | /time-periods | viewer | 获取时段电价 |
| GET | /peak-valley-spread | viewer | 获取峰谷电价差 |

## 31. 节能机会 (`/opportunities`)

> 文件: `backend/app/api/v1/opportunities.py`

| 方法 | 路径 | 认证 | 描述 |
|------|------|------|------|
| GET | /dashboard | viewer | 获取机会仪表盘数据 |
| POST | /detect | operator | 手动触发节能机会检测 |
| GET | /{opportunity_id}/detail | viewer | 获取机会详情 |
| POST | /{opportunity_id}/simulate | operator | 模拟参数调整效果 |
| GET | /{opportunity_id}/devices | viewer | 获取可参与设备列表 |
| POST | /{opportunity_id}/select-devices | operator | 选择参与设备 |
| POST | /{opportunity_id}/execute | operator | 确认执行 |
| GET | / | viewer | 获取机会列表 |
| POST | / | operator | 创建节能机会 |
| PUT | /{opportunity_id} | operator | 更新节能机会 |
| DELETE | /{opportunity_id} | admin | 删除节能机会 |

## 32. 执行管理 (`/execution`)

> 文件: `backend/app/api/v1/execution.py`

| 方法 | 路径 | 认证 | 描述 |
|------|------|------|------|
| POST | /plans/from-shift | operator | 从负荷转移配置创建执行计划 |
| GET | /plans | viewer | 获取执行计划列表 |
| GET | /plans/{plan_id} | viewer | 获取执行计划详情 |
| PUT | /plans/{plan_id}/status | operator | 更新计划状态 |
| GET | /plans/{plan_id}/checklist | viewer | 生成执行清单 |
| POST | /tasks/{task_id}/execute | operator | 执行自动任务 |
| POST | /tasks/{task_id}/complete | operator | 完成手动任务 |
| GET | /tasks/{task_id} | viewer | 获取任务详情 |
| GET | /plans/{plan_id}/tracking | viewer | 获取效果追踪数据 |
| POST | /plans/{plan_id}/tracking | operator | 创建追踪任务 |
| GET | /results | viewer | 获取追踪结果列表 |
| GET | /stats/summary | viewer | 获取执行统计汇总 |

## 33. 需量管理 (`/demand`)

> 文件: `backend/app/api/v1/demand.py`

| 方法 | 路径 | 认证 | 描述 |
|------|------|------|------|
| GET | /comparison | viewer | 需量配置对比数据 |
| GET | /curve-mini | viewer | 迷你需量曲线 |
| GET | /load-period | viewer | 负荷时段分布 |
| GET | /power-factor-trend | viewer | 功率因数趋势 |

## 34. 调度管理 (`/dispatch`)

> 文件: `backend/app/api/v1/dispatch.py`

| 方法 | 路径 | 认证 | 描述 |
|------|------|------|------|
| GET | /devices | viewer | 获取可调度设备列表 |
| GET | /devices/{device_id} | viewer | 获取单个可调度设备 |
| POST | /devices | operator | 创建可调度设备 |
| PUT | /devices/{device_id} | operator | 更新可调度设备 |
| DELETE | /devices/{device_id} | admin | 删除可调度设备 |
| GET | /devices/summary/stats | viewer | 获取设备统计 |
| GET | /storage | viewer | 获取储能系统列表 |
| GET | /storage/{storage_id} | viewer | 获取单个储能系统 |
| POST | /storage | operator | 创建储能系统 |
| PUT | /storage/{storage_id} | operator | 更新储能系统 |
| DELETE | /storage/{storage_id} | admin | 删除储能系统 |
| GET | /pv | viewer | 获取光伏系统列表 |
| GET | /pv/{pv_id} | viewer | 获取单个光伏系统 |
| POST | /pv | operator | 创建光伏系统 |
| PUT | /pv/{pv_id} | operator | 更新光伏系统 |
| DELETE | /pv/{pv_id} | admin | 删除光伏系统 |
| GET | /summary | viewer | 获取所有可调度资源汇总 |

## 35. 需量监控 (`/monitoring`)

> 文件: `backend/app/api/v1/monitoring.py`

| 方法 | 路径 | 认证 | 描述 |
|------|------|------|------|
| GET | /realtime/status | viewer | 获取实时需量状态 |
| GET | /realtime/alerts | viewer | 获取当前预警列表 |
| GET | /realtime/curve | viewer | 获取实时功率曲线数据 |
| GET | /monthly/current | viewer | 获取当月电费汇总 |
| GET | /monthly/history | viewer | 获取历史月度电费 |
| GET | /demand/daily-trend | viewer | 获取日需量趋势 |
| GET | /dispatch/status | viewer | 获取实时调度状态 |
| POST | /dispatch/command | operator | 发送调度指令 |
| PUT | /dispatch/command/{command_id}/complete | operator | 完成调度指令 |

## 36. 配电拓扑 (`/topology`)

> 文件: `backend/app/api/v1/topology.py`

| 方法 | 路径 | 认证 | 描述 |
|------|------|------|------|
| POST | /nodes | operator | 创建拓扑节点 |
| PUT | /nodes | operator | 更新拓扑节点 |
| DELETE | /nodes | admin | 删除拓扑节点 |
| POST | /batch | operator | 批量拓扑操作 |
| GET | /export | viewer | 导出拓扑数据 |
| POST | /import | operator | 导入拓扑数据 |
| POST | /device-points | operator | 创建设备测点配置 |
| GET | /device-points/{device_id} | viewer | 获取设备测点配置 |
| PUT | /device-points/{point_id} | operator | 更新设备测点配置 |
| DELETE | /device-points/{device_id} | admin | 删除设备所有测点 |
| DELETE | /device-points/point/{point_id} | admin | 删除单个点位 |
| POST | /connections | operator | 创建拓扑连接 |
| DELETE | /connections | admin | 删除拓扑连接 |
| POST | /sync | operator | 同步设备与点位关联 |
| GET | /sync/status | viewer | 获取同步状态统计 |
| GET | /device/{device_id}/points | viewer | 获取设备关联的所有点位 |
| GET | /unlinked-devices | viewer | 获取未关联拓扑的设备列表 |
| POST | /sync-devices | operator | 同步拓扑节点与动环设备 |
| GET | /cascade/{node_id} | viewer | 向下级联分析 |
| GET | /upstream/{device_id} | viewer | 向上溯源分析 |

## 37. 拓扑配置 (`/topology-config`)

> 文件: `backend/app/api/v1/topology_config.py`

| 方法 | 路径 | 认证 | 描述 |
|------|------|------|------|
| GET | /power-phase | viewer | 获取电力相位映射列表 |
| GET | /power-phase/cabinet/{cabinet_id} | viewer | 获取机柜电力相位映射 |
| GET | /power-phase/pdu/{pdu_device_id}/balance | viewer | 获取PDU相位平衡 |
| POST | /power-phase | operator | 创建电力相位映射 |
| PUT | /power-phase/{mapping_id} | operator | 更新电力相位映射 |
| DELETE | /power-phase/{mapping_id} | admin | 删除电力相位映射 |
| GET | /cooling-zones | viewer | 获取制冷区域列表 |
| GET | /cooling-zones/{zone_id} | viewer | 获取制冷区域详情 |
| POST | /cooling-zones | operator | 创建制冷区域 |
| PUT | /cooling-zones/{zone_id} | operator | 更新制冷区域 |
| DELETE | /cooling-zones/{zone_id} | admin | 删除制冷区域 |
| GET | /cooling-zones/{zone_id}/capacity | viewer | 获取制冷区域容量 |
| GET | /cabinet/{cabinet_id}/topology-summary | viewer | 获取机柜拓扑汇总 |
| POST | /smart-site-selection | operator | 智能选址 |
| POST | /fault-impact-analysis | operator | 故障影响分析 |

## 38. 数据追溯 (`/trace`)

> 文件: `backend/app/api/v1/trace.py`

| 方法 | 路径 | 认证 | 描述 |
|------|------|------|------|
| GET | /{trace_id} | viewer | 获取追溯记录详情 |
| GET | /{trace_id}/tree | viewer | 获取追溯树 |
| GET | /proposal/{proposal_id} | viewer | 获取方案追溯汇总 |
| GET | /measure/{measure_id} | viewer | 获取措施追溯记录 |
| GET | /proposal/{proposal_id}/ml | viewer | 获取方案ML预测追溯 |
| GET | /measure/{measure_id}/ml | viewer | 获取措施ML预测追溯 |
| GET | /mappings/list | viewer | 获取数据源映射列表 |
| POST | /mappings | operator | 创建数据源映射 |
| GET | /templates/{template_id}/params | viewer | 获取模板参数列表 |
| POST | /templates/params | operator | 创建模板参数配置 |
| POST | /mappings/init | operator | 初始化默认数据源映射 |

## 39. 日前优化 (`/optimization`)

> 文件: `backend/app/api/v1/optimization.py`

| 方法 | 路径 | 认证 | 描述 |
|------|------|------|------|
| GET | /forecast | viewer | 获取负荷预测 |
| POST | /day-ahead | operator | 执行日前优化 |
| GET | /day-ahead/{date} | viewer | 获取日前调度计划 |
| PUT | /schedule/{schedule_id} | operator | 更新调度状态 |
| GET | /summary | viewer | 获取优化汇总 |
| GET | /compare | viewer | 计划vs实际对比 |
| GET | /learning/metrics | viewer | 获取学习指标 |
| POST | /learning/adjust | operator | 执行参数调整 |
| GET | /learning/report | viewer | 获取优化效果报告 |
| POST | /learning/feedback | operator | 提交反馈数据 |
| POST | /integration/create-opportunity | operator | 从优化结果创建节能机会 |
| POST | /integration/auto-generate | operator | 自动生成节能机会 |
| GET | /integration/statistics | viewer | 获取优化统计 |

## 40. 数据源管理 (`/datasources`)

> 文件: `backend/app/api/v1/datasources.py`

| 方法 | 路径 | 认证 | 描述 |
|------|------|------|------|
| PUT | /{datasource_id}/write-permission | admin | 切换数据源写入权限 |
| GET | / | viewer | 获取数据源列表 |
| POST | / | operator | 创建数据源 |
| POST | /test-connection | operator | 测试数据源连接 |
| GET | /export-report | viewer | 导出对接报告 |
| GET | /communication-status | viewer | 获取数据源通信状态 |
| GET | /{datasource_id} | viewer | 获取数据源详情 |
| PUT | /{datasource_id} | operator | 更新数据源 |
| POST | /{datasource_id}/test-connection | operator | 测试已有数据源连接 |
| POST | /{datasource_id}/points/validate | operator | 预校验点位Excel |
| POST | /{datasource_id}/points/import | operator | 批量导入点位 |
| DELETE | /{datasource_id} | admin | 删除数据源 |

## 41. 设备模板 (`/device-templates`)

> 文件: `backend/app/api/v1/device_templates.py`

| 方法 | 路径 | 认证 | 描述 |
|------|------|------|------|
| GET | / | viewer | 获取设备模板列表 |
| POST | / | operator | 创建设备模板 |
| GET | /{template_id} | viewer | 获取模板详情 |
| PUT | /{template_id} | operator | 更新模板 |
| DELETE | /{template_id} | admin | 删除模板 |
| POST | /{template_id}/create-datasource | operator | 从模板创建数据源 |

## 42. 系统健康 (`/system`)

> 文件: `backend/app/api/v1/system_health.py`

| 方法 | 路径 | 认证 | 描述 |
|------|------|------|------|
| GET | /health | viewer | 系统健康状态 |
| GET | /backup/config | admin | 获取备份配置 |
| PUT | /backup/config | admin | 更新备份配置 |
| POST | /backup/manual | admin | 手动备份 |
| GET | /backup/list | admin | 获取备份列表 |
| POST | /backup/restore | admin | 恢复备份 |

## 43. 数据质量 (`/data-quality`)

> 文件: `backend/app/api/v1/data_quality.py`

| 方法 | 路径 | 认证 | 描述 |
|------|------|------|------|
| GET | /status | viewer | 数据质量概览 |
| GET | /points | viewer | 数据质量点位列表 |

## 44. 告警升级 (`/escalations`)

> 文件: `backend/app/api/v1/escalation.py`

| 方法 | 路径 | 认证 | 描述 |
|------|------|------|------|
| GET | / | viewer | 获取升级规则列表 |
| POST | / | operator | 创建升级规则 |
| GET | /{escalation_id} | viewer | 获取升级规则详情 |
| PUT | /{escalation_id} | operator | 更新升级规则 |
| DELETE | /{escalation_id} | admin | 删除升级规则 |
| PUT | /{escalation_id}/toggle | operator | 切换升级规则启用状态 |

## 45. 设备控制 (`/command`)

> 文件: `backend/app/api/v1/command.py`

| 方法 | 路径 | 认证 | 描述 |
|------|------|------|------|
| POST | /submit | operator | 提交控制命令 |
| GET | /approvals | viewer | 审批工单列表 |
| GET | /approvals/{approval_id} | viewer | 审批工单详情 |
| POST | /approvals/{approval_id}/approve | admin | 批准审批 |
| POST | /approvals/{approval_id}/reject | admin | 驳回审批 |
| GET | /audit-logs | viewer | 审计日志列表 |
| GET | /risk-configs | admin | 获取风险等级配置 |
| PUT | /risk-configs | admin | 更新风险等级配置 |

## 46. 漂移检测 (`/drift`)

> 文件: `backend/app/api/v1/drift.py`

| 方法 | 路径 | 认证 | 描述 |
|------|------|------|------|
| POST | /detect | operator | 触发漂移检测 |
| GET | /results | viewer | 漂移检测结果列表 |
| GET | /summary | viewer | 漂移检测概览 |
| GET | /results/{result_id} | viewer | 漂移检测结果详情 |
| POST | /results/{result_id}/resolve | operator | 手动解除漂移标记 |

## 47. 视频监控 (`/video`)

> 文件: `backend/app/api/v1/video.py`

| 方法 | 路径 | 认证 | 描述 |
|------|------|------|------|
| POST | /nvrs | operator | 创建NVR |
| GET | /nvrs | viewer | NVR列表 |
| GET | /nvrs/{nvr_id} | viewer | NVR详情 |
| PUT | /nvrs/{nvr_id} | operator | 更新NVR |
| DELETE | /nvrs/{nvr_id} | admin | 删除NVR |
| GET | /cameras/by-alarm/{alarm_id} | viewer | 按告警查询关联摄像头 |
| GET | /cameras/by-area/{area_code} | viewer | 按区域查询摄像头 |
| GET | /cameras/by-device/{device_id} | viewer | 按设备查询摄像头 |
| POST | /cameras | operator | 创建摄像头 |
| GET | /cameras | viewer | 摄像头列表 |
| GET | /cameras/{camera_id} | viewer | 摄像头详情 |
| PUT | /cameras/{camera_id} | operator | 更新摄像头 |
| DELETE | /cameras/{camera_id} | admin | 删除摄像头 |
| POST | /ptz/control | operator | 云台控制 |
| POST | /ptz/preset | operator | 调用预置位 |
| POST | /recording/start | operator | 开始录像 |
| POST | /recording/stop | operator | 停止录像 |
| GET | /events | viewer | 视频事件列表 |
| GET | /playback/alarm/{alarm_id} | viewer | 告警回放信息 |
| GET | /playback/segments | viewer | 录像片段列表 |

## 48. OTA升级 (`/ota`)

> 文件: `backend/app/api/v1/ota.py`

| 方法 | 路径 | 认证 | 描述 |
|------|------|------|------|
| POST | /firmware | operator | 注册固件包 |
| GET | /firmware | viewer | 固件包列表 |
| DELETE | /firmware/{firmware_id} | admin | 删除固件包 |
| POST | /tasks | operator | 创建升级任务 |
| GET | /tasks | viewer | 任务列表 |
| GET | /tasks/{task_id} | viewer | 任务详情 |
| POST | /tasks/{task_id}/start | operator | 启动任务 |
| POST | /tasks/{task_id}/cancel | operator | 取消任务 |
| POST | /tasks/{task_id}/pause | operator | 暂停任务 |
| POST | /tasks/{task_id}/resume | operator | 恢复任务 |

## 49. 故障树版本 (`/fault-trees/{tree_id}/versions`)

> 文件: `backend/app/api/v1/fault_tree_versions.py`

| 方法 | 路径 | 认证 | 描述 |
|------|------|------|------|
| POST | / | admin | 创建故障树版本 |
| POST | /{version_id}/review | admin | 审核故障树版本 |
| POST | /{version_id}/activate | admin | 激活故障树版本 |
| POST | /rollback | admin | 回滚故障树版本 |
| GET | / | viewer | 获取故障树版本列表 |

## 50. 传感器元数据 (`/diagnosis/sensor-metadata`)

> 文件: `backend/app/api/v1/sensor_metadata.py`

| 方法 | 路径 | 认证 | 描述 |
|------|------|------|------|
| POST | / | operator | 创建传感器元数据 |
| GET | / | viewer | 获取传感器元数据列表 |
| GET | /{metadata_id} | viewer | 获取传感器元数据详情 |
| PUT | /{metadata_id} | operator | 更新传感器元数据 |
| DELETE | /{metadata_id} | operator | 删除传感器元数据 |
| GET | /calibration-status/{point_id} | viewer | 获取校准状态 |
| POST | /check-expired-calibrations | operator | 检查过期校准 |

## 51. 概率调参 (`/diagnosis/probability-tuning`)

> 文件: `backend/app/api/v1/probability_tuning.py`

| 方法 | 路径 | 认证 | 描述 |
|------|------|------|------|
| POST | /trigger | admin | 触发概率分析 |
| GET | /adjustments | viewer | 获取概率调整列表 |
| POST | /adjustments/{adjustment_id}/approve | admin | 批准概率调整 |
| POST | /adjustments/{adjustment_id}/reject | admin | 驳回概率调整 |
| POST | /rollback/{tree_id} | admin | 回滚概率调整 |

## 52. A/B 测试 (`/diagnosis/ab-tests`)

> 文件: `backend/app/api/v1/ab_testing.py`

| 方法 | 路径 | 认证 | 描述 |
|------|------|------|------|
| POST | / | operator | 创建A/B测试 |
| GET | / | viewer | 获取A/B测试列表 |
| GET | /{ab_test_id} | viewer | 获取A/B测试详情 |
| GET | /{ab_test_id}/report | viewer | 获取A/B测试报告 |
| PATCH | /{ab_test_id} | operator | 更新A/B测试 |
| POST | /{ab_test_id}/complete | operator | 完成A/B测试 |
| DELETE | /{ab_test_id} | admin | 删除A/B测试 |

## 53. 误判分析 (`/diagnosis/misdiagnosis-reports`)

> 文件: `backend/app/api/v1/misdiagnosis_reports.py`

| 方法 | 路径 | 认证 | 描述 |
|------|------|------|------|
| GET | / | admin | 获取误判报告列表 |
| GET | /{report_id} | admin | 获取误判报告详情 |
| GET | /{report_id}/download | admin | 下载误判报告 |
| POST | /generate | operator | 生成误判分析报告 |

## 54. 灾难恢复演练 (`/diagnosis/chaos`)

> 文件: `backend/app/api/v1/chaos_drill.py`

| 方法 | 路径 | 认证 | 描述 |
|------|------|------|------|
| GET | /schedule | admin | 获取演练计划 |
| PUT | /schedule | admin | 更新演练计划 |
| POST | /schedule/confirm | operator | 确认演练计划 |
| POST | /trigger | operator | 触发演练 |
| POST | /stop | operator | 停止演练 |
| GET | /history | admin | 获取演练历史 |

## 55. 机器学习 (`/ml`)

> 文件: `backend/app/api/v1/ml.py` (条件加载，需 torch)

| 方法 | 路径 | 认证 | 描述 |
|------|------|------|------|
| GET | /status | viewer | 获取ML模块状态 |
| POST | /analyze/loads | operator | 分析负荷数据 |
| POST | /calculate/peak-valley-saving | operator | 计算峰谷节省 |
| POST | /analyze/conflicts | operator | 分析冲突 |
| POST | /optimize/actions | operator | 优化动作 |
| POST | /rl/update | admin | 更新RL模型 |
| POST | /scheme/generate | operator | 生成方案 |
| POST | /train | admin | 训练模型 |
| POST | /integrate/opportunity-engine | operator | 集成机会引擎 |

## 56. 测试端点 (`/test-simple`)

> 文件: `backend/app/api/v1/test_endpoint.py`

| 方法 | 路径 | 认证 | 描述 |
|------|------|------|------|
| GET | /test-simple | 无 | 简单测试端点 |

## 57. 故障树详情 (内联路由)

> 文件: `backend/app/api/v1/__init__.py` (内联定义)

| 方法 | 路径 | 认证 | 描述 |
|------|------|------|------|
| GET | /fault-trees/{tree_id} | viewer | 获取故障树详情 |

---

## 统计汇总

| 指标 | 数值 |
|------|------|
| API 模块总数 | 57 |
| 端点总数 | ~817 |
| 认证方式 | JWT Bearer Token (OAuth2) |
| 角色体系 | admin / operator / viewer |
| WebSocket 通道 | 3 (realtime / alarms / system) |

---

*文档生成时间: 2026-03-17 | 项目版本: V4.2.0*
