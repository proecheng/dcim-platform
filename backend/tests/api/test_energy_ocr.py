"""
电费单 OCR API 端点集成测试

覆盖:
  - POST /api/v1/energy/ocr/bill — 正常上传（mock 模式）
  - POST /api/v1/energy/ocr/bill — 不支持的文件格式
  - POST /api/v1/energy/ocr/bill — 未认证请求
"""
import pytest
from io import BytesIO
from tests.conftest import auth_headers


class TestOcrBillEndpoint:
    """电费单 OCR 识别 API 测试"""

    @pytest.mark.asyncio
    async def test_ocr_bill_success_mock_mode(self, client, admin_user, async_db):
        """上传 JPG 文件，mock 模式应返回五时段电价数据"""
        _, token = admin_user
        # 构造 multipart 文件上传
        files = {"file": ("bill.jpg", b"fake image content", "image/jpeg")}
        resp = await client.post(
            "/api/v1/energy/ocr/bill",
            files=files,
            headers=auth_headers(token),
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["code"] == 200
        assert body["message"] == "识别成功"
        data = body["data"]
        assert data["success"] is True
        assert data["provider"] == "国家电网"
        assert len(data["items"]) == 5

    @pytest.mark.asyncio
    async def test_ocr_bill_png_accepted(self, client, admin_user, async_db):
        """PNG 格式也应被接受"""
        _, token = admin_user
        files = {"file": ("bill.png", b"fake png data", "image/png")}
        resp = await client.post(
            "/api/v1/energy/ocr/bill",
            files=files,
            headers=auth_headers(token),
        )
        assert resp.status_code == 200
        assert resp.json()["data"]["success"] is True

    @pytest.mark.asyncio
    async def test_ocr_bill_invalid_format(self, client, admin_user, async_db):
        """不支持的文件格式应返回错误信息"""
        _, token = admin_user
        files = {"file": ("bill.txt", b"text content", "text/plain")}
        resp = await client.post(
            "/api/v1/energy/ocr/bill",
            files=files,
            headers=auth_headers(token),
        )
        assert resp.status_code == 200
        body = resp.json()
        data = body["data"]
        assert data["success"] is False
        assert "不支持的文件格式" in (data.get("error_message") or body.get("message", ""))

    @pytest.mark.asyncio
    async def test_ocr_bill_no_auth(self, client, async_db):
        """未认证请求应返回 401"""
        files = {"file": ("bill.jpg", b"fake", "image/jpeg")}
        resp = await client.post("/api/v1/energy/ocr/bill", files=files)
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_ocr_bill_response_item_fields(self, client, admin_user, async_db):
        """验证返回的电价条目包含所有必要字段"""
        _, token = admin_user
        files = {"file": ("bill.jpg", b"fake", "image/jpeg")}
        resp = await client.post(
            "/api/v1/energy/ocr/bill",
            files=files,
            headers=auth_headers(token),
        )
        assert resp.status_code == 200
        items = resp.json()["data"]["items"]
        assert len(items) > 0
        item = items[0]
        # 验证字段完整性
        assert "pricing_name" in item
        assert "period_type" in item
        assert "start_time" in item
        assert "end_time" in item
        assert "price" in item
        assert "confidence" in item
        assert "effective_date" in item
