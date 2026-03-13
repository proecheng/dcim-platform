# Story 26.8: 边缘推理预留与 SBOM 管理

Status: done

## Story

As a 开发者,
I want 为边缘推理预留接口并建立依赖安全管理,
So that 未来扩展边缘推理时无需重构，且第三方库漏洞能及时发现。

## 依赖

- Epic 24（智能诊断核心引擎）— done
- Epic 25（智能诊断专业扩展）— done
- Story 26.7（灾难恢复演练）— done（CircuitBreaker.force_open 已添加）

## Acceptance Criteria

1. Given 网关层代码已存在
   When 开发者在诊断服务模块中预留边缘推理接口
   Then 在 `backend/app/services/diagnosis/` 中定义 `EdgeDiagnosisHandler` 抽象接口
   And 接口包含 4 个抽象方法：`connect()`, `receive_rules()`, `execute_l1()`, `report_result()`
   And 提供 `EdgeDiagnosisStub` 具体实现类（所有方法返回占位值并记录日志）

2. Given MQTT 通信链路已实现（Epic 2）
   When 预留边缘诊断 MQTT topic
   Then 在 `edge_diagnosis_handler.py` 中以代码常量定义 topic 模板
   And 包含 topic 模板：`dcim/diagnosis/rules/{gateway_id}` 和 `dcim/diagnosis/results/{gateway_id}`
   And 提供 `get_edge_diagnosis_config()` 方法返回完整预留配置
   And 配置仅为代码级预留，不写入数据库，不启用实际订阅

3. Given 项目 CI 已有 GitHub Actions 配置
   When 集成 `pip-audit` 扫描
   Then 在 `.github/workflows/ci.yml` 的 `backend-tests` job 中追加 `pip-audit` 扫描步骤
   And 首次集成使用 `continue-on-error: true`，避免已知低危漏洞阻断所有 PR
   And 扫描发现任何已知漏洞时输出 warning 注解

4. Given 项目使用多个关键算法库
   When 创建 SBOM 文件
   Then 在项目根目录创建 `SBOM.md`
   And 列出关键算法依赖：NetworkX、numpy、scipy、APScheduler
   And scikit-learn 标注为"计划引入（Story 26.9）"，当前未安装
   And 每个依赖包含：版本范围、许可证类型、用途说明

5. Given 后端依赖安全扫描
   When APScheduler 每周定时任务执行 pip-audit
   Then 发现漏洞时通过 `logger.critical()` 记录告警日志
   And 告警内容包含：库名、漏洞 ID、建议修复版本
   And pip-audit 未安装时静默跳过（`FileNotFoundError` 被捕获）

6. Given 所有新增代码
   When 运行测试
   Then 单元测试全部通过（15+ 个）

## Tasks / Subtasks

