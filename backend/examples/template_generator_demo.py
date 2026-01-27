"""
模板生成器使用示例
演示如何使用 TemplateGenerator 生成6种类型的节能方案
"""
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.services.template_generator import TemplateGenerator
from app.core.database import Base
import json


def print_proposal_summary(proposal):
    """打印方案摘要"""
    print("\n" + "="*80)
    print(f"方案编号: {proposal.proposal_code}")
    print(f"方案类型: {proposal.proposal_type} - {proposal.template_name}")
    print(f"分析周期: {proposal.analysis_start_date} 至 {proposal.analysis_end_date}")
    print(f"总收益: {proposal.total_benefit} 万元/年")
    print(f"总投资: {proposal.total_investment} 万元")
    print("="*80)

    print("\n【当前状况】")
    for key, value in proposal.current_situation.items():
        print(f"  - {key}: {value}")

    print(f"\n【措施清单】（共{len(proposal.measures)}项）")
    for i, measure in enumerate(proposal.measures, 1):
        print(f"\n  措施{i}: {measure.regulation_object}")
        print(f"    编号: {measure.measure_code}")
        print(f"    描述: {measure.regulation_description}")
        print(f"    年收益: {measure.annual_benefit} 万元")
        print(f"    投资: {measure.investment} 万元")

        print(f"\n    当前状态:")
        for key, value in measure.current_state.items():
            print(f"      • {key}: {value}")

        print(f"\n    目标状态:")
        for key, value in measure.target_state.items():
            print(f"      • {key}: {value}")

        print(f"\n    计算公式:")
        for line in measure.calculation_formula.split('\n'):
            if line.strip():
                print(f"      {line}")


def demo_template_generation():
    """演示模板生成"""
    # 注意：这是一个演示脚本，实际使用时需要配置数据库连接
    print("""
╔══════════════════════════════════════════════════════════════╗
║          节能方案模板生成器 - 使用示例                       ║
╚══════════════════════════════════════════════════════════════╝

本演示展示如何使用 TemplateGenerator 生成6种类型的节能方案：

A1 - 峰谷套利优化方案（无需投资）
A2 - 需量控制方案（无需投资）
A3 - 设备运行优化方案（无需投资）
A4 - VPP需求响应方案（无需投资）
A5 - 负荷调度优化方案（无需投资）
B1 - 设备改造升级方案（需要投资）

每个方案包含3个独立的措施，用户可以选择性实施。
    """)

    # 实际使用示例代码
    print("""
【使用方法】

from app.services.template_generator import TemplateGenerator
from sqlalchemy.orm import Session

# 1. 创建生成器实例（传入数据库会话）
generator = TemplateGenerator(db_session)

# 2. 生成A1方案（峰谷套利优化）
proposal_a1 = generator.generate_proposal("A1", analysis_days=30)

# 3. 访问方案信息
print(f"方案编号: {proposal_a1.proposal_code}")
print(f"总收益: {proposal_a1.total_benefit} 万元/年")
print(f"措施数量: {len(proposal_a1.measures)}")

# 4. 遍历措施
for measure in proposal_a1.measures:
    print(f"措施: {measure.regulation_object}")
    print(f"年收益: {measure.annual_benefit} 万元")
    print(f"当前状态: {measure.current_state}")
    print(f"目标状态: {measure.target_state}")

# 5. 保存到数据库
db_session.add(proposal_a1)
db_session.commit()

# 6. 生成其他类型方案
proposal_a2 = generator.generate_proposal("A2", analysis_days=30)  # 需量控制
proposal_a3 = generator.generate_proposal("A3", analysis_days=30)  # 设备优化
proposal_a4 = generator.generate_proposal("A4", analysis_days=30)  # VPP响应
proposal_a5 = generator.generate_proposal("A5", analysis_days=30)  # 负荷调度
proposal_b1 = generator.generate_proposal("B1", analysis_days=30)  # 设备改造
    """)


def demo_measure_selection():
    """演示措施选择流程"""
    print("""
【措施选择流程】

# 1. 生成方案
proposal = generator.generate_proposal("A1", analysis_days=30)

# 2. 展示给用户选择
for measure in proposal.measures:
    # 用户选择是否实施该措施
    user_choice = input(f"是否实施'{measure.regulation_object}'? (y/n): ")

    if user_choice.lower() == 'y':
        measure.is_selected = True
        print(f"  已选择，年收益: {measure.annual_benefit} 万元")
    else:
        measure.is_selected = False
        print(f"  未选择")

# 3. 计算选中措施的总收益
selected_benefit = sum(
    m.annual_benefit for m in proposal.measures if m.is_selected
)
print(f"\\n选中措施总收益: {selected_benefit} 万元/年")

# 4. 保存方案和选择结果
db_session.add(proposal)
db_session.commit()
    """)


