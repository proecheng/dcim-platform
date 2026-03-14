"""Story 26.10: HMAC 密钥管理服务测试"""

import hashlib
import hmac as hmac_lib
import json
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.diagnosis.hmac_key_service import HMACKeyManagementService


# ============================================================
# Fixtures
# ============================================================


@pytest.fixture
def service():
    return HMACKeyManagementService()


def _make_version(id_, tree_id, version_number, status, snapshot, hmac_signature=None):
    """创建模拟 FaultTreeVersion 对象"""
    v = MagicMock()
    v.id = id_
    v.tree_id = tree_id
    v.version_number = version_number
    v.status = status
    v.snapshot = snapshot
    v.hmac_signature = hmac_signature
    return v


def _make_rotation_log(
    id_,
    rotated_at,
    rotated_by,
    versions_resigned,
    resigned_version_ids,
    new_key_prefix,
    old_key_prefix,
    status,
    error_detail=None,
):
    """创建模拟 HMACKeyRotationLog 对象"""
    log = MagicMock()
    log.id = id_
    log.rotated_at = rotated_at
    log.rotated_by = rotated_by
    log.versions_resigned = versions_resigned
    log.resigned_version_ids = resigned_version_ids
    log.new_key_prefix = new_key_prefix
    log.old_key_prefix = old_key_prefix
    log.status = status
    log.error_detail = error_detail
    return log


def _sign(data: str, key: str) -> str:
    """生成 HMAC-SHA256 签名"""
    return hmac_lib.new(key.encode(), data.encode(), hashlib.sha256).hexdigest()


TEST_KEY = "test-hmac-key-at-least-32-chars-long-for-testing-only"
NEW_KEY = "new-hmac-key-at-least-32-chars-long-for-production-use"


# ============================================================
# get_key_status 测试
# ============================================================


@pytest.mark.asyncio
async def test_get_key_status_with_previous_key(service):
    """测试密钥状态查询（有 previous key）"""
    mock_settings = MagicMock()
    mock_settings.FAULT_TREE_HMAC_KEY = TEST_KEY
    mock_settings.FAULT_TREE_HMAC_KEY_PREVIOUS = "old-key-at-least-32-chars-long-for-previous"

    mock_session = AsyncMock()
    # active count
    count_result = MagicMock()
    count_result.scalar.return_value = 3
    # last rotation
    rotation_result = MagicMock()
    rotation_result.scalar_one_or_none.return_value = None

    mock_session.execute = AsyncMock(side_effect=[count_result, rotation_result])

    with (
        patch("app.services.diagnosis.hmac_key_service.get_settings", return_value=mock_settings),
        patch("app.services.diagnosis.hmac_key_service.async_session") as mock_async_session,
    ):
        mock_async_session.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_async_session.return_value.__aexit__ = AsyncMock(return_value=False)

        result = await service.get_key_status()

    assert result["key_configured"] is True
    assert result["key_length"] == len(TEST_KEY)
    assert result["key_prefix"] == "test****"
    assert result["previous_key_configured"] is True
    assert result["active_versions_count"] == 3
    assert result["last_rotation_at"] is None


@pytest.mark.asyncio
async def test_get_key_status_no_previous_key(service):
    """测试密钥状态查询（无 previous key）"""
    mock_settings = MagicMock()
    mock_settings.FAULT_TREE_HMAC_KEY = TEST_KEY
    mock_settings.FAULT_TREE_HMAC_KEY_PREVIOUS = None

    mock_session = AsyncMock()
    count_result = MagicMock()
    count_result.scalar.return_value = 0
    rotation_result = MagicMock()
    rotation_result.scalar_one_or_none.return_value = None
    mock_session.execute = AsyncMock(side_effect=[count_result, rotation_result])

    with (
        patch("app.services.diagnosis.hmac_key_service.get_settings", return_value=mock_settings),
        patch("app.services.diagnosis.hmac_key_service.async_session") as mock_async_session,
    ):
        mock_async_session.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_async_session.return_value.__aexit__ = AsyncMock(return_value=False)

        result = await service.get_key_status()

    assert result["previous_key_configured"] is False
    assert result["active_versions_count"] == 0