- [ ] Task 1: 边缘诊断抽象接口 (AC: #1)
  - [ ] 1.1 新建 `backend/app/services/diagnosis/edge_diagnosis_handler.py` — 抽象接口定义
  - [ ] 1.2 新建 `backend/app/services/diagnosis/edge_diagnosis_stub.py` — Stub 实现（日志 + NotImplementedError）

- [ ] Task 2: MQTT Topic 预留配置 (AC: #2)
  - [ ] 2.1 在 `backend/app/services/diagnosis/edge_diagnosis_handler.py` 中定义 topic 常量
  - [ ] 2.2 提供 `get_edge_diagnosis_config()` 方法返回预留配置

- [ ] Task 3: pip-audit CI 集成 (AC: #3)
  - [ ] 3.1 修改 `.github/workflows/ci.yml` 追加 pip-audit 步骤

- [ ] Task 4: SBOM 文件创建 (AC: #4)
  - [ ] 4.1 新建 `SBOM.md` 列出关键算法依赖

- [ ] Task 5: 依赖安全扫描定时任务 (AC: #5)
  - [ ] 5.1 新建 `backend/app/services/diagnosis/dependency_audit_service.py` — pip-audit 定时扫描服务
  - [ ] 5.2 在诊断调度器中注册每周定时任务

- [ ] Task 6: 单元测试 (AC: #6)
  - [ ] 6.1 新建 `backend/tests/services/diagnosis/test_edge_diagnosis_handler.py`
  - [ ] 6.2 新建 `backend/tests/services/diagnosis/test_dependency_audit_service.py`

## Dev Notes

### Task 1: 边缘诊断抽象接口

**文件**: `backend/app/services/diagnosis/edge_diagnosis_handler.py`

```python
"""边缘推理预留接口 — 愿景阶段，仅定义抽象接口不实现具体逻辑。

Architecture Reference: Section 18.13 边缘推理架构（FR34-33~34）
- 网关层预留 diagnosis_handler 接口
- 协议: 中心节点通过 MQTT 下发规则子集到边缘
- 边缘执行 L1 规则匹配，复杂场景上报中心
- 多节点一致性: 中心节点作为仲裁者
"""
from abc import ABC, abstractmethod
from typing import Any

# 预留 MQTT Topic 模板
EDGE_DIAGNOSIS_TOPICS = {
    "rules_push": "dcim/diagnosis/rules/{gateway_id}",
    "results_report": "dcim/diagnosis/results/{gateway_id}",
}


class EdgeDiagnosisHandler(ABC):
    """边缘诊断处理器抽象接口。

    未来实现时，网关端实例化此接口的具体实现类，
    通过 MQTT 接收中心节点下发的 L1 规则子集并本地执行。
    """

    @abstractmethod
    async def connect(self, gateway_id: str, mqtt_broker: str) -> bool:
        """连接到中心节点的 MQTT broker，订阅规则下发 topic。"""
        ...

    @abstractmethod
    async def receive_rules(self, gateway_id: str) -> list[dict]:
        """接收中心节点下发的 L1 规则子集。"""
        ...

    @abstractmethod
    async def execute_l1(self, rules: list[dict], evidence: dict[str, Any]) -> dict:
        """在边缘端执行 L1 规则匹配。"""
        ...

    @abstractmethod
    async def report_result(self, gateway_id: str, result: dict) -> bool:
        """将诊断结果上报中心节点。"""
        ...
```

**⚠️ 不要在 gateway 模块中创建文件**：架构 18.13 说"网关层预留 diagnosis_handler 接口"，但实际的网关模块（`app/models/gateway.py`, `app/services/gateway_registration.py`）是管理网关设备的，不是网关端代码。边缘推理接口应放在 `services/diagnosis/` 中，作为中心节点侧的抽象定义。

### Task 1.2: Stub 实现

**文件**: `backend/app/services/diagnosis/edge_diagnosis_stub.py`

```python
"""边缘推理 Stub 实现 — 记录调用日志，返回"未实现"状态。

用于系统集成测试和未来开发时的占位验证。
"""
import logging
from typing import Any
from .edge_diagnosis_handler import EdgeDiagnosisHandler

logger = logging.getLogger(__name__)


class EdgeDiagnosisStub(EdgeDiagnosisHandler):
    """Stub 实现：所有方法记录日志并返回未实现状态。"""

    async def connect(self, gateway_id: str, mqtt_broker: str) -> bool:
        logger.info(f"[EdgeStub] connect called: gateway={gateway_id}, broker={mqtt_broker} — 未实现")
        return False

    async def receive_rules(self, gateway_id: str) -> list[dict]:
        logger.info(f"[EdgeStub] receive_rules called: gateway={gateway_id} — 未实现")
        return []

    async def execute_l1(self, rules: list[dict], evidence: dict[str, Any]) -> dict:
        logger.info(f"[EdgeStub] execute_l1 called: {len(rules)} rules — 未实现")
        return {"status": "not_implemented", "message": "边缘推理尚未实现"}

    async def report_result(self, gateway_id: str, result: dict) -> bool:
        logger.info(f"[EdgeStub] report_result called: gateway={gateway_id} — 未实现")
        return False
```

### Task 2: MQTT Topic 预留

MQTT topic 常量已在 `edge_diagnosis_handler.py` 中定义（`EDGE_DIAGNOSIS_TOPICS` dict）。

额外提供一个工具方法用于获取完整预留配置：

```python
def get_edge_diagnosis_config() -> dict:
    """返回边缘推理预留配置（用于 API 查询和未来集成）。"""
    return {
        "enabled": False,
        "status": "reserved",
        "description": "边缘推理接口预留，愿景阶段，待 FR34-33/34 实现",
        "mqtt_topics": EDGE_DIAGNOSIS_TOPICS,
        "supported_levels": ["L1"],
        "arbitration": "center_node",
    }
```

此方法放在 `edge_diagnosis_handler.py` 底部。**不需要写入 system_configs 数据库表** — 配置是代码级预留，不是运行时可修改的参数。

### Task 3: pip-audit CI 集成

**修改文件**: `.github/workflows/ci.yml`

在 `backend-tests` job 的 `运行测试` 步骤之后、`上传覆盖率报告` 步骤之前追加：

```yaml
      - name: 依赖安全扫描 (pip-audit)
        continue-on-error: true
        run: |
          pip install pip-audit
          pip-audit --desc 2>&1 || echo "::warning::发现依赖安全漏洞，请检查并修复"
```

**⚠️ CI 文件结构（已验证）**：
- `backend-tests` job 使用 `defaults.run.working-directory: backend`
- 步骤顺序：checkout → setup-python → 安装依赖 → ruff check → ruff format → **运行测试** → [在此插入] → 上传覆盖率报告
- `pip-audit` 扫描的是当前 Python 环境中已安装的包（`pip install -r requirements.txt` 在前面步骤已执行）

**⚠️ `continue-on-error: true`**：首次集成时必须设置，避免现有依赖的已知低危漏洞阻断所有 PR。确认无误后可去掉此标志改为严格模式。

**⚠️ pip-audit 不支持 CVSS 过滤**：`pip-audit` 命令行没有 `--cvss-threshold` 参数。它只能报告所有已知漏洞或忽略特定漏洞 ID（`--ignore-vuln`）。无法在 CI 层面按 CVSS 分数过滤。

### Task 4: SBOM.md

**新建文件**: `SBOM.md`（项目根目录）

内容包含：
- 文档目的和更新说明
- 关键算法依赖表格（名称、版本范围、许可证、用途、引入 Epic）
- 依赖关系说明
- 安全扫描策略

**关键依赖信息（从 requirements.txt 提取）**：

| 库名 | 版本范围 | 许可证 | 状态 | 用途 |
|------|---------|--------|------|------|
| NetworkX | >=3.0,<4.0 | BSD-3-Clause | 已安装 | 故障树/因果图 DAG 推理（Epic 24-26） |
| numpy | >=1.24.0 | BSD-3-Clause | 已安装 | 贝叶斯矩阵化传播、数值计算 |
| scipy | >=1.11.0 | BSD-3-Clause | 已安装 | 最小二乘校准（Epic 32）、多设备优化 |
| APScheduler | ==3.10.4 | MIT | 已安装 | 定时诊断/校准/扫描任务调度 |
| scikit-learn | (未安装) | BSD-3-Clause | 计划引入 | IsolationForest 异常检测（Story 26.9 需要时添加到 requirements.txt） |

**⚠️ scikit-learn 当前不在 requirements.txt 或 requirements-ml.txt 中**：requirements-ml.txt 仅含 torch、numpy、reportlab。scikit-learn 需要在 Story 26.9 实现时才添加到 requirements.txt。SBOM 中标注为"计划引入"。

### Task 5: 依赖安全扫描定时任务

**新建文件**: `backend/app/services/diagnosis/dependency_audit_service.py`

```python
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
                "pip-audit", "--format", "json",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(), timeout=120
            )

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
                    vulnerable_packages.append({
                        "package": pkg_name,
                        "version": pkg_version,
                        "vuln_id": vuln.get("id", "unknown"),
                        "fix_versions": vuln.get("fix_versions", []),
                        "aliases": vuln.get("aliases", []),
                        "description": vuln.get("description", ""),
                    })

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
        except (json.JSONDecodeError, Exception) as e:
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
```

**⚠️ pip-audit 不提供 CVSS 分数**：pip-audit 只报告漏洞 ID 和修复版本。如需 CVSS 分数，需要额外集成 OSV API（`https://api.osv.dev/v1/vulns/{id}`），这超出本 Story 范围。当前策略：任何被 pip-audit 标记的漏洞都记录告警。

**⚠️ pip-audit 可能未安装在生产环境**：服务启动时不会失败（`FileNotFoundError` 被捕获）。仅在 pip-audit 可用时执行扫描。

**⚠️ 告警机制**：当前使用 `logger.critical()` 记录。后续可扩展 `_trigger_alert()` 集成 Redis Pub/Sub → WebSocket 推送。

### Task 5.2: 注册定时任务

在 `backend/app/main.py` 的 APScheduler `try` 块中注册定时任务。

**⚠️ 关键模式（已验证）**：所有 APScheduler 任务都注册在 `main.py` 第 598-955 行的 `try` 块内（`from apscheduler.schedulers.asyncio import AsyncIOScheduler` 开始，`scheduler.start()` 结束之前）。每个任务用独立的 `try/except ImportError` 包裹，内部定义 `async def` 包装函数。

**注册位置**：在 `scheduler.start()`（line 955）之前、VPP 容量刷新任务（line 953）之后追加：

```python
        # Story 26.8: 依赖安全扫描 — 每周一凌晨 3:30
        try:
            from app.services.diagnosis.dependency_audit_service import dependency_audit_service

            async def _run_dependency_audit():
                try:
                    result = await dependency_audit_service.run_audit()
                    vuln_count = result.get("total_vulnerabilities", 0)
                    logger.info(f"依赖安全扫描完成: 发现 {vuln_count} 个漏洞")
                except Exception as e:
                    logger.error(f"依赖安全扫描任务失败: {e}", exc_info=True)

            scheduler.add_job(
                _run_dependency_audit,
                'cron',
                day_of_week='mon',
                hour=3,
                minute=30,
                id='dependency_audit_weekly',
                max_instances=1,
                replace_existing=True,
                name='依赖安全审计',
            )
        except ImportError:
            logger.warning("⚠️  dependency_audit_service 模块不可用，跳过依赖安全扫描任务")
```

**⚠️ 不要在 `try` 块外注册**：`scheduler` 变量仅在 line 598 的 `try` 块内可用。如果在外部引用会导致 `NameError`。

同时在 `scheduler.start()` 之后追加日志行：
```python
        logger.info("✓ 依赖安全审计任务已启动（每周一凌晨 3:30）")
```

### 测试设计

#### test_edge_diagnosis_handler.py（约 10 个测试）

```python
import pytest
from app.services.diagnosis.edge_diagnosis_handler import (
    EdgeDiagnosisHandler, EDGE_DIAGNOSIS_TOPICS, get_edge_diagnosis_config,
)
from app.services.diagnosis.edge_diagnosis_stub import EdgeDiagnosisStub

class TestEdgeDiagnosisHandler:
    """抽象接口测试"""
    # 1. test_cannot_instantiate_abstract_class — pytest.raises(TypeError) 验证 ABC 不可直接实例化
    #    EdgeDiagnosisHandler() 会抛 TypeError("Can't instantiate abstract class...")

class TestEdgeDiagnosisStub:
    """Stub 实现测试（核心测试 — 验证 Stub 正确实现了所有抽象方法）"""
    # 2. test_stub_is_subclass — isinstance(EdgeDiagnosisStub(), EdgeDiagnosisHandler) == True
    # 3. test_connect_returns_false — await stub.connect("gw-1", "mqtt://...") == False
    # 4. test_receive_rules_returns_empty — await stub.receive_rules("gw-1") == []
    # 5. test_execute_l1_returns_not_implemented_status — result["status"] == "not_implemented"
    # 6. test_report_result_returns_false — await stub.report_result("gw-1", {}) == False
    # 7. test_connect_logs_call — 使用 caplog 验证 "[EdgeStub] connect called" 日志
    # 8. test_execute_l1_logs_rule_count — 传入 3 条规则，验证日志包含 "3 rules"

class TestEdgeDiagnosisConfig:
    # 9. test_get_edge_diagnosis_config_structure — 返回 dict 包含 enabled/status/mqtt_topics 键
    # 10. test_config_disabled_by_default — config["enabled"] == False
    # 11. test_mqtt_topics_contain_gateway_placeholder — "{gateway_id}" 在两个 topic 中
    # 12. test_topics_constant_keys — EDGE_DIAGNOSIS_TOPICS 包含 "rules_push" 和 "results_report" 键
```

**⚠️ 不要测试 ABC 方法的 NotImplementedError**：`@abstractmethod` + `...` 的方法体无法被直接调用（Python 不允许实例化 ABC），也无需测试。只需验证：(1) ABC 不可实例化 (2) Stub 正确实现所有方法。

**⚠️ 测试异步方法**：使用 `@pytest.mark.asyncio` 装饰器。项目中已有此模式（参考 `test_chaos_drill_service.py`）。

#### test_dependency_audit_service.py（约 8 个测试）

```python
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from app.services.diagnosis.dependency_audit_service import DependencyAuditService

class TestDependencyAuditService:
    # 1. test_run_audit_pip_audit_not_installed — patch create_subprocess_exec 抛 FileNotFoundError，返回 error 字段
    # 2. test_run_audit_success_no_vulnerabilities — stdout=b"[]"，total_vulnerabilities==0
    # 3. test_run_audit_with_vulnerabilities — stdout 含嵌套结构 [{"name":"pkg","version":"1.0","vulns":[...]}]
    #    验证展平逻辑：vulnerable_packages 列表包含正确的 package/vuln_id/fix_versions
    # 4. test_run_audit_triggers_alert — 有漏洞时 logger.critical 被调用
    # 5. test_run_audit_timeout — patch wait_for 抛 asyncio.TimeoutError，返回 error=="timeout"
    # 6. test_run_audit_json_parse_error — stdout=b"invalid json"，返回 error 字段
    # 7. test_trigger_alert_format — 验证告警日志包含包名、漏洞ID、修复版本
    # 8. test_run_audit_empty_stdout — stdout=b""，返回 total_vulnerabilities==0
```

**⚠️ 测试模式**：使用 `unittest.mock.AsyncMock` patch `asyncio.create_subprocess_exec`，不实际运行 pip-audit。Mock 的 `proc.communicate()` 返回 `(stdout_bytes, stderr_bytes)` 元组。

**⚠️ pip-audit JSON mock 数据**：
```python
MOCK_AUDIT_OUTPUT = json.dumps([
    {
        "name": "requests",
        "version": "2.25.0",
        "vulns": [
            {
                "id": "PYSEC-2024-001",
                "fix_versions": ["2.31.0"],
                "aliases": ["CVE-2024-12345"],
                "description": "HTTP redirect vulnerability"
            }
        ]
    }
]).encode()
```

### Project Structure Notes

- **新建文件:**
  - `backend/app/services/diagnosis/edge_diagnosis_handler.py` — 抽象接口 + topic 常量 + 配置方法
  - `backend/app/services/diagnosis/edge_diagnosis_stub.py` — Stub 实现
  - `backend/app/services/diagnosis/dependency_audit_service.py` — pip-audit 扫描服务
  - `backend/tests/services/diagnosis/test_edge_diagnosis_handler.py` — 接口测试
  - `backend/tests/services/diagnosis/test_dependency_audit_service.py` — 审计服务测试
  - `SBOM.md` — 软件物料清单

- **修改文件:**
  - `.github/workflows/ci.yml` — 追加 pip-audit 步骤
  - `backend/app/main.py` — 追加依赖审计定时任务注册（需确认现有模式）

### References

- [Source: _bmad-output/planning-artifacts/epics.md — Story 26.8]
- [Source: _bmad-output/planning-artifacts/architecture.md — Section 18.11 安全加固架构]
- [Source: _bmad-output/planning-artifacts/architecture.md — Section 18.13 边缘推理架构]
- [Source: backend/app/services/diagnosis/ — 现有诊断服务目录（34 文件）]
- [Source: backend/app/models/gateway.py — 网关数据模型]
- [Source: backend/requirements.txt — 依赖版本]
- [Source: .github/workflows/ci.yml — 现有 CI 配置]
- [Source: 26-7-disaster-recovery-drill.md — 前序 Story 实现模式]
