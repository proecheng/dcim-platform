"""
集成测试: 方案完整工作流
"""
import pytest
from httpx import AsyncClient


class TestProposalWorkflow:
    """测试完整工作流: 生成 → 接受 → 执行 → 监控"""

    @pytest.mark.skip(reason="需要完整的能源数据种子数据，暂跳过")
    async def test_complete_workflow(self, client: AsyncClient, admin_user):
        """端到端工作流测试（需要认证）"""
        _, token = admin_user
        headers = {"Authorization": f"Bearer {token}"}

        # 1. 生成方案
        response = await client.post("/api/v1/proposals/generate", json={
            "template_id": "A1",
            "analysis_days": 30
        }, headers=headers)
        assert response.status_code == 200
        proposal = response.json()
        proposal_id = proposal["id"]

        # 2. 接受方案
        measure_ids = [m["id"] for m in proposal["measures"][:2]]
        response = await client.post(f"/api/v1/proposals/{proposal_id}/accept", json={
            "selected_measure_ids": measure_ids
        }, headers=headers)
        assert response.status_code == 200
        assert response.json()["status"] == "accepted"

        # 3. 执行方案
        response = await client.post(f"/api/v1/proposals/{proposal_id}/execute",
                                     headers=headers)
        assert response.status_code == 200

        # 4. 获取监控数据
        response = await client.get(f"/api/v1/proposals/{proposal_id}/monitoring",
                                    headers=headers)
        assert response.status_code == 200
        monitoring = response.json()
        assert monitoring["proposal_id"] == proposal_id
