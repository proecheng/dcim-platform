# Epic 3 回顾：数据源管理 UI + 设备模板

## 完成情况

全部 5 个 Story 完成，实现了数据源前端管理界面、点位批量导入、写入权限管理、设备模板和对接报告导出。

| Story | 标题 | 后端测试 | 前端构建 |
|-------|------|---------|---------|
| 3-1 | 数据源配置管理 | ✅ | ✅ |
| 3-2 | 点位批量导入与预校验 | ✅ | ✅ |
| 3-3 | 只读模式与写入权限管理 | ✅ | ✅ |
| 3-4 | 设备模板管理 | ✅ | ✅ |
| 3-5 | 对接报告导出 | ✅ | ✅ |

## 关键经验教训

### 前后端协作模式

1. **协议动态表单**：根据 protocol_type 动态渲染不同的连接参数表单（Modbus TCP/RTU/SNMP），使用 Vue 3 的 `v-if` 条件渲染。这是项目中首次出现的动态表单模式
2. **Excel 导入/导出**：使用 openpyxl 处理 Excel 文件。导入时先校验再入库（validate → import 两步），校验报告包含行号和字段级错误信息
3. **文件上传限制**：Excel 文件限制 10MB，非 xlsx 格式返回 400。前端使用 el-upload 组件

### 反复出现的模式

1. **FastAPI 路由顺序**：静态路由（`/export-report`、`/test-connection`）必须在参数化路由（`/{datasource_id}`）之前定义，否则会被误匹配。Epic 1 的 Story 1.5 首次发现，本 Epic 继续遵循
2. **操作日志记录**：写入权限变更记录到 OperationLog 表（module/action/old_value/new_value），为后续审计功能铺路
3. **DeviceTemplate 预置点位**：模板的 point_configs 存储为 JSON 字段，从模板创建数据源时自动填充 DataSourcePoint

### 技术模式沉淀

- **地址冲突检测**：点位导入时校验 Excel 内部地址重复 + 与数据库已有地址冲突
- **数据类型白名单**：int16/uint16/int32/uint32/float32/float64/bool/string
- **enum_mapping JSON 校验**：导入时验证 enum_mapping 字段为合法 JSON
- **StreamingResponse 文件下载**：对接报告使用 FastAPI StreamingResponse 返回 Excel 文件流

## 下一步

Epic 4: 实时监控适配 — 5 个 Stories
