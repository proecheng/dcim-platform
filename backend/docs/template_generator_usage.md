# TemplateGenerator 服务使用说明

## 概述

`TemplateGenerator` 是节能方案模板系统的核心服务，用于从6种预定义模板生成详细的节能方案。每个方案包含3个独立可选的措施，用户可以根据实际情况选择性实施。

## 模板类型

### A类方案（无需投资）

| 模板ID | 模板名称 | 说明 | 措施数量 |
|--------|----------|------|----------|
| **A1** | 峰谷套利优化方案 | 通过调整用电时段，避开尖峰高峰时段，降低电费 | 3 |
| **A2** | 需量控制方案 | 优化申报需量，避免偶发性高峰，降低基本电费 | 3 |
| **A3** | 设备运行优化方案 | 优化设备运行参数，提高运行效率，降低能耗 | 3 |
| **A4** | VPP需求响应方案 | 参与虚拟电厂需求响应市场，获得补贴收益 | 3 |
| **A5** | 负荷调度优化方案 | 优化负荷曲线，提高负荷率，降低峰谷差 | 3 |

### B类方案（需要投资）

| 模板ID | 模板名称 | 说明 | 措施数量 |
|--------|----------|------|----------|
| **B1** | 设备改造升级方案 | 改造老旧设备，提升能效水平 | 3 |

## 快速开始

### 基本用法

```python
from sqlalchemy.orm import Session
from app.services.template_generator import TemplateGenerator

# 创建生成器实例
generator = TemplateGenerator(db_session)

# 生成A1方案（峰谷套利优化）
proposal = generator.generate_proposal("A1", analysis_days=30)

# 访问方案信息
print(f"方案编号: {proposal.proposal_code}")
print(f"总收益: {proposal.total_benefit} 万元/年")
print(f"措施数量: {len(proposal.measures)}")

# 保存到数据库
db_session.add(proposal)
db_session.commit()
```

### 批量生成所有类型

```python
template_ids = ["A1", "A2", "A3", "A4", "A5", "B1"]
proposals = []

for template_id in template_ids:
    proposal = generator.generate_proposal(template_id, analysis_days=30)
    proposals.append(proposal)
    db_session.add(proposal)

db_session.commit()
```

## 方案结构

### EnergySavingProposal（方案对象）

```python
proposal = generator.generate_proposal("A1", 30)

# 基本信息
proposal.proposal_code        # 方案编号，如 "A1-20260125-001"
proposal.proposal_type        # 方案类型："A" 或 "B"
proposal.template_id          # 模板ID："A1"、"A2" 等
proposal.template_name        # 模板名称："峰谷套利优化方案"

# 收益和投资
proposal.total_benefit        # 总年收益（万元）
proposal.total_investment     # 总投资（万元，A类为0）

# 分析数据
proposal.current_situation    # 当前状况数据（JSON字典）
proposal.analysis_start_date  # 分析起始日期
proposal.analysis_end_date    # 分析结束日期

# 措施列表
proposal.measures            # ProposalMeasure 对象列表（通常3个）
```

### ProposalMeasure（措施对象）

```python
for measure in proposal.measures:
    # 基本信息
    measure.measure_code              # 措施编号，如 "A1-20260125-001-M001"
    measure.regulation_object         # 调节对象，如 "热处理生产线预热工序"
    measure.regulation_description    # 调节说明

    # 状态数据
    measure.current_state            # 当前状态（JSON字典）
    measure.target_state             # 目标状态（JSON字典）

    # 计算信息
    measure.calculation_formula      # 计算公式和步骤（文本）
    measure.calculation_basis        # 计算依据（文本）

    # 收益和投资
    measure.annual_benefit           # 年收益（万元）
    measure.investment               # 投资（万元）

    # 用户选择
    measure.is_selected              # 是否选中该措施（默认False）
```

## 方案详解

### A1 - 峰谷套利优化方案

通过调整用电时段，避开尖峰高峰时段，充分利用峰谷电价差。

**措施清单：**
1. **热处理预热工序时段调整**：将预热工序从尖峰时段调整至平段
2. **辅助设备错峰运行**：将部分辅助设备运行时段从高峰调整至平段
3. **空压机储气罐充气策略优化**：低谷时段提前充气，减少尖峰时段空压机启动

**核心数据来源：**
- `FormulaCalculator.calc_peak_valley_data()` - 峰谷电量统计
- `FormulaCalculator.calc_peak_shift_benefit()` - 峰谷转移收益

### A2 - 需量控制方案

优化申报需量，建立监控预警机制，避免偶发性高峰导致需量电费增加。

**措施清单：**
1. **降低申报需量至合理水平**：基于95分位需量优化申报值
2. **需量实时监控与预警**：建立需量监控机制，80%阈值预警
3. **高峰时段负荷控制**：建立负荷控制策略，削减非关键负荷

**核心数据来源：**
- `FormulaCalculator.calc_demand_control_data()` - 需量控制数据

### A3 - 设备运行优化方案

优化设备运行参数，提高运行效率，降低能耗。

**措施清单：**
1. **空压机负荷匹配优化**：优化空压机组合运行策略，提高负荷率
2. **循环水泵变频调速**：根据冷却需求调整水泵转速
3. **照明分区控制**：实施照明分区精细化管理

**核心数据来源：**
- `FormulaCalculator.calc_equipment_load_rate()` - 设备负荷率
- `FormulaCalculator.calc_equipment_optimization_potential()` - 优化潜力

### A4 - VPP需求响应方案

