# DCIM 算力中心智能监控系统 - 知识库

> 版本: 1.0 | 更新日期: 2026-02-01

---

## 📚 知识库导航

### 🚀 [1. 快速入门](./1-quick-start/README.md)
新用户从这里开始，5分钟了解系统核心功能。

| 文档 | 描述 | 适用人员 |
|------|------|----------|
| [系统概览](./1-quick-start/overview.md) | 系统功能架构和核心价值 | 所有人 |
| [首次登录](./1-quick-start/first-login.md) | 登录、导航、个人设置 | 所有人 |
| [5分钟导览](./1-quick-start/5-minute-tour.md) | 快速了解主要功能模块 | 所有人 |

---

### 📖 [2. 操作指南](./2-user-guides/README.md)
按角色分类的详细操作手册。

#### 🔧 运维人员
| 文档 | 描述 |
|------|------|
| [告警处理](./2-user-guides/operator/alarm-handling.md) | 告警查看、确认、处理流程 |
| [设备监控](./2-user-guides/operator/device-monitoring.md) | 设备状态监控和巡检 |
| [大屏操作](./2-user-guides/operator/bigscreen.md) | 3D数字孪生大屏使用 |

#### ⚡ 能源管理员
| 文档 | 描述 |
|------|------|
| [PUE分析](./2-user-guides/energy-manager/pue-analysis.md) | PUE指标监控和优化 |
| [负荷转移](./2-user-guides/energy-manager/load-shifting.md) | 峰谷转移方案配置 |
| [节能方案](./2-user-guides/energy-manager/proposal-workflow.md) | 智能节能方案全流程 |
| [需量管理](./2-user-guides/energy-manager/demand-management.md) | 最大需量监控和控制 |

---

### 🔄 [3. 业务流程](./3-workflows/README.md)
核心业务流程的可视化图解。

| 流程 | 描述 | 查看 |
|------|------|------|
| 节能方案生成流程 | 从分析到执行的完整闭环 | [查看](./3-workflows/energy-saving-flow.md) |
| RL优化闭环流程 | 深度强化学习自适应优化 | [查看](./3-workflows/rl-optimization-flow.md) |
| 告警升级流程 | 四级告警的触发和处理 | [查看](./3-workflows/alarm-escalation.md) |
| 负荷转移流程 | 可转移负荷的调度流程 | [查看](./3-workflows/load-transfer-flow.md) |

---

### 📊 [4. 数据利用指南](./4-data-guides/README.md)
理解数据含义，掌握计算逻辑。

| 文档 | 描述 |
|------|------|
| [数据字典](./4-data-guides/data-dictionary.md) | 核心数据表和字段说明 |
| [计算公式大全](./4-data-guides/formula-reference.md) | PUE、节能收益等核心公式 |
| [API调用示例](./4-data-guides/api-cookbook.md) | 常用API的调用示例 |
| [报表模板](./4-data-guides/report-templates.md) | 标准报表格式和生成方法 |

---

### 🔧 [5. 问题解决](./5-troubleshooting/README.md)
快速定位和解决常见问题。

| 文档 | 描述 |
|------|------|
| [常见问题 FAQ](./5-troubleshooting/faq.md) | 高频问题快速解答 |
| [错误代码速查](./5-troubleshooting/error-codes.md) | 系统错误代码和解决方案 |
| [性能优化](./5-troubleshooting/performance-tuning.md) | 系统性能调优指南 |

#### 具体问题解决方案
- [PUE异常波动](./5-troubleshooting/common-issues/pue-abnormal.md)
- [告警风暴处理](./5-troubleshooting/common-issues/alarm-flood.md)
- [数据缺失排查](./5-troubleshooting/common-issues/data-missing.md)
- [节能方案无效](./5-troubleshooting/common-issues/proposal-ineffective.md)

---

### 💡 [6. 案例库](./6-case-studies/README.md)
真实场景的最佳实践案例。

| 案例 | 场景 | 收益 |
|------|------|------|
| [案例001: 冷却系统优化](./6-case-studies/case-001-cooling-optimization.md) | 冷机群控+变频水泵 | 年省 ¥85万 |
| [案例002: 峰谷套利](./6-case-studies/case-002-peak-valley-arbitrage.md) | UPS储能+负荷转移 | 年省 ¥42万 |
| [案例003: 需求响应](./6-case-studies/case-003-demand-response.md) | VPP虚拟电厂参与 | 年收入 ¥15万 |
| [案例004: 告警精准化](./6-case-studies/case-004-alarm-optimization.md) | ML告警降噪 | 误报降低85% |

---

## 🔍 快速查找

### 按任务查找

| 我想要... | 查看文档 |
|-----------|----------|
| 了解系统能做什么 | [系统概览](./1-quick-start/overview.md) |
| 处理一个告警 | [告警处理](./2-user-guides/operator/alarm-handling.md) |
| 创建节能方案 | [节能方案流程](./2-user-guides/energy-manager/proposal-workflow.md) |
| 配置负荷转移 | [负荷转移指南](./2-user-guides/energy-manager/load-shifting.md) |
| 看懂PUE数据 | [PUE分析](./2-user-guides/energy-manager/pue-analysis.md) |
| 理解某个公式 | [计算公式大全](./4-data-guides/formula-reference.md) |
| 解决一个报错 | [错误代码速查](./5-troubleshooting/error-codes.md) |
| 参考成功案例 | [案例库](./6-case-studies/README.md) |

### 按关键词查找

- **PUE**: [PUE分析](./2-user-guides/energy-manager/pue-analysis.md) | [公式](./4-data-guides/formula-reference.md#pue)
- **告警**: [告警处理](./2-user-guides/operator/alarm-handling.md) | [告警流程](./3-workflows/alarm-escalation.md)
- **节能**: [节能方案](./2-user-guides/energy-manager/proposal-workflow.md) | [节能流程](./3-workflows/energy-saving-flow.md)
- **负荷转移**: [负荷转移指南](./2-user-guides/energy-manager/load-shifting.md) | [转移流程](./3-workflows/load-transfer-flow.md)
- **RL/强化学习**: [RL优化流程](./3-workflows/rl-optimization-flow.md)

---

## 📞 获取帮助

- **技术支持**: support@dcim.example.com
- **问题反馈**: 提交 Issue 到项目仓库
- **紧急热线**: 400-XXX-XXXX (7×24小时)

---

*本知识库由 Claude Code 智能生成，持续更新中。*
