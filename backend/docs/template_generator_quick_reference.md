# TemplateGenerator 快速参考

## 一行代码生成方案

```python
proposal = TemplateGenerator(db).generate_proposal("A1", 30)
```

## 6种模板速查

| ID | 名称 | 类型 | 投资 | 典型收益 |
|----|------|------|------|----------|
| A1 | 峰谷套利 | A | 0 | 15-30万/年 |
| A2 | 需量控制 | A | 0 | 3-8万/年 |
| A3 | 设备优化 | A | 0 | 5-12万/年 |
| A4 | VPP响应 | A | 0 | 8-20万/年 |
| A5 | 负荷调度 | A | 0 | 6-15万/年 |
| B1 | 设备改造 | B | 20-30万 | 12-18万/年 |

## 方案对象速查

```python
# 访问方案信息
proposal.proposal_code       # "A1-20260125-001"
proposal.template_name       # "峰谷套利优化方案"
proposal.total_benefit       # Decimal('25.50') 万元/年
proposal.total_investment    # Decimal('0')
proposal.measures           # 3个措施的列表
```

## 措施对象速查

```python
# 遍历措施
for measure in proposal.measures:
    measure.regulation_object      # "热处理生产线预热工序"
    measure.annual_benefit         # Decimal('8.96') 万元
    measure.current_state          # {'时段': '尖峰', ...}
    measure.target_state           # {'时段': '平段', ...}
    measure.calculation_formula    # 详细计算步骤
    measure.is_selected           # False (用户选择标记)
```

## 常用操作

### 生成单个方案
```python
from app.services.template_generator import TemplateGenerator

generator = TemplateGenerator(db)
proposal = generator.generate_proposal("A1", analysis_days=30)
db.add(proposal)
db.commit()
```

### 批量生成所有方案
```python
for tid in ["A1", "A2", "A3", "A4", "A5", "B1"]:
    p = generator.generate_proposal(tid, 30)
    db.add(p)
db.commit()
```

### 用户选择措施
```python
proposal = generator.generate_proposal("A1", 30)
proposal.measures[0].is_selected = True  # 选择第1个措施
proposal.measures[1].is_selected = False # 不选择第2个措施
db.commit()
```

### 计算选中措施收益
```python
selected_benefit = sum(
    m.annual_benefit
    for m in proposal.measures
    if m.is_selected
)
```

## FormulaCalculator 调用速查

| 方法 | 用途 | 模板 |
|------|------|------|
| `calc_peak_valley_data()` | 峰谷电量统计 | A1 |
| `calc_peak_shift_benefit()` | 峰谷转移收益 | A1 |
| `calc_demand_control_data()` | 需量控制数据 | A2 |
| `calc_equipment_load_rate()` | 设备负荷率 | A3 |
| `calc_vpp_response_potential()` | VPP响应潜力 | A4 |
| `calc_load_curve_analysis()` | 负荷曲线分析 | A5 |
| `calc_equipment_efficiency_benchmark()` | 能效对标 | B1 |

## API路由示例

```python
@router.post("/proposals/generate/{template_id}")
async def generate(template_id: str, db: Session = Depends(get_db)):
    return TemplateGenerator(db).generate_proposal(template_id, 30)

@router.get("/proposals/{id}")
async def get(id: int, db: Session = Depends(get_db)):
    return db.query(EnergySavingProposal).filter_by(id=id).first()

@router.put("/measures/{id}/select")
async def select(id: int, selected: bool, db: Session = Depends(get_db)):
    m = db.query(ProposalMeasure).get(id)
    m.is_selected = selected
    db.commit()
```

## 测试命令

```bash
# 运行所有测试
pytest tests/services/test_template_generator.py -v

# 测试特定模板
pytest tests/services/test_template_generator.py::TestTemplateGenerator::test_generate_a1_peak_valley_proposal -v
```

## 文件位置

| 文件 | 路径 |
|------|------|
| 服务文件 | `app/services/template_generator.py` |
| 测试文件 | `tests/services/test_template_generator.py` |
| 使用文档 | `docs/template_generator_usage.md` |
| 演示脚本 | `examples/template_generator_demo.py` |

## 注意事项

⚠️ **数据依赖**: 需要 EnergyDaily、DemandHistory 等表有数据
⚠️ **方案编号**: 同一天生成的同类型方案编号会递增
⚠️ **收益计算**: 基于实际数据，数据不足时使用默认值
⚠️ **投资金额**: 仅B类方案有投资，A类方案投资为0

---
**版本**: 1.0 | **更新**: 2026-01-25
