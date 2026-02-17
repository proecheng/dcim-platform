# Story 6-3: 节能机会自动识别

## Story

As a 能源管理员,
I want 系统自动识别节能机会,
So that 我可以发现潜在的电费节省空间。

## Status: Ready

## FR 追溯: FR49

## Acceptance Criteria

1. 系统定时（每小时）自动运行6种分析插件，识别节能机会
2. 自动识别的机会持久化到 `energy_opportunities` 表，附带来源插件、置信度、预估节省金额
3. 每种机会附带预估节省金额和实施建议（通过 `analysis_data` JSON 字段）
4. 插件架构可扩展，新增插件不影响已有分析（已有架构满足，本 Story 不改动插件基类）
5. 前端节能分析页面可查看自动识别的机会列表，区分"自动识别"和"手动创建"
6. 避免重复创建：同一插件在同一天内不重复生成相同类型的机会
7. 仪表盘数据源从纯内存计算切换为 DB 查询 + 实时分析混合模式

## 对抗性审查修复记录

### [C1] SuggestionResult 无 plugin_id 属性
- **问题**: generate_opportunities() 的 _convert_to_opportunity 用 hasattr(result, 'plugin_id')，但 SuggestionResult 没有 plugin_id 字段，所有结果都会映射为 'unknown'
- **修复**: 检测器绕过 OpportunityEngine.generate_opportunities()，直接调用 plugin_manager 逐插件执行，用 plugin.plugin_id 标记来源

### [C2] SuggestionResult.priority 是 PluginPriority 枚举(1-4)，不是 int(1-3)
- **问题**: PluginPriority 有 CRITICAL=1, HIGH=2, MEDIUM=3, LOW=4 四个级别
- **修复**: 映射 CRITICAL/HIGH→"high", MEDIUM→"medium", LOW→"low"

### [C3] SuggestionResult 无 potential_saving 字段
- **问题**: 实际字段是 estimated_cost_saving(元/年) 和 estimated_saving(kWh/年)
- **修复**: 映射 estimated_cost_saving → potential_saving

### [C4] SuggestionResult.confidence 是 int(0-100)，DB 是 Numeric(3,2)(0.00-1.00)
- **问题**: 直接存储 80 到 Numeric(3,2) 会溢出（最大 9.99）
- **修复**: confidence / 100.0 后再存储

### [C5] SuggestionResult 无 implementation_steps 字段
- **问题**: 实际字段是 detail(str) 和 analysis_data(dict)
- **修复**: 将 detail、estimated_saving、implementation_difficulty、payback_period、related_devices 和 analysis_data 合并存入 JSON

### [H1] 去重只检查 discovered 状态会导致重复
- **修复**: 去重排除 rejected/completed 状态，其余所有状态都算已存在

### [H2] OpportunityCategory 是 str 枚举，不能直接 .value 得到 int
- **修复**: 显式映射字典 CATEGORY_TO_INT

### [H3] 定时任务不应受 simulation_enabled 控制
- **修复**: 检测器始终运行（模拟模式下也能分析模拟数据），无需新增配置项

### [H4] 无 opportunity_detection_enabled 配置
- **修复**: 不新增配置项，检测器始终启用

### [H5] SQLite/PostgreSQL 日期函数兼容
- **修复**: 使用 func.date(discovered_at) == date.today()

### [M1] 批量提交风险
- **修复**: 逐条 flush + 最终一次 commit，失败时 rollback 整批

### [M3] 定时任务需要在 shutdown 时 cancel
- **修复**: 在 yield 后添加 detection_task.cancel()

## 现有基础设施分析

### 已存在（不需要创建）
- **6个分析插件**: peak_valley, demand_optimization, power_factor, load_shifting, pue_optimization, equipment_efficiency
- **PluginManager**: 单例，负责注册、构建上下文、执行分析
- **OpportunityEngine**: 整合插件（但 generate_opportunities 有数据丢失问题，本 Story 绕过它）
- **EnergyOpportunity 模型**: 完整 ORM，含 category(int)/title/description/priority(str)/status/potential_saving(Numeric)/confidence(Numeric 3,2)/analysis_data(JSON)/source_plugin/trigger_condition
- **OpportunityMeasure 模型**: 机会措施表
- **opportunities.py API**: 完整 CRUD + dashboard + simulate + execute
- **前端**: opportunities.ts API、opportunity.ts Pinia store、analysis.vue 视图

