# 系统改进方案 (V2.3)

## 改进需求分析

### 需求1: 增强监控仪表盘
**现状**: 仪表盘过于简单，缺少能耗、效率、建议等关键信息
**改进目标**:
- 显示实时能耗数据（总功率、IT负载、制冷功率）
- 显示PUE效率指标（当前PUE、趋势、历史对比）
- 显示节能建议概览（待处理建议数、潜在节能量）
- 显示需量状态（当前需量、申报需量、利用率）
- 显示成本信息（今日电费、本月电费、预测电费）

### 需求2: 负荷功率调节功能
**现状**: 只有负荷转移分析，缺少负荷调节功能
**改进目标**:
- 增加负荷调节配置（设备类型、可调功率范围、调节方式）
- 支持空调温度调节（温度 ↔ 功率映射）
- 支持照明亮度调节（亮度 ↔ 功率映射）
- 支持设备运行模式调节（节能模式 vs 标准模式）
- 实现需量预测与调节建议
- 提供调节策略优化算法

**技术方案**:
```
负荷调节类型:
1. 温度调节 (空调)
   - 每升高1℃，功率降低约5-8%
   - 可调范围: 22-28℃
   - 舒适度影响评估

2. 亮度调节 (照明)
   - 线性调节: 0-100%
   - 可调范围: 30-100%
   - 照度标准检查

3. 运行模式 (服务器/UPS)
   - 节能模式: 功率降低10-15%
   - 标准模式: 100%功率
   - 性能影响评估

4. 负载优先级 (可中断负载)
   - 高优先级: 核心业务，不可调
   - 中优先级: 辅助系统，可小幅调节
   - 低优先级: 非关键负载，可大幅调节或暂停
```

### 需求3: 完善需量分析方法
**现状**: 缺少具体分析方法，只能刷新但无结果
**改进目标**:
- 实现基于历史数据的需量分析算法
- 提供多种分析维度（日需量曲线、月最大需量、需量利用率）
- 给出具体的需量优化建议
- 显示需量优化效果预测

**分析方法**:
```
1. 需量分析算法:
   - 滑动窗口需量计算（15分钟间隔）
   - 月最大需量识别
   - 需量利用率计算 = 月最大需量 / 申报需量
   - 超需量风险评估

2. 优化策略分析:
   - 错峰用电策略（将高负荷转移到低负荷时段）
   - 负荷调节策略（降低峰值功率）
   - 需量申报调整建议
   - 成本收益分析

3. 具体实现数据:
   - 生成模拟的15分钟功率数据（基于当前实时数据）
   - 计算滑动需量（连续15分钟平均功率）
   - 识别需量高峰时段
   - 给出可调节设备列表和调节建议
```

### 需求4: 细化节能建议系统
**现状**: 节能建议过于笼统，缺少具体格式和自动化分析
**改进目标**:
- 定义10+种节能建议模板
- 实现自动分析引擎，根据数据自动生成建议
- 每种建议包含：问题描述、节能潜力、实施步骤、预期效果

**节能建议模板库**:

