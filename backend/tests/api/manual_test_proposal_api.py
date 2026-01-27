"""
手动测试 Proposal API 端点
演示如何使用各个 API 端点
"""
from app.api.v1.proposal import (
    generate_proposal,
    get_proposal,
    get_proposals,
    accept_proposal,
    execute_proposal,
    get_proposal_monitoring,
    delete_proposal
)
from app.schemas.proposal_schema import ProposalCreate, MeasureAcceptRequest
from app.core.database import SessionLocal


def test_api_endpoints():
    """测试所有 API 端点"""
    db = SessionLocal()

    try:
        print("=" * 60)
        print("测试 Proposal API 端点")
        print("=" * 60)

        # 1. 生成方案
        print("\n1. 生成 A1 峰谷套利方案...")
        proposal_request = ProposalCreate(
            template_id="A1",
            analysis_days=30
        )

        # 注意: 这里不能直接调用异步函数，需要使用同步版本或者实际的HTTP请求
        print("   提示: 需要通过 HTTP 请求测试")
        print(f"   请求数据: {proposal_request.dict()}")

        # 2. 显示 API 端点列表
        print("\n2. API 端点列表:")
        print("   POST   /api/v1/proposals/generate        - 生成节能方案")
        print("   GET    /api/v1/proposals/{proposal_id}   - 获取方案详情")
        print("   GET    /api/v1/proposals/                - 获取方案列表")
        print("   POST   /api/v1/proposals/{proposal_id}/accept  - 接受方案")
        print("   POST   /api/v1/proposals/{proposal_id}/execute - 执行方案")
        print("   GET    /api/v1/proposals/{proposal_id}/monitoring - 获取监控数据")
        print("   DELETE /api/v1/proposals/{proposal_id}   - 删除方案")

        # 3. 测试数据准备示例
        print("\n3. 测试数据示例:")
        print("   生成方案请求:")
        print(f"     {proposal_request.dict()}")

        accept_request = MeasureAcceptRequest(
            selected_measure_ids=[1, 2, 3]
        )
        print("\n   接受方案请求:")
        print(f"     {accept_request.dict()}")

        print("\n4. 使用建议:")
        print("   - 启动 FastAPI 应用: uvicorn app.main:app --reload")
        print("   - 访问 API 文档: http://localhost:8000/docs")
        print("   - 在 Swagger UI 中测试所有端点")

        print("\n5. 测试流程:")
        print("   步骤 1: POST /api/v1/proposals/generate")
        print("           生成一个新方案，获得 proposal_id")
        print("   步骤 2: GET /api/v1/proposals/{proposal_id}")
        print("           查看方案详情和措施列表")
        print("   步骤 3: POST /api/v1/proposals/{proposal_id}/accept")
        print("           选择要实施的措施")
        print("   步骤 4: POST /api/v1/proposals/{proposal_id}/execute")
        print("           启动方案执行（需要任务6）")
        print("   步骤 5: GET /api/v1/proposals/{proposal_id}/monitoring")
        print("           查看执行监控数据")

        print("\n" + "=" * 60)
        print("API 端点配置完成！")
        print("=" * 60)

    finally:
        db.close()


if __name__ == "__main__":
    test_api_endpoints()
