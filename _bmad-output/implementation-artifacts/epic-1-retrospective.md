# Epic 1 回顾：采集网关框架 + Modbus/SNMP 适配器

## 完成情况

全部 6 个 Story 完成，建立了 gateway/ 独立模块和完整的协议适配器插件化框架。

| Story | 标题 | 后端测试 | 前端构建 |
|-------|------|---------|---------|
| 1-1 | 协议适配器插件化框架 | 45/45 ✅ | N/A |
| 1-2 | Modbus TCP 适配器 | 49/49 ✅ | N/A |
| 1-3 | Modbus RTU 适配器 | 28/28 ✅ | N/A |
| 1-4 | SNMP v2c/v3 适配器 | 30/30 ✅ | N/A |
| 1-5 | 连接测试功能 | 22/22 ✅ | N/A |
| 1-6 | 干接点信号采集 | 25/25 ✅ | N/A |

总计：199 个测试通过，6 次代码审查全部通过。

## 关键经验教训

### 架构决策

1. **gateway/ 模块独立于 backend/**：网关代码放在项目根目录 `gateway/`，不依赖 `backend/app/`，通过 MQTT 通信。这个决策为后续 Epic 2 的 MQTT 链路奠定了基础
2. **装饰器注册模式**：`@register_adapter("protocol_type")` 在 import 时自动注册，简洁有效。但需要在 `__init__.py` 中显式 import 模块触发注册
3. **存根文件预留**：Story 1.1 创建了 cache.py、mqtt_client.py 等 4 个存根文件，预留了 Epic 2 的模块位置，避免后续冲突

### 反复出现的模式

1. **pymodbus 版本差异**：pymodbus 3.12 的 `FramerType` 导入路径从 `pymodbus` 变为 `pymodbus.framer`，`device_id` 参数实际名为 `slave`
2. **pysnmp 版本升级**：原计划用 pysnmp-lextudio 6.x，实际升级到 pysnmp 7.x（6.x 已弃用），API 从 camelCase 改为 snake_case
3. **lazy logging**：全部适配器统一使用 `%s` 格式而非 f-string，代码审查中多次修复
4. **异常链**：`raise ValueError(...) from e` 保留异常链，代码审查中多次修复

### 代码审查高价值发现

- **1-2 H2**: 允许写入 IR（Input Register）违反 Modbus 协议 → 禁止写入 IR/DI
- **1-2 H3**: 自动类型转换后标记 NORMAL 应为 UNRELIABLE
- **1-4 H1**: pysnmp-lextudio 6.x 已弃用 → 升级 pysnmp 7.x
- **1-5 C1**: `connection_params` 与 DataSource 模型 `connection_config` 字段名不一致 → 统一命名

### 对抗性审查高价值发现

- **1-1 H3**: 干接点类型优先走枚举映射，DI 点位 0/1 正确映射为"开/关"
- **1-5 C2**: API 用 `KNOWN_PROTOCOL_TYPES` 校验包含未实现协议 → 改用 `ADAPTER_REGISTRY`
- **1-6 C1**: DryContactMonitor 用归一化后的 value 做状态比较不可靠 → 改用 raw_value

## 下一步

Epic 2: 网关管理 + MQTT 通信链路 — 6 个 Stories
