"""依赖安全审计服务 — 每周运行 pip-audit 扫描已知漏洞。

Architecture Reference: Section 18.11 安全加固架构（FR34-37 SBOM 管理）
- 集成 pip-audit 定期扫描
- 发现漏洞时触发系统告警
"""

import asyncio
import json
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


class DependencyAuditService:
    """依赖安全审计服务 — 每周扫描 Python 依赖漏洞。"""

    async def run_audit(self) -> dict:
        """执行 pip-audit 扫描并返回结果。

        pip-audit --format json 输出格式为嵌套结构:
        [
          {
            "name": "package-name",
            "version": "1.0.0",
            "vulns": [
              {"id": "PYSEC-2024-XXX", "fix_versions": ["1.0.1"], "aliases": ["CVE-..."], "description": "..."}
            ]
          }
        ]
        注意: pip-audit 不提供 CVSS 分数，只提供漏洞 ID 和修复版本。
        """
        try:
            proc = await asyncio.create_subprocess_exec(
                "pip-audit",
                "--format",
                "json",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=120)

            if stdout:
                raw_data = json.loads(stdout.decode())
            else:
                raw_data = []

            # 展平嵌套结构: 提取所有有漏洞的包
            vulnerable_packages = []
            for pkg_entry in raw_data:
                pkg_name = pkg_entry.get("name", "unknown")
                pkg_version = pkg_entry.get("version", "unknown")
                vulns = pkg_entry.get("vulns", [])
                for vuln in vulns:
                    vulnerable_packages.append(
                        {
                            "package": pkg_name,
                            "version": pkg_version,
                            "vuln_id": vuln.get("id", "unknown"),
                            "fix_versions": vuln.get("fix_versions", []),
                            "aliases": vuln.get("aliases", []),
                            "description": vuln.get("description", ""),
                        }
                    )

            result = {
                "scan_time": datetime.now().isoformat(),
                "total_vulnerabilities": len(vulnerable_packages),
                "vulnerable_packages": vulnerable_packages,
            }

            if vulnerable_packages:
                await self._trigger_alert(vulnerable_packages)

            return result

        except FileNotFoundError:
            logger.warning("pip-audit 未安装，跳过依赖安全扫描")
            return {"scan_time": datetime.now().isoformat(), "error": "pip-audit not installed"}
        except asyncio.TimeoutError:
            logger.error("pip-audit 扫描超时（120s）")
            return {"scan_time": datetime.now().isoformat(), "error": "timeout"}
        except Exception as e:
            logger.error(f"依赖安全扫描失败: {e}", exc_info=True)
            return {"scan_time": datetime.now().isoformat(), "error": str(e)}

    async def _trigger_alert(self, vulnerable_packages: list):
        """通过日志告警记录发现的漏洞。"""
        for vuln in vulnerable_packages:
            fix_ver = ", ".join(vuln["fix_versions"]) if vuln["fix_versions"] else "未知"
            aliases = ", ".join(vuln["aliases"]) if vuln["aliases"] else ""
            alias_str = f" ({aliases})" if aliases else ""
            logger.critical(
                f"[安全告警] 依赖漏洞: {vuln['package']}=={vuln['version']} — "
                f"{vuln['vuln_id']}{alias_str} — 建议升级到 {fix_ver}"
            )


# 单例
dependency_audit_service = DependencyAuditService()