```
模板1: PUE过高建议
触发条件: PUE > 1.8
建议内容:
  - 标题: "机房PUE偏高，建议优化制冷系统"
  - 问题: "当前PUE为{pue_value}，高于行业标准1.5"
  - 分析: "制冷功率占总功率{cooling_ratio}%，建议值应低于30%"
  - 措施:
    1. 提高空调设定温度至24-26℃
    2. 优化机房气流组织，消除热点
    3. 采用冷热通道封闭方案
  - 预期: "PUE可降至{target_pue}，年节电{saving_kwh}kWh，节省{saving_cost}元"
  - 优先级: 高

模板2: 空调温度过低
触发条件: 空调设定温度 < 22℃
建议内容:
  - 标题: "空调温度设定过低，存在节能空间"
  - 问题: "当前空调设定温度{current_temp}℃，低于推荐值24℃"
  - 分析: "温度每升高1℃，制冷功率降低约6%"
  - 措施:
    1. 将空调温度调高至24℃
    2. 监测设备温度，确保安全
  - 预期: "制冷功率可降低{power_reduction}kW，月节省{monthly_saving}元"
  - 优先级: 中

模板3: 峰时用电过高
触发条件: 峰时电量 > 总电量的50%
建议内容:
  - 标题: "峰时用电占比过高，建议错峰用电"
  - 问题: "峰时用电占比{peak_ratio}%，电费成本高"
  - 分析: "峰谷电价差为{price_diff}元/kWh"
  - 措施:
    1. 将非关键任务调整至谷时（23:00-07:00）
    2. 优化设备启停时间
    3. 使用储能设备削峰填谷
  - 预期: "月电费可节省{cost_saving}元"
  - 优先级: 高

模板4: 需量申报不合理
触发条件: 需量利用率 < 70% 或 > 95%
建议内容:
  - 标题: "需量申报{status}，建议调整"  # 过高/偏低
  - 问题: "申报需量{declared}kW，实际最大需量{actual}kW，利用率{ratio}%"
  - 分析: "申报过高导致容量电费浪费；申报过低面临超需量罚款风险"
  - 措施:
    1. 建议申报需量调整为{recommended}kW
    2. 月容量电费差额{fee_diff}元
  - 预期: "年节省容量电费{annual_saving}元"
  - 优先级: 高

模板5: 设备长时间空载
触发条件: 设备负载率 < 30% 持续 > 24小时
建议内容:
  - 标题: "{device_name}长时间低负载运行"
  - 问题: "设备负载率仅{load_ratio}%，持续{duration}小时"
  - 分析: "空载功耗约为满载功耗的{idle_ratio}%，存在浪费"
  - 措施:
    1. 评估是否可关闭该设备
    2. 合并负载，提高设备利用率
    3. 启用设备节能模式
  - 预期: "可节省功耗{power_saving}kW，月节省{cost_saving}元"
  - 优先级: 中

模板6: 照明长时间开启
触发条件: 非工作时间照明功率 > 白天的50%
建议内容:
  - 标题: "非工作时间照明能耗过高"
  - 问题: "夜间照明功率{night_power}kW，为白天的{ratio}%"
  - 分析: "建议非工作时间仅保留必要照明"
  - 措施:
    1. 安装定时控制或感应开关
    2. 非工作时间照明降低50%
  - 预期: "日节电{daily_saving}kWh，年节省{annual_cost}元"
  - 优先级: 低

模板7: UPS负载率过低
触发条件: UPS负载率 < 40%
建议内容:
  - 标题: "UPS容量配置过大，效率偏低"
  - 问题: "UPS负载率仅{load_ratio}%，处于低效运行区"
  - 分析: "UPS最佳效率区为50-80%负载"
  - 措施:
    1. 增加IT负载，提高UPS利用率
    2. 或更换为容量匹配的UPS
  - 预期: "UPS效率可提升{efficiency_gain}%"
  - 优先级: 低

模板8: 功率因数偏低
触发条件: 功率因数 < 0.9
建议内容:
  - 标题: "功率因数偏低，存在无功损耗"
  - 问题: "当前功率因数{pf_value}，低于标准0.9"
  - 分析: "低功率因数导致线路损耗增加，可能面临罚款"
  - 措施:
    1. 安装无功补偿装置
    2. 减少感性负载
  - 预期: "功率因数提升至0.95以上，降低损耗{loss_reduction}kW"
  - 优先级: 中

模板9: 冷却液温差过小
触发条件: 供回水温差 < 5℃
建议内容:
  - 标题: "冷却系统温差过小，效率低下"
  - 问题: "供回水温差仅{delta_t}℃，设计值应为8-12℃"
  - 分析: "温差过小说明冷却水流量过大或换热不充分"
  - 措施:
    1. 调节冷却水泵流量
    2. 检查换热器积垢情况
    3. 优化末端设备冷量分配
  - 预期: "冷却系统效率提升{efficiency_gain}%"
  - 优先级: 中

模板10: 需量临近超标
触发条件: 当前15分钟平均功率 > 申报需量的95%
建议内容:
  - 标题: "⚠️ 需量即将超标，建议立即采取措施"
  - 问题: "当前15分钟平均功率{current_demand}kW，申报需量{declared}kW"
  - 分析: "超需量将产生2倍电费罚款"
  - 措施:
    1. 立即降低空调设定温度（临时措施）
    2. 暂停非关键负载
    3. 调节可控设备至节能模式
  - 预期: "避免超需量罚款，预计节省{penalty_saving}元"
  - 优先级: 紧急
```

## 数据库设计改进

### 新增表1: 负荷调节配置表
```sql
CREATE TABLE load_regulation_configs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    device_id INTEGER NOT NULL,  -- 关联用电设备
    regulation_type VARCHAR(20),  -- temperature, brightness, mode, load
    min_value REAL,  -- 最小可调值
    max_value REAL,  -- 最大可调值
    current_value REAL,  -- 当前值
    step_size REAL,  -- 调节步长
    power_factor REAL,  -- 功率系数（每单位变化对应的功率变化）
    priority INTEGER,  -- 调节优先级 1-5
    is_enabled BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP,
    updated_at TIMESTAMP,
    FOREIGN KEY (device_id) REFERENCES power_devices(id)
);
```

### 新增表2: 需量分析记录表
```sql
CREATE TABLE demand_analysis_records (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    meter_point_id INTEGER NOT NULL,
    analysis_date DATE,
    max_demand REAL,  -- 月最大需量
    max_demand_time TIMESTAMP,  -- 最大需量发生时间
    declared_demand REAL,  -- 申报需量
    utilization_rate REAL,  -- 需量利用率
    over_demand_risk REAL,  -- 超需量风险评分
    optimization_potential REAL,  -- 优化潜力(kW)
    recommended_actions TEXT,  -- JSON: 推荐措施列表
    created_at TIMESTAMP,
    FOREIGN KEY (meter_point_id) REFERENCES meter_points(id)
);
```