注册虚拟电厂需求响应资源，参与电网削峰填谷，获得补贴收益。

**措施清单：**
1. **Ⅰ级快速响应资源**（响应时间≤5分钟）：照明、空调
2. **Ⅱ级常规响应资源**（响应时间≤15分钟）：空压机、循环水泵
3. **Ⅲ级计划响应资源**（提前4小时通知）：生产负荷调整

**核心数据来源：**
- `FormulaCalculator.calc_vpp_response_potential()` - VPP响应潜力

### A5 - 负荷调度优化方案

优化负荷曲线，提高负荷率，降低峰谷差。

**措施清单：**
1. **生产计划优化**：将高能耗工序安排在低电价时段
2. **设备启停时序优化**：避免同时启动造成需量冲高
3. **负荷曲线平滑化**：通过填谷削峰手段平滑负荷曲线

**核心数据来源：**
- `FormulaCalculator.calc_load_curve_analysis()` - 负荷曲线分析

### B1 - 设备改造升级方案

改造老旧设备，提升能效水平（需要投资，有投资回收期）。

**措施清单：**
1. **老旧空压机更换为变频空压机**：投资12万元，年收益约7万元
2. **普通水泵加装变频器**：投资4.5万元，年收益约5万元
3. **传统照明改造为LED**：投资8万元，年收益约4万元

**核心数据来源：**
- `FormulaCalculator.calc_equipment_efficiency_benchmark()` - 能效对标

## 用户选择措施

方案生成后，用户可以选择性实施措施：

```python
# 生成方案
proposal = generator.generate_proposal("A1", 30)

# 用户选择措施
for measure in proposal.measures:
    # 展示给用户
    print(f"措施: {measure.regulation_object}")
    print(f"年收益: {measure.annual_benefit} 万元")

    # 用户选择
    user_input = input("是否实施? (y/n): ")
    if user_input.lower() == 'y':
        measure.is_selected = True

# 计算选中措施的总收益
selected_benefit = sum(
    m.annual_benefit for m in proposal.measures if m.is_selected
)
print(f"选中措施总收益: {selected_benefit} 万元/年")

# 保存
db_session.add(proposal)
db_session.commit()
```

## API集成示例

```python
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.services.template_generator import TemplateGenerator

router = APIRouter()

@router.post("/proposals/generate/{template_id}")
async def generate_proposal(
    template_id: str,
    analysis_days: int = 30,
    db: Session = Depends(get_db)
):
    """生成节能方案"""
    generator = TemplateGenerator(db)
    proposal = generator.generate_proposal(template_id, analysis_days)

    db.add(proposal)
    db.commit()

    return {
        "code": 200,
        "data": {
            "proposal_id": proposal.id,
            "proposal_code": proposal.proposal_code,
            "total_benefit": float(proposal.total_benefit),
            "measures": [
                {
                    "measure_code": m.measure_code,
                    "regulation_object": m.regulation_object,
                    "annual_benefit": float(m.annual_benefit)
                }
                for m in proposal.measures
            ]
        }
    }
```

## 数据依赖

TemplateGenerator 依赖以下数据表：

| 数据表 | 用途 | 必需 |
|--------|------|------|
| `EnergyDaily` | 日能耗数据（峰谷电量） | 是 |
| `DemandHistory` | 需量历史数据 | A2需要 |
| `MeterPoint` | 计量点配置（申报需量） | A2需要 |
| `PowerDevice` | 设备信息 | A3/B1需要 |
| `DeviceShiftConfig` | 设备转移配置 | A4需要 |
| `PowerCurveData` | 功率曲线数据 | A5需要 |

**注意：** 即使数据库中没有完整数据，服务也会使用默认值生成方案，但收益计算会基于模拟数据。

## 测试

运行测试：

```bash
# 运行所有测试
pytest tests/services/test_template_generator.py -v

# 运行特定测试
pytest tests/services/test_template_generator.py::TestTemplateGenerator::test_generate_a1_peak_valley_proposal -v

# 查看详细输出
pytest tests/services/test_template_generator.py -v -s
```

## 扩展

### 添加新模板

1. 在 `TEMPLATE_CONFIGS` 中添加配置
2. 实现生成方法（如 `generate_xxx_proposal`）
3. 在 `generate_proposal` 的 `generator_map` 中添加映射
4. 添加对应的测试用例

### 自定义措施

```python
def _generate_measure_custom(self, proposal, params):
    """自定义措施生成方法"""
    measure = ProposalMeasure(
        measure_code=f"{proposal.proposal_code}-M001",
        regulation_object="自定义调节对象",
        regulation_description="自定义描述",
        current_state={...},
        target_state={...},
        calculation_formula="计算公式",
        calculation_basis="计算依据",
        annual_benefit=Decimal("10.5"),
        investment=Decimal("0")
    )
    return measure
```

## 常见问题

### Q: 如何修改措施数量？

A: 在对应的生成方法中添加或删除措施即可，例如在 `generate_peak_valley_proposal` 中添加第4个措施。

### Q: 如何调整收益计算逻辑？

A: 修改 `FormulaCalculator` 中的计算方法，或在措施生成方法中调整参数。

### Q: 方案编号规则是什么？

A: 格式为 `{template_id}-{日期YYYYMMDD}-{序号}，如 A1-20260125-001`

### Q: 如何处理数据缺失？

A: 服务会使用默认值，建议在生产环境中完善数据采集。

## 更新日志

- **2026-01-25**: 初始版本，实现6种模板和18个措施的生成