@pytest.mark.asyncio
async def test_get_key_status_with_last_rotation(service):
    """测试密钥状态查询（有历史轮换记录）"""
    mock_settings = MagicMock()
    mock_settings.FAULT_TREE_HMAC_KEY = TEST_KEY
    mock_settings.FAULT_TREE_HMAC_KEY_PREVIOUS = None

    last_rotation = MagicMock()
    last_rotation.rotated_at = datetime(2026, 3, 14, 10, 0, 0)

    mock_session = AsyncMock()
    count_result = MagicMock()
    count_result.scalar.return_value = 1
    rotation_result = MagicMock()
    rotation_result.scalar_one_or_none.return_value = last_rotation
    mock_session.execute = AsyncMock(side_effect=[count_result, rotation_result])

    with (
        patch("app.services.diagnosis.hmac_key_service.get_settings", return_value=mock_settings),
        patch("app.services.diagnosis.hmac_key_service.async_session") as mock_async_session,
    ):
        mock_async_session.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_async_session.return_value.__aexit__ = AsyncMock(return_value=False)

        result = await service.get_key_status()

    assert result["last_rotation_at"] == "2026-03-14T10:00:00"


# ============================================================
# rotate_key 测试
# ============================================================


@pytest.mark.asyncio
async def test_rotate_key_too_short(service):
    """测试密钥轮换 — 新密钥太短"""
    with pytest.raises(ValueError, match="新密钥长度必须 >= 32 字符"):
        await service.rotate_key("short-key", 1)


@pytest.mark.asyncio
async def test_rotate_key_no_versions(service):
    """测试密钥轮换 — 无 active/reviewed 版本"""
    mock_settings = MagicMock()
    mock_settings.FAULT_TREE_HMAC_KEY = TEST_KEY
    mock_settings.FAULT_TREE_HMAC_KEY_PREVIOUS = None

    mock_session = AsyncMock()
    # versions query returns empty
    versions_result = MagicMock()
    versions_result.scalars.return_value.all.return_value = []
    mock_session.execute = AsyncMock(return_value=versions_result)
    mock_session.add = MagicMock()
    mock_session.commit = AsyncMock()

    with (
        patch("app.services.diagnosis.hmac_key_service.get_settings", return_value=mock_settings),
        patch("app.services.diagnosis.hmac_key_service.async_session") as mock_async_session,
    ):
        mock_async_session.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_async_session.return_value.__aexit__ = AsyncMock(return_value=False)

        result = await service.rotate_key(NEW_KEY, 1)

    assert result["versions_resigned"] == 0
    assert result["resigned_version_ids"] == []


@pytest.mark.asyncio
async def test_rotate_key_success(service):
    """测试密钥轮换 — 成功重签名"""
    snapshot = json.dumps({"tree": {"id": 1}, "nodes": [], "edges": []}, sort_keys=True)
    old_sig = _sign(snapshot, TEST_KEY)

    v1 = _make_version(1, 1, 1, "active", snapshot, old_sig)
    v2 = _make_version(2, 1, 2, "reviewed", snapshot, None)

    mock_settings = MagicMock()
    mock_settings.FAULT_TREE_HMAC_KEY = TEST_KEY
    mock_settings.FAULT_TREE_HMAC_KEY_PREVIOUS = None

    mock_session = AsyncMock()
    versions_result = MagicMock()
    versions_result.scalars.return_value.all.return_value = [v1, v2]
    mock_session.execute = AsyncMock(return_value=versions_result)
    mock_session.add = MagicMock()
    mock_session.commit = AsyncMock()

    with (
        patch("app.services.diagnosis.hmac_key_service.get_settings", return_value=mock_settings),
        patch("app.services.diagnosis.hmac_key_service.async_session") as mock_async_session,
        patch("app.services.diagnosis.hmac_key_service.HMACManager") as mock_hmac,
    ):
        mock_async_session.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_async_session.return_value.__aexit__ = AsyncMock(return_value=False)
        mock_hmac.verify_signature.return_value = True
        mock_hmac.generate_signature_with_key.return_value = _sign(snapshot, NEW_KEY)

        result = await service.rotate_key(NEW_KEY, 1)

    assert result["versions_resigned"] == 2
    assert result["resigned_version_ids"] == [1, 2]
    # 验证签名被更新
    assert v1.hmac_signature == _sign(snapshot, NEW_KEY)
    assert v2.hmac_signature == _sign(snapshot, NEW_KEY)