### SuggestionResult 实际字段（base.py:320-363）
```
suggestion_type: SuggestionType (enum)
priority: PluginPriority (enum: CRITICAL=1, HIGH=2, MEDIUM=3, LOW=4)
title: str
description: str
detail: str
estimated_saving: float (kWh/年)
estimated_cost_saving: float (元/年)
implementation_difficulty: str
payback_period: str
related_devices: List[str]
analysis_data: Dict[str, Any]
created_at: datetime
confidence: int (0-100)
```

### 缺失（本 Story 需要实现）
1. **自动检测定时任务**: main.py 中没有定时运行插件的调度器
2. **插件结果 → EnergyOpportunity 持久化**: 需要正确的字段映射（见上）
3. **去重逻辑**: 同一天同一插件不应重复创建相同机会
4. **前端自动识别标识**: analysis.vue 的 dashboard 没有区分自动/手动来源

## 技术方案

### Task 1: 创建自动检测服务 `opportunity_detector.py`

**文件**: `backend/app/services/opportunity_detector.py`

**关键设计决策**: 绕过 OpportunityEngine.generate_opportunities()，直接调用 plugin_manager 逐插件执行。原因：generate_opportunities 内部的 _convert_to_opportunity 会丢失 plugin_id（SuggestionResult 没有此字段），导致所有机会的 source_plugin 都是 'unknown'。

```python
class OpportunityDetector:
    """节能机会自动检测服务"""

    CATEGORY_TO_INT = {
        OpportunityCategory.BILL_OPTIMIZATION: 1,
        OpportunityCategory.DEVICE_OPERATION: 2,
        OpportunityCategory.EQUIPMENT_UPGRADE: 3,
        OpportunityCategory.COMPREHENSIVE: 4,
    }

    PRIORITY_TO_STR = {
        PluginPriority.CRITICAL: "high",
        PluginPriority.HIGH: "high",
        PluginPriority.MEDIUM: "medium",
        PluginPriority.LOW: "low",
    }

    def __init__(self, db: AsyncSession):
        self.db = db
        register_all_plugins()

    async def run_detection(self, days: int = 30) -> Dict[str, Any]:
        """
        1. plugin_manager.build_context() 构建分析上下文
        2. 逐插件执行 plugin.analyze(context)，保留 plugin.plugin_id
        3. 对每个 SuggestionResult 做去重检查
        4. 持久化新发现的机会
        5. 返回统计
        """
```

**字段映射（SuggestionResult → EnergyOpportunity）**:
| SuggestionResult 字段 | 转换 | EnergyOpportunity 字段 |
|---|---|---|
| plugin.plugin_id | 直接 | source_plugin |
| PLUGIN_CATEGORY_MAPPING[plugin_id] | CATEGORY_TO_INT[enum] | category (int 1-4) |
| result.priority | PRIORITY_TO_STR[enum] | priority (str) |
| result.estimated_cost_saving | 直接 (元/年) | potential_saving |
| result.confidence | / 100.0 | confidence (0.00-1.00) |
| result.title | 直接 | title |
| result.description | 直接 | description |
| result.detail + analysis_data + ... | 合并为 dict | analysis_data (JSON) |
| f"自动检测 - {plugin.plugin_name}" | 构造 | trigger_condition |

**去重策略**:
- 查询: `source_plugin=X AND category=Y AND func.date(discovered_at)=today AND status NOT IN ('rejected', 'completed')`
- 使用 `func.date()` 兼容 SQLite 和 PostgreSQL

**提交策略**: 逐条 flush + 最终一次 commit

### Task 2: 注册定时任务到 main.py

**文件**: `backend/app/main.py`

