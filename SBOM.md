# 软件物料清单 (SBOM)

> 本文件记录项目使用的关键算法依赖及其安全信息。
> 更新时机：新增/升级/移除关键依赖时同步更新本文件。

## 关键算法依赖

| 库名 | 版本范围 | 许可证 | 状态 | 用途 | 引入 Epic |
|------|---------|--------|------|------|-----------|
| NetworkX | >=3.0,<4.0 | BSD-3-Clause | 已安装 | 故障树/因果图 DAG 推理 | Epic 24-26 |
| numpy | >=1.24.0 | BSD-3-Clause | 已安装 | 贝叶斯矩阵化传播、数值计算 | Epic 24 |
| scipy | >=1.11.0 | BSD-3-Clause | 已安装 | 最小二乘校准（Epic 32）、多设备优化 | Epic 7, 32 |
| APScheduler | ==3.10.4 | MIT | 已安装 | 定时诊断/校准/扫描任务调度 | Epic 24 |
| scikit-learn | >=1.3.0,<2.0 | BSD-3-Clause | 已安装 | IsolationForest 异常检测 | Epic 26 |

## 依赖关系说明

- **NetworkX** 用于构建故障树 DAG 结构，支持拓扑排序和路径搜索
- **numpy** 为贝叶斯推理提供矩阵运算，被 scipy 依赖
- **scipy** 提供 `scipy.optimize.least_squares` 用于 RC 热参数校准
- **APScheduler** 管理所有异步定时任务（诊断调度、校准、安全扫描等）
- **scikit-learn** 提供 IsolationForest 用于训练数据异常检测（Story 26.9），条件导入（未安装时静默跳过）

## 安全扫描策略

- **CI 扫描**: `.github/workflows/ci.yml` 中 `pip-audit` 步骤（`continue-on-error: true`）
- **定时扫描**: APScheduler 每周一凌晨 3:30 执行 `pip-audit --format json`
- **告警方式**: `logger.critical()` 记录漏洞详情（库名、漏洞 ID、建议修复版本）
- **工具**: pip-audit（扫描 PyPI 已知漏洞数据库）