@pytest.mark.asyncio
async def test_rotate_key_invalid_existing_signature(service):
    """测试密钥轮换 — 现有签名无效，中止轮换"""
    snapshot = json.dumps({"tree": {"id": 1}}, sort_keys=True)
    v1 = _make_version(1, 1, 1, "active", snapshot, "invalid_signature_aaaa" + "0" * 44)

    mock_settings = MagicMock()
    mock_settings.FAULT_TREE_HMAC_KEY = TEST_KEY
    mock_settings.FAULT_TREE_HMAC_KEY_PREVIOUS = None

    mock_session = AsyncMock()
    versions_result = MagicMock()
    versions_result.scalars.return_value.all.return_value = [v1]
    mock_session.execute = AsyncMock(return_value=versions_result)
    mock_session.add = MagicMock()
    mock_session.commit = AsyncMock()

    with (
        patch("app.services.diagnosis.hmac_key_service.get_settings", return_value=mock_settings),
        patch("app.services.diagnosis.hmac_key_service.async_session") as mock_async_session,
        patch("app.services.diagnosis.hmac_key_service.HMACManager") as mock_hmac,
    ):
        mock_async_session.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_async_session.return_value.__aexit__ = AsyncMock(return_value=False)
        mock_hmac.verify_signature.return_value = False

        with pytest.raises(ValueError, match="现有签名验证失败"):
            await service.rotate_key(NEW_KEY, 1)


# ============================================================
# verify_all_signatures 测试
# ============================================================


@pytest.mark.asyncio
async def test_verify_all_valid(service):
    """测试批量验证 — 全部通过"""
    snapshot = json.dumps({"tree": {"id": 1}}, sort_keys=True)
    sig = _sign(snapshot, TEST_KEY)
    v1 = _make_version(1, 1, 1, "active", snapshot, sig)

    mock_session = AsyncMock()
    versions_result = MagicMock()
    versions_result.scalars.return_value.all.return_value = [v1]
    mock_session.execute = AsyncMock(return_value=versions_result)

    with (
        patch("app.services.diagnosis.hmac_key_service.async_session") as mock_async_session,
        patch("app.services.diagnosis.hmac_key_service.HMACManager") as mock_hmac,
    ):
        mock_async_session.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_async_session.return_value.__aexit__ = AsyncMock(return_value=False)
        mock_hmac.verify_signature.return_value = True

        result = await service.verify_all_signatures()

    assert result["total_versions"] == 1
    assert result["valid_count"] == 1
    assert result["invalid_count"] == 0
    assert result["results"][0]["verification"] == "valid"


@pytest.mark.asyncio
async def test_verify_all_invalid(service):
    """测试批量验证 — 部分失败"""
    snapshot = json.dumps({"tree": {"id": 1}}, sort_keys=True)
    v1 = _make_version(1, 1, 1, "active", snapshot, "bad_sig" + "0" * 56)
    v2 = _make_version(2, 2, 1, "reviewed", snapshot, None)

    mock_session = AsyncMock()
    versions_result = MagicMock()
    versions_result.scalars.return_value.all.return_value = [v1, v2]
    mock_session.execute = AsyncMock(return_value=versions_result)

    with (
        patch("app.services.diagnosis.hmac_key_service.async_session") as mock_async_session,
        patch("app.services.diagnosis.hmac_key_service.HMACManager") as mock_hmac,
    ):
        mock_async_session.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_async_session.return_value.__aexit__ = AsyncMock(return_value=False)
        mock_hmac.verify_signature.return_value = False

        result = await service.verify_all_signatures()

    assert result["total_versions"] == 2
    assert result["valid_count"] == 0
    assert result["invalid_count"] == 2
    # v1 has signature but invalid, v2 has no signature
    verifications = {r["version_id"]: r["verification"] for r in result["results"]}
    assert verifications[1] == "invalid"
    assert verifications[2] == "no_signature"


