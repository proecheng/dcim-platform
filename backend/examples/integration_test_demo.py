"""
集成测试脚本 - 演示 TemplateGenerator 在真实场景中的使用

这个脚本模拟了一个完整的业务流程：
1. 管理员生成所有类型的节能方案
2. 展示方案列表给用户
3. 用户查看方案详情并选择措施
4. 计算预期收益
5. 生成实施报告
"""
import sys
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from decimal import Decimal
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.services.template_generator import TemplateGenerator
from app.models.energy import EnergySavingProposal, ProposalMeasure


def print_header(title: str):
    """打印标题"""
    print("\n" + "="*80)
    print(f"  {title}")
    print("="*80 + "\n")


def print_proposal_summary(proposal: EnergySavingProposal):
    """打印方案摘要"""
    print(f"📋 方案编号: {proposal.proposal_code}")
    print(f"📝 方案名称: {proposal.template_name}")
    print(f"📊 方案类型: {'无需投资' if proposal.proposal_type == 'A' else '需要投资'}")
    print(f"💰 总年收益: {proposal.total_benefit} 万元")
    if proposal.total_investment > 0:
        print(f"💸 总投资: {proposal.total_investment} 万元")
        payback = proposal.total_investment / proposal.total_benefit if proposal.total_benefit > 0 else 0
        print(f"⏱️  投资回收期: {float(payback):.1f} 年")
    print(f"📅 分析周期: {proposal.analysis_start_date} 至 {proposal.analysis_end_date}")
    print(f"🔧 措施数量: {len(proposal.measures)} 项")
    print()


def simulate_user_selection(proposal: EnergySavingProposal) -> list:
    """模拟用户选择措施（自动选择收益最高的2个）"""
    # 按收益排序
    sorted_measures = sorted(
        proposal.measures,
        key=lambda m: m.annual_benefit,
        reverse=True
    )

    # 选择前2个
    selected = []
    for i, measure in enumerate(sorted_measures):
        if i < 2:  # 选择前2个
            measure.is_selected = True
            selected.append(measure)
        else:
            measure.is_selected = False

    return selected


def generate_implementation_report(proposals: list):
    """生成实施报告"""
    print_header("节能方案实施报告")

    # 统计
    total_proposals = len(proposals)
    a_type_count = sum(1 for p in proposals if p.proposal_type == 'A')
    b_type_count = sum(1 for p in proposals if p.proposal_type == 'B')

    selected_measures_count = sum(
        sum(1 for m in p.measures if m.is_selected)
        for p in proposals
    )

    total_benefit = sum(
        sum(m.annual_benefit for m in p.measures if m.is_selected)
        for p in proposals
    )

    total_investment = sum(
        sum(m.investment for m in p.measures if m.is_selected)
        for p in proposals
    )

    print(f"📊 方案总数: {total_proposals}")
    print(f"   - A类方案（无需投资）: {a_type_count}")
    print(f"   - B类方案（需要投资）: {b_type_count}")
    print(f"\n🔧 选中措施总数: {selected_measures_count}")
    print(f"\n💰 预期年收益: {total_benefit} 万元")
    print(f"💸 所需投资: {total_investment} 万元")

    if total_investment > 0 and total_benefit > 0:
        overall_payback = total_investment / total_benefit
        print(f"⏱️  综合投资回收期: {float(overall_payback):.1f} 年")

    print("\n" + "-"*80)
    print("各方案选中措施明细:")
    print("-"*80 + "\n")

    for proposal in proposals:
        selected_measures = [m for m in proposal.measures if m.is_selected]
        if selected_measures:
            print(f"【{proposal.template_name}】")
            for measure in selected_measures:
                print(f"  ✓ {measure.regulation_object}")
                print(f"    年收益: {measure.annual_benefit} 万元", end="")
                if measure.investment > 0:
                    print(f" | 投资: {measure.investment} 万元", end="")
                print()
            print()