def demo_api_integration():
    """演示API集成示例"""
    print("""
【API集成示例】

# 在路由文件中 (app/api/v1/endpoints/proposals.py)

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.services.template_generator import TemplateGenerator
from app.core.database import get_db

router = APIRouter()

@router.post("/proposals/generate/{template_id}")
async def generate_proposal(
    template_id: str,
    analysis_days: int = 30,
    db: Session = Depends(get_db)
):
    '''生成节能方案'''
    try:
        generator = TemplateGenerator(db)
        proposal = generator.generate_proposal(template_id, analysis_days)

        # 保存到数据库
        db.add(proposal)
        db.commit()
        db.refresh(proposal)

        return {
            "code": 200,
            "message": "方案生成成功",
            "data": {
                "proposal_id": proposal.id,
                "proposal_code": proposal.proposal_code,
                "total_benefit": float(proposal.total_benefit),
                "total_investment": float(proposal.total_investment),
                "measures_count": len(proposal.measures)
            }
        }
    except ValueError as e:
        return {"code": 400, "message": str(e)}
    except Exception as e:
        return {"code": 500, "message": f"生成失败: {str(e)}"}


@router.get("/proposals/{proposal_id}")
async def get_proposal(
    proposal_id: int,
    db: Session = Depends(get_db)
):
    '''获取方案详情'''
    proposal = db.query(EnergySavingProposal).filter(
        EnergySavingProposal.id == proposal_id
    ).first()

    if not proposal:
        return {"code": 404, "message": "方案不存在"}

    return {
        "code": 200,
        "data": {
            "proposal_code": proposal.proposal_code,
            "template_name": proposal.template_name,
            "total_benefit": float(proposal.total_benefit),
            "current_situation": proposal.current_situation,
            "measures": [
                {
                    "measure_code": m.measure_code,
                    "regulation_object": m.regulation_object,
                    "annual_benefit": float(m.annual_benefit),
                    "investment": float(m.investment),
                    "current_state": m.current_state,
                    "target_state": m.target_state,
                    "calculation_formula": m.calculation_formula,
                    "is_selected": m.is_selected
                }
                for m in proposal.measures
            ]
        }
    }


@router.put("/proposals/{proposal_id}/measures/{measure_id}/select")
async def select_measure(
    proposal_id: int,
    measure_id: int,
    is_selected: bool,
    db: Session = Depends(get_db)
):
    '''用户选择/取消选择某个措施'''
    measure = db.query(ProposalMeasure).filter(
        ProposalMeasure.id == measure_id,
        ProposalMeasure.proposal_id == proposal_id
    ).first()

    if not measure:
        return {"code": 404, "message": "措施不存在"}

    measure.is_selected = is_selected
    db.commit()

    return {
        "code": 200,
        "message": "更新成功",
        "data": {
            "measure_code": measure.measure_code,
            "is_selected": measure.is_selected
        }
    }
    """)


def demo_batch_generation():
    """演示批量生成"""
    print("""
【批量生成所有类型方案】

from app.services.template_generator import TemplateGenerator

def generate_all_proposals(db: Session, analysis_days: int = 30):
    '''批量生成所有6种类型的方案'''
    generator = TemplateGenerator(db)
    template_ids = ["A1", "A2", "A3", "A4", "A5", "B1"]

    proposals = []
    for template_id in template_ids:
        try:
            proposal = generator.generate_proposal(template_id, analysis_days)
            db.add(proposal)
            proposals.append(proposal)
            print(f"✓ {template_id} - {proposal.template_name} 生成成功")
        except Exception as e:
            print(f"✗ {template_id} 生成失败: {e}")

    db.commit()
    return proposals


# 使用示例
proposals = generate_all_proposals(db_session)

# 汇总统计
total_benefit_a = sum(
    p.total_benefit for p in proposals if p.proposal_type == "A"
)
total_benefit_b = sum(
    p.total_benefit for p in proposals if p.proposal_type == "B"
)
total_investment_b = sum(
    p.total_investment for p in proposals if p.proposal_type == "B"
)

print(f"\\nA类方案（无需投资）总收益: {total_benefit_a} 万元/年")
print(f"B类方案（需要投资）总收益: {total_benefit_b} 万元/年")
print(f"B类方案总投资: {total_investment_b} 万元")
print(f"B类方案投资回收期: {total_investment_b / total_benefit_b if total_benefit_b > 0 else 0:.1f} 年")
    """)


if __name__ == "__main__":
    demo_template_generation()
    print("\n" + "="*80 + "\n")
    demo_measure_selection()
    print("\n" + "="*80 + "\n")
    demo_api_integration()
    print("\n" + "="*80 + "\n")
    demo_batch_generation()
