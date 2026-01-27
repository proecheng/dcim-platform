"""
初始化节能方案表并生成示例数据
运行: python scripts/init_proposal_tables.py
"""
import sys
import asyncio
import io
sys.path.insert(0, 'D:\\mytest1\\backend')
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

from app.core.database import engine, async_session, Base
from app.models.energy import EnergySavingProposal, ProposalMeasure, MeasureExecutionLog
from datetime import datetime, timedelta
from sqlalchemy import select

async def init_tables():
    """创建数据库表"""
    print("正在创建数据库表...")
    # 导入所有模型确保它们被注册
    from app.models import energy
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print("[OK] 数据库表创建完成")

async def generate_sample_proposals():
    """生成6种模板的示例方案（简化版）"""
    print("\n正在生成示例节能方案...")
    print("注意: 使用简化数据生成。完整数据生成请通过API调用 POST /api/v1/proposals/generate")
    async with async_session() as db:
        try:
            # 模板配置
            templates_config = {
                "A1": {"name": "峰谷套利优化方案", "type": "A", "benefit": 58.5},
                "A2": {"name": "需量控制方案", "type": "A", "benefit": 42.3},
                "A3": {"name": "设备运行优化方案", "type": "A", "benefit": 35.7},
                "A4": {"name": "VPP需求响应方案", "type": "A", "benefit": 28.9},
                "A5": {"name": "负荷调度优化方案", "type": "A", "benefit": 45.2},
                "B1": {"name": "设备改造升级方案", "type": "B", "benefit": 125.6}
            }

            for template_id, config in templates_config.items():
                try:
                    # 生成方案编号
                    proposal_code = f"ESP-{template_id}-{datetime.now().strftime('%Y%m%d%H%M%S')}"

                    # 创建方案
                    proposal = EnergySavingProposal(
                        proposal_code=proposal_code,
                        proposal_type=config["type"],
                        template_id=template_id,
                        template_name=config["name"],
                        total_benefit=config["benefit"],
                        total_investment=0 if config["type"] == "A" else 280.0,
                        current_situation={},
                        analysis_start_date=(datetime.now() - timedelta(days=30)).date(),
                        analysis_end_date=datetime.now().date(),
                        status="pending"
                    )

                    db.add(proposal)
                    await db.flush()  # 获取proposal.id

                    # 创建示例措施（每个方案3个措施）
                    for i in range(1, 4):
                        measure = ProposalMeasure(
                            proposal_id=proposal.id,
                            measure_code=f"{proposal_code}-M{i:03d}",
                            regulation_object=f"{config['name']}措施{i}",
                            regulation_description=f"示例措施{i}的描述",
                            current_state={},
                            target_state={},
                            calculation_formula="示例公式",
                            calculation_basis="示例依据",
                            annual_benefit=config["benefit"] / 3,
                            investment=0 if config["type"] == "A" else 280.0 / 3,
                            is_selected=False,
                            execution_status="pending"
                        )
                        db.add(measure)

                    await db.commit()
                    print(f"  [OK] {template_id}: {config['name']} - 预计收益 {config['benefit']:.2f} 万元/年")

                except Exception as e:
                    print(f"  [!] {template_id}: 生成失败 - {str(e)}")
                    await db.rollback()
                    import traceback
                    traceback.print_exc()

            print(f"\n[OK] 示例方案生成完成")
            print("提示: 这些是简化的示例数据，完整方案请通过API生成")

        finally:
            await db.close()

async def verify_deployment():
    """验证部署"""
    print("\n正在验证部署...")
    async with async_session() as db:
        try:
            # Count proposals with eager loading
            from sqlalchemy.orm import selectinload
            result = await db.execute(
                select(EnergySavingProposal).options(selectinload(EnergySavingProposal.measures))
            )
            proposals = result.scalars().all()
            count = len(proposals)
            print(f"  - 方案总数: {count}")

            for proposal in proposals:
                measures_count = len(proposal.measures)
                print(f"  - {proposal.proposal_code}: {proposal.template_name} ({measures_count} 个措施)")

            print("\n[OK] 部署验证完成！")

        finally:
            await db.close()

async def main():
    print("=" * 50)
    print("节能方案系统部署初始化")
    print("=" * 50)

    await init_tables()
    await generate_sample_proposals()
    await verify_deployment()

    print("\n" + "=" * 50)
    print("部署完成！API 可在以下地址访问：")
    print("  GET  /api/v1/proposals/           - 获取方案列表")
    print("  POST /api/v1/proposals/generate   - 生成新方案")
    print("=" * 50)

if __name__ == "__main__":
    asyncio.run(main())
