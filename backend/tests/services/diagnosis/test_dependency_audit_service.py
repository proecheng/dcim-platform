"""依赖安全审计服务测试。

Story 26.8 — AC #5, #6
"""
import asyncio
import json
import logging

import pytest
from unittest.mock import AsyncMock, patch

from app.services.diagnosis.dependency_audit_service import DependencyAuditService


MOCK_AUDIT_OUTPUT_WITH_VULNS = json.dumps([
    {
        "name": "requests",
        "version": "2.25.0",
        "vulns": [
            {
                "id": "PYSEC-2024-001",
                "fix_versions": ["2.31.0"],
                "aliases": ["CVE-2024-12345"],
                "description": "HTTP redirect vulnerability",
            }
        ],
    }
]).encode()

MOCK_AUDIT_OUTPUT_NO_VULNS = b"[]"


class TestDependencyAuditService:
    """依赖安全审计服务测试"""

    @pytest.mark.asyncio
    async def test_run_audit_pip_audit_not_installed(self):
        """pip-audit 未安装时静默跳过"""
        service = DependencyAuditService()
        with patch("asyncio.create_subprocess_exec", side_effect=FileNotFoundError):
            result = await service.run_audit()
        assert "error" in result
        assert result["error"] == "pip-audit not installed"

    @pytest.mark.asyncio
    async def test_run_audit_success_no_vulnerabilities(self):
        """无漏洞时返回 total_vulnerabilities=0"""
        service = DependencyAuditService()
        mock_proc = AsyncMock()
        mock_proc.communicate = AsyncMock(return_value=(MOCK_AUDIT_OUTPUT_NO_VULNS, b""))
        with patch("asyncio.create_subprocess_exec", return_value=mock_proc):
            result = await service.run_audit()
        assert result["total_vulnerabilities"] == 0
        assert result["vulnerable_packages"] == []

    @pytest.mark.asyncio
    async def test_run_audit_with_vulnerabilities(self):
        """有漏洞时正确展平嵌套结构"""
        service = DependencyAuditService()
        mock_proc = AsyncMock()
        mock_proc.communicate = AsyncMock(return_value=(MOCK_AUDIT_OUTPUT_WITH_VULNS, b""))
        with patch("asyncio.create_subprocess_exec", return_value=mock_proc):
            result = await service.run_audit()
        assert result["total_vulnerabilities"] == 1
        vuln = result["vulnerable_packages"][0]
        assert vuln["package"] == "requests"
        assert vuln["vuln_id"] == "PYSEC-2024-001"
        assert "2.31.0" in vuln["fix_versions"]

    @pytest.mark.asyncio
    async def test_run_audit_triggers_alert(self, caplog):
        """有漏洞时触发 critical 日志告警"""
        service = DependencyAuditService()
        mock_proc = AsyncMock()
        mock_proc.communicate = AsyncMock(return_value=(MOCK_AUDIT_OUTPUT_WITH_VULNS, b""))
        with patch("asyncio.create_subprocess_exec", return_value=mock_proc):
            with caplog.at_level(logging.CRITICAL):
                await service.run_audit()
        assert "[安全告警]" in caplog.text
        assert "requests" in caplog.text
        assert "PYSEC-2024-001" in caplog.text

    @pytest.mark.asyncio
    async def test_run_audit_timeout(self):
        """扫描超时返回 error=timeout"""
        service = DependencyAuditService()
        mock_proc = AsyncMock()
        mock_proc.communicate = AsyncMock(return_value=(b"", b""))
        with patch("asyncio.create_subprocess_exec", return_value=mock_proc):
            with patch("asyncio.wait_for", side_effect=asyncio.TimeoutError):
                result = await service.run_audit()
        assert result["error"] == "timeout"

    @pytest.mark.asyncio
    async def test_run_audit_json_parse_error(self):
        """JSON 解析失败返回 error"""
        service = DependencyAuditService()
        mock_proc = AsyncMock()
        mock_proc.communicate = AsyncMock(return_value=(b"invalid json", b""))
        with patch("asyncio.create_subprocess_exec", return_value=mock_proc):
            result = await service.run_audit()
        assert "error" in result

    @pytest.mark.asyncio
    async def test_trigger_alert_format(self, caplog):
        """告警日志包含包名、漏洞ID、修复版本"""
        service = DependencyAuditService()
        vulns = [
            {
                "package": "flask",
                "version": "2.0.0",
                "vuln_id": "PYSEC-2024-999",
                "fix_versions": ["2.3.0"],
                "aliases": ["CVE-2024-99999"],
                "description": "test vuln",
            }
        ]
        with caplog.at_level(logging.CRITICAL):
            await service._trigger_alert(vulns)
        assert "flask==2.0.0" in caplog.text
        assert "PYSEC-2024-999" in caplog.text
        assert "2.3.0" in caplog.text
        assert "CVE-2024-99999" in caplog.text

    @pytest.mark.asyncio
    async def test_run_audit_empty_stdout(self):
        """stdout 为空时返回 total_vulnerabilities=0"""
        service = DependencyAuditService()
        mock_proc = AsyncMock()
        mock_proc.communicate = AsyncMock(return_value=(b"", b""))
        with patch("asyncio.create_subprocess_exec", return_value=mock_proc):
            result = await service.run_audit()
        assert result["total_vulnerabilities"] == 0
