import pytest
from fastapi.testclient import TestClient

class TestProposalWorkflow:
    """测试完整工作流: 生成 → 接受 → 执行 → 监控"""

    def test_complete_workflow(self, client: TestClient, db):
        # 1. 生成方案
        response = client.post("/api/v1/proposals/generate", json={
            "template_id": "A1",
            "analysis_days": 30
        })
        assert response.status_code == 200
        proposal = response.json()
        proposal_id = proposal["id"]

        # 2. 接受方案
        measure_ids = [m["id"] for m in proposal["measures"][:2]]
        response = client.post(f"/api/v1/proposals/{proposal_id}/accept", json={
            "selected_measure_ids": measure_ids
        })
        assert response.status_code == 200
        assert response.json()["status"] == "accepted"

        # 3. 执行方案
        response = client.post(f"/api/v1/proposals/{proposal_id}/execute")
        assert response.status_code == 200

        # 4. 获取监控数据
        response = client.get(f"/api/v1/proposals/{proposal_id}/monitoring")
        assert response.status_code == 200
        monitoring = response.json()
        assert monitoring["proposal_id"] == proposal_id