```python
async def _opportunity_detection_loop():
    """节能机会自动检测定时任务 - 每小时执行"""
    await asyncio.sleep(60)
    while True:
        try:
            async with async_session() as db:
                from app.services.opportunity_detector import OpportunityDetector
                detector = OpportunityDetector(db)
                result = await detector.run_detection()
                logger.info(f"节能机会自动检测完成: {result}")
        except Exception as e:
            logger.error(f"节能机会自动检测失败: {e}")
        await asyncio.sleep(3600)
```

**关键点**: 不受 simulation_enabled 控制，import 放循环内避免循环导入，shutdown 时 cancel

### Task 3: 增强 Dashboard API

**文件**: `backend/app/api/v1/opportunities.py`

DB 有数据时跳过 engine.get_opportunity_summary() 实时分析（节省性能）。

### Task 4: 前端 - 机会列表增加来源标识

**文件**: `frontend/src/views/energy/analysis.vue`

source_plugin 非空 → "自动识别" Tag（蓝色），为空 → "手动创建" Tag（灰色）

### Task 5: 前端 - 触发手动检测按钮

**文件**: `frontend/src/views/energy/analysis.vue`

overview tab 增加"立即检测"按钮，调用 triggerDetection() API。

### Task 6: 新增手动触发检测 API

**文件**: `backend/app/api/v1/opportunities.py`

**重要**: 路由 `/detect` 必须在 `/{opportunity_id}` 之前注册。

```python
@router.post("/detect", summary="手动触发节能机会检测")
async def trigger_detection(
    days: int = Query(30, ge=7, le=365),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin)
):
    from ...services.opportunity_detector import OpportunityDetector
    detector = OpportunityDetector(db)
    result = await detector.run_detection(days=days)
    return {"code": 0, "data": result, "message": "检测完成"}
```

### Task 7: 后端测试

**文件**: `backend/tests/test_opportunity_detector.py`

1. `test_run_detection_creates_opportunities` - 检测创建机会记录
2. `test_run_detection_dedup` - 同一天重复运行不创建重复记录
3. `test_category_mapping` - CATEGORY_TO_INT 映射正确
4. `test_priority_mapping` - PRIORITY_TO_STR 映射正确
5. `test_confidence_conversion` - int(0-100) → float(0.00-1.00)
6. `test_potential_saving_mapping` - estimated_cost_saving → potential_saving
7. `test_detection_with_no_data` - 无数据时不崩溃
8. `test_trigger_detection_api` - POST /detect 可调用
9. `test_dedup_excludes_rejected_completed` - rejected/completed 不阻止新创建
10. `test_analysis_data_json_structure` - JSON 包含 detail、estimated_saving_kwh 等

### Task 8: 前端 API 模块更新

**文件**: `frontend/src/api/modules/opportunities.ts`

```typescript
export function triggerDetection(days?: number) {
  return request.post<ResponseModel<DetectionResult>>('/v1/opportunities/detect', null, {
    params: { days }
  })
}

export interface DetectionResult {
  total_analyzed: number
  new_opportunities: number
  skipped_duplicates: number
  errors: number
  details: Array<{
    plugin_id: string
    opportunities_found: number
    new_created: number
    skipped: number
  }>
}
```

## 实施顺序

1. Task 1: opportunity_detector.py（核心服务）
2. Task 6: 手动触发 API — 注意路由顺序
3. Task 7: 后端测试
4. Task 2: 定时任务注册 + shutdown cancel
5. Task 3: Dashboard 增强
6. Task 8: 前端 API 更新
7. Task 4 + Task 5: 前端 UI 更新

## 关键约束

- **不修改插件基类或现有插件**: 本 Story 只消费插件输出
- **不修改 EnergyOpportunity 模型**: 无需数据库迁移
- **不修改 config.py**: 不新增配置项
- **绕过 generate_opportunities()**: 直接调用 plugin_manager 逐插件执行
- **去重窗口为自然日**: func.date(discovered_at) == date.today()
- **confidence 除以 100**: int(0-100) → Numeric(3,2)(0.00-1.00)
- **estimated_cost_saving → potential_saving**: 不是 estimated_saving（那是 kWh）
- **energy.py 不修改**: 所有新端点在 opportunities.py 中
- **路由顺序**: /detect 必须在 /{opportunity_id} 之前