### 新增表3: 15分钟需量数据表
```sql
CREATE TABLE demand_15min_data (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    meter_point_id INTEGER NOT NULL,
    timestamp TIMESTAMP,
    average_power REAL,  -- 15分钟平均功率
    is_peak_period BOOLEAN,  -- 是否峰时
    is_max_of_month BOOLEAN,  -- 是否当月最大需量
    recorded_at TIMESTAMP,
    FOREIGN KEY (meter_point_id) REFERENCES meter_points(id)
);

CREATE INDEX idx_demand_meter_time ON demand_15min_data(meter_point_id, timestamp);
```

### 更新表: 节能建议表
```sql
-- 在 energy_suggestions 表中增加字段
ALTER TABLE energy_suggestions ADD COLUMN template_id VARCHAR(50);  -- 建议模板ID
ALTER TABLE savings ADD COLUMN implementation_steps TEXT;  -- JSON: 实施步骤
ALTER TABLE energy_suggestions ADD COLUMN expected_effect TEXT;  -- JSON: 预期效果
ALTER TABLE energy_suggestions ADD COLUMN parameters TEXT;  -- JSON: 模板参数
```

## API 接口设计改进

### 新增API组: 负荷调节
```
1. GET /api/v1/energy/regulation/configs - 获取负荷调节配置列表
2. POST /api/v1/energy/regulation/configs - 创建调节配置
3. PUT /api/v1/energy/regulation/configs/{id} - 更新配置
4. POST /api/v1/energy/regulation/simulate - 模拟调节效果
5. POST /api/v1/energy/regulation/apply - 应用调节方案
6. GET /api/v1/energy/regulation/recommendations - 获取调节建议
```

### 增强API: 需量分析
```
7. GET /api/v1/energy/demand/15min-curve - 获取15分钟需量曲线
8. GET /api/v1/energy/demand/peak-analysis - 需量峰值分析
9. GET /api/v1/energy/demand/optimization-plan - 需量优化方案
10. POST /api/v1/energy/demand/forecast - 需量预测
```

### 增强API: 节能建议
```
11. POST /api/v1/energy/suggestions/analyze - 触发自动分析
12. GET /api/v1/energy/suggestions/templates - 获取建议模板列表
13. GET /api/v1/energy/suggestions/{id}/details - 获取建议详情（含实施步骤）
```

### 增强API: 监控仪表盘
```
14. GET /api/v1/realtime/energy-dashboard - 能耗综合仪表盘
   返回数据:
   {
     "realtime": {
       "total_power": 120.5,
       "it_load": 80.2,
       "cooling_load": 35.3,
       "other_load": 5.0,
       "pue": 1.50
     },
     "efficiency": {
       "current_pue": 1.50,
       "target_pue": 1.30,
       "pue_trend": "stable",
       "cooling_efficiency": 0.85
     },
     "demand": {
       "current_demand": 115.0,
       "declared_demand": 150.0,
       "utilization_rate": 0.77,
       "risk_level": "low"
     },
     "cost": {
       "today_cost": 580.5,
       "month_cost": 12500.0,
       "forecast_month_cost": 18000.0
     },
     "suggestions": {
       "total_count": 8,
       "urgent_count": 1,
       "potential_saving_kwh": 500.0,
       "potential_saving_cost": 600.0
     }
   }
```

## 前端页面改进

### 1. 监控仪表盘增强
```vue
新增卡片:
- 能耗概览卡片 (实时功率分布饼图 + 数值)
- PUE效率卡片 (仪表盘 + 趋势线)
- 需量状态卡片 (进度条 + 风险提示)
- 成本信息卡片 (今日/本月/预测)
- 节能建议卡片 (紧急建议数 + 潜在节能量)
```

### 2. 新增页面: 负荷调节
```
路由: /energy/regulation
功能:
- 可调节设备列表（显示当前值、可调范围）
- 调节模拟器（拖动滑块查看功率变化）
- 调节方案推荐（基于当前需量状况）
- 一键应用优化方案
```

### 3. 需量分析页面增强
```
新增功能:
- 15分钟需量曲线图（可交互查看具体值）
- 月最大需量标注
- 需量优化方案对比（当前 vs 优化后）
- 具体优化措施列表（可勾选应用）
```

### 4. 节能建议页面增强
```
改进:
- 建议卡片显示模板化内容
- 展开查看详细步骤和预期效果
- 建议分类筛选（PUE优化/成本优化/需量优化）
- 建议优先级排序
- 实施进度跟踪
```

## 实施计划

### Phase 1: 需求分析与技术选型 (V2.3)
- 更新 findings.md 设计文档
- 细化功能需求和技术方案

### Phase 2: 数据库与API设计 (V2.3)
- 创建新的数据库表
- 设计新的API接口
- 更新Schema定义

### Phase 3: 后端实现
- 实现负荷调节服务
- 实现需量分析算法
- 实现节能建议引擎
- 实现能耗仪表盘API

### Phase 4: 前端实现
- 增强监控仪表盘
- 创建负荷调节页面
- 增强需量分析页面
- 增强节能建议页面

### Phase 5: 测试与优化
- 功能测试
- 性能优化
- 用户体验优化
