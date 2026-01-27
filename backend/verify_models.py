"""
验证节能方案模型是否正常工作
"""
import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

from app.models.energy import EnergySavingProposal, ProposalMeasure, MeasureExecutionLog

print("=" * 50)
print("验证节能方案模型")
print("=" * 50)

# 1. 创建方案对象
proposal = EnergySavingProposal(
    proposal_code="A1-20260124-001",
    proposal_type="A",
    template_id="A1",
    template_name="峰谷套利优化方案",
    total_benefit=150.0,
    status="pending"
)
print(f"\n[OK] 创建方案: {proposal.proposal_code} - {proposal.template_name}")

# 2. 创建措施对象
measure1 = ProposalMeasure(
    measure_code="A1-001-M001",
    regulation_object="空压机系统",
    regulation_description="降低运行压力至0.6MPa",
    annual_benefit=50.0,
    is_selected=False,
    execution_status="pending"
)
print(f"[OK] 创建措施1: {measure1.measure_code} - {measure1.regulation_object}")

measure2 = ProposalMeasure(
    measure_code="A1-001-M002",
    regulation_object="中央空调",
    regulation_description="供水温度调高1℃",
    annual_benefit=100.0,
    is_selected=False,
    execution_status="pending"
)
print(f"[OK] 创建措施2: {measure2.measure_code} - {measure2.regulation_object}")

# 3. 建立关系
proposal.measures.append(measure1)
proposal.measures.append(measure2)
print(f"\n[OK] 方案包含 {len(proposal.measures)} 个措施")

# 4. 创建执行日志
log = MeasureExecutionLog(
    power_before=100.0,
    power_after=80.0,
    power_saved=20.0,
    expected_power_saved=18.0,
    result="success",
    result_message="措施执行成功"
)
measure1.execution_logs.append(log)
print(f"[OK] 措施1添加执行日志: 节省功率 {log.power_saved} kW")

# 5. 验证数据结构
print("\n" + "=" * 50)
print("数据结构验证")
print("=" * 50)
print(f"方案类型: {proposal.proposal_type}")
print(f"模板ID: {proposal.template_id}")
print(f"总收益: {proposal.total_benefit} 万元/年")
print(f"状态: {proposal.status}")
print(f"\n措施列表:")
for i, m in enumerate(proposal.measures, 1):
    print(f"  {i}. {m.regulation_object} - 年收益: {m.annual_benefit} 万元")
print(f"\n执行日志数量: {len(measure1.execution_logs)}")
print(f"执行结果: {measure1.execution_logs[0].result}")

print("\n" + "=" * 50)
print("所有验证通过！")
print("=" * 50)