def main():
    """主流程"""
    print_header("节能方案模板生成器 - 集成测试")

    # 注意：这里使用 SQLite 内存数据库作为演示
    # 实际使用时应该连接到真实数据库
    print("⚠️  注意: 本演示使用内存数据库，不会持久化数据")
    print("⚠️  实际使用时需要连接到真实数据库并准备好基础数据\n")

    # 创建内存数据库（仅用于演示）
    # engine = create_engine("sqlite:///:memory:")
    # Session = sessionmaker(bind=engine)
    # db = Session()

    # 由于没有真实数据库连接，这里仅演示代码流程
    print("="*80)
    print("📝 演示流程（代码示例）")
    print("="*80 + "\n")

    print("""
# ==================== 步骤1: 创建生成器实例 ====================

from app.services.template_generator import TemplateGenerator
from sqlalchemy.orm import Session

# 获取数据库会话
db_session = get_db_session()

# 创建生成器
generator = TemplateGenerator(db_session)
print("✓ 生成器已创建")


# ==================== 步骤2: 批量生成所有方案 ====================

template_ids = ["A1", "A2", "A3", "A4", "A5", "B1"]
proposals = []

for template_id in template_ids:
    try:
        print(f"正在生成 {template_id} 方案...")
        proposal = generator.generate_proposal(template_id, analysis_days=30)
        proposals.append(proposal)
        print(f"✓ {proposal.template_name} 生成成功")
    except Exception as e:
        print(f"✗ {template_id} 生成失败: {e}")

# 保存到数据库
for proposal in proposals:
    db_session.add(proposal)
db_session.commit()

print(f"\\n✓ 成功生成 {len(proposals)} 个方案")


# ==================== 步骤3: 展示方案列表 ====================

print("\\n【生成的方案列表】\\n")

for i, proposal in enumerate(proposals, 1):
    print(f"{i}. {proposal.template_name}")
    print(f"   编号: {proposal.proposal_code}")
    print(f"   年收益: {proposal.total_benefit} 万元")
    if proposal.total_investment > 0:
        print(f"   投资: {proposal.total_investment} 万元")
    print()


# ==================== 步骤4: 查看A1方案详情 ====================

a1_proposal = proposals[0]  # 假设第一个是A1

print("\\n【方案详情 - A1 峰谷套利优化方案】\\n")
print(f"方案编号: {a1_proposal.proposal_code}")
print(f"总收益: {a1_proposal.total_benefit} 万元/年")

print("\\n当前状况:")
for key, value in a1_proposal.current_situation.items():
    print(f"  • {key}: {value}")

print("\\n措施清单:")
for i, measure in enumerate(a1_proposal.measures, 1):
    print(f"\\n措施{i}: {measure.regulation_object}")
    print(f"  年收益: {measure.annual_benefit} 万元")
    print(f"  投资: {measure.investment} 万元")

    print("\\n  当前状态:")
    for k, v in measure.current_state.items():
        print(f"    - {k}: {v}")

    print("\\n  目标状态:")
    for k, v in measure.target_state.items():
        print(f"    - {k}: {v}")

    print("\\n  计算公式:")
    for line in measure.calculation_formula.split('\\n')[:5]:  # 只显示前5行
        if line.strip():
            print(f"    {line}")


# ==================== 步骤5: 用户选择措施 ====================

print("\\n【用户选择措施】\\n")

# 方式1: 手动选择
a1_proposal.measures[0].is_selected = True   # 选择措施1
a1_proposal.measures[1].is_selected = False  # 不选择措施2
a1_proposal.measures[2].is_selected = True   # 选择措施3

# 方式2: 批量选择（按收益排序，选择最高的N个）
def auto_select_top_measures(proposal, top_n=2):
    sorted_measures = sorted(
        proposal.measures,
        key=lambda m: m.annual_benefit,
        reverse=True
    )
    for i, measure in enumerate(sorted_measures):
        measure.is_selected = (i < top_n)

# 对所有方案自动选择最高收益的2个措施
for proposal in proposals:
    auto_select_top_measures(proposal, top_n=2)
    db_session.commit()

print("✓ 已为所有方案选择收益最高的2个措施")


# ==================== 步骤6: 计算实际预期收益 ====================

print("\\n【预期收益计算】\\n")

for proposal in proposals:
    selected_measures = [m for m in proposal.measures if m.is_selected]
    selected_benefit = sum(m.annual_benefit for m in selected_measures)
    selected_investment = sum(m.investment for m in selected_measures)

    print(f"{proposal.template_name}:")
    print(f"  选中措施: {len(selected_measures)}/3")
    print(f"  预期年收益: {selected_benefit} 万元")
    if selected_investment > 0:
        print(f"  所需投资: {selected_investment} 万元")
    print()


# ==================== 步骤7: 生成实施报告 ====================

total_selected_benefit = sum(
    sum(m.annual_benefit for m in p.measures if m.is_selected)
    for p in proposals
)

total_selected_investment = sum(
    sum(m.investment for m in p.measures if m.is_selected)
    for p in proposals
)

print("\\n【总体实施报告】\\n")
print(f"方案总数: {len(proposals)}")
print(f"选中措施总数: {sum(sum(1 for m in p.measures if m.is_selected) for p in proposals)}")
print(f"预期年收益: {total_selected_benefit} 万元")
print(f"所需投资: {total_selected_investment} 万元")

if total_selected_investment > 0:
    payback = total_selected_investment / total_selected_benefit
    print(f"综合投资回收期: {float(payback):.1f} 年")


# ==================== 步骤8: API集成示例 ====================

print("\\n【API集成示例】\\n")

# FastAPI 路由
from fastapi import APIRouter, Depends, HTTPException
from app.core.database import get_db

router = APIRouter()

@router.post("/api/v1/proposals/generate")
async def generate_all_proposals(
    analysis_days: int = 30,
    db: Session = Depends(get_db)
):
    '''批量生成所有类型方案'''
    generator = TemplateGenerator(db)
    template_ids = ["A1", "A2", "A3", "A4", "A5", "B1"]

    results = []
    for template_id in template_ids:
        try:
            proposal = generator.generate_proposal(template_id, analysis_days)
            db.add(proposal)
            results.append({
                "template_id": template_id,
                "proposal_code": proposal.proposal_code,
                "total_benefit": float(proposal.total_benefit),
                "status": "success"
            })
        except Exception as e:
            results.append({
                "template_id": template_id,
                "error": str(e),
                "status": "failed"
            })

    db.commit()

    return {
        "code": 200,
        "message": f"成功生成 {len([r for r in results if r['status'] == 'success'])} 个方案",
        "data": results
    }


@router.get("/api/v1/proposals/{proposal_id}")
async def get_proposal_detail(
    proposal_id: int,
    db: Session = Depends(get_db)
):
    '''获取方案详情'''
    proposal = db.query(EnergySavingProposal).filter(
        EnergySavingProposal.id == proposal_id
    ).first()

    if not proposal:
        raise HTTPException(status_code=404, detail="方案不存在")

    return {
        "code": 200,
        "data": {
            "proposal_code": proposal.proposal_code,
            "template_name": proposal.template_name,
            "total_benefit": float(proposal.total_benefit),
            "total_investment": float(proposal.total_investment),
            "current_situation": proposal.current_situation,
            "measures": [
                {
                    "id": m.id,
                    "regulation_object": m.regulation_object,
                    "annual_benefit": float(m.annual_benefit),
                    "investment": float(m.investment),
                    "is_selected": m.is_selected,
                    "current_state": m.current_state,
                    "target_state": m.target_state
                }
                for m in proposal.measures
            ]
        }
    }


@router.put("/api/v1/measures/{measure_id}/select")
async def toggle_measure_selection(
    measure_id: int,
    is_selected: bool,
    db: Session = Depends(get_db)
):
    '''切换措施选择状态'''
    measure = db.query(ProposalMeasure).filter(
        ProposalMeasure.id == measure_id
    ).first()

    if not measure:
        raise HTTPException(status_code=404, detail="措施不存在")

    measure.is_selected = is_selected
    db.commit()

    return {
        "code": 200,
        "message": "更新成功",
        "data": {
            "measure_id": measure.id,
            "is_selected": measure.is_selected
        }
    }


print("✓ API路由定义完成")
    """)

    print("\n" + "="*80)
    print("✓ 集成测试演示完成")
    print("="*80 + "\n")

    print("后续步骤:")
    print("1. 准备真实数据库和基础数据")
    print("2. 运行单元测试验证功能")
    print("3. 集成到API路由")
    print("4. 添加前端界面展示")
    print("5. 根据实际业务调整参数和逻辑")


if __name__ == "__main__":
    main()