@pytest.mark.asyncio
async def test_verify_all_empty(service):
    """测试批量验证 — 无版本"""
    mock_session = AsyncMock()
    versions_result = MagicMock()
    versions_result.scalars.return_value.all.return_value = []
    mock_session.execute = AsyncMock(return_value=versions_result)

    with patch("app.services.diagnosis.hmac_key_service.async_session") as mock_async_session:
        mock_async_session.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_async_session.return_value.__aexit__ = AsyncMock(return_value=False)

        result = await service.verify_all_signatures()

    assert result["total_versions"] == 0
    assert result["valid_count"] == 0
    assert result["invalid_count"] == 0


# ============================================================
# list_rotation_logs 测试
# ============================================================


@pytest.mark.asyncio
async def test_list_rotation_logs_pagination(service):
    """测试轮换日志分页查询"""
    log1 = _make_rotation_log(1, datetime(2026, 3, 14, 10, 0), 1, 3, [1, 2, 3], "new-", "old-", "success")
    log2 = _make_rotation_log(2, datetime(2026, 3, 14, 11, 0), 1, 0, [], "new2", None, "failed", "密钥太短")

    mock_session = AsyncMock()
    count_result = MagicMock()
    count_result.scalar.return_value = 2
    logs_result = MagicMock()
    logs_result.scalars.return_value.all.return_value = [log2, log1]
    mock_session.execute = AsyncMock(side_effect=[count_result, logs_result])

    with patch("app.services.diagnosis.hmac_key_service.async_session") as mock_async_session:
        mock_async_session.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_async_session.return_value.__aexit__ = AsyncMock(return_value=False)

        result = await service.list_rotation_logs(page=1, page_size=10)

    assert result["total"] == 2
    assert result["page"] == 1
    assert len(result["items"]) == 2
    assert result["items"][0]["status"] == "failed"
    assert result["items"][0]["error_detail"] == "密钥太短"
    assert result["items"][1]["versions_resigned"] == 3
    assert result["items"][1]["resigned_version_ids"] == [1, 2, 3]


@pytest.mark.asyncio
async def test_list_rotation_logs_empty(service):
    """测试轮换日志查询 — 无记录"""
    mock_session = AsyncMock()
    count_result = MagicMock()
    count_result.scalar.return_value = 0
    logs_result = MagicMock()
    logs_result.scalars.return_value.all.return_value = []
    mock_session.execute = AsyncMock(side_effect=[count_result, logs_result])

    with patch("app.services.diagnosis.hmac_key_service.async_session") as mock_async_session:
        mock_async_session.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_async_session.return_value.__aexit__ = AsyncMock(return_value=False)

        result = await service.list_rotation_logs()

    assert result["total"] == 0
    assert result["items"] == []


# ============================================================
# HMACManager.generate_signature_with_key 测试
# ============================================================


def test_generate_signature_with_key():
    """测试 HMACManager.generate_signature_with_key 方法"""
    from app.services.diagnosis.hmac_manager import HMACManager

    data = '{"tree": {"id": 1}}'
    key = "test-key-at-least-32-chars-long-for-unit-test"
    sig = HMACManager.generate_signature_with_key(data, key)

    # 验证是 64 字符的十六进制字符串
    assert len(sig) == 64
    assert all(c in "0123456789abcdef" for c in sig)

    # 验证与直接使用 hmac 模块结果一致
    expected = hmac_lib.new(key.encode(), data.encode(), hashlib.sha256).hexdigest()
    assert sig == expected


def test_generate_signature_with_key_different_keys():
    """测试不同密钥生成不同签名"""
    from app.services.diagnosis.hmac_manager import HMACManager

    data = '{"tree": {"id": 1}}'
    key1 = "key1-at-least-32-chars-long-for-unit-test-purpose"
    key2 = "key2-at-least-32-chars-long-for-unit-test-purpose"

    sig1 = HMACManager.generate_signature_with_key(data, key1)
    sig2 = HMACManager.generate_signature_with_key(data, key2)

    assert sig1 != sig2
