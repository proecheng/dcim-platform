# 启动脚本重构说明

## 📋 概述

start.bat 已完成 v6.0 重构，新增数据一致性检查和修复功能，确保系统启动时数据正确绑定。

## 🆕 新增功能

### 1. **数据一致性修复**（Step 5）
- 自动运行 `fix_circuit_bindings.py` 修复 PowerDevice 的 circuit_id 绑定
- 如果数据库被锁定，会在服务启动后重试
- 确保所有设备在配电拓扑中正确显示

### 2. **服务验证**（Post-Start）
- 使用 curl 检查后端和代理服务是否正常响应
- 提供即时反馈，帮助快速发现启动问题

### 3. **数据一致性验证**（Post-Start）
- 自动运行 `verify_data_consistency.py` 验证数据绑定
- 检查 UPS、PowerDevice、配电回路等关键数据
- 发现问题时提供警告信息

### 4. **更完善的错误处理**
- 每个步骤都有错误检查和友好提示
- 端口清理失败时会自动重试
- 提供详细的故障排查指南

## 📂 新增文件

### 1. **maintain.bat** - 维护工具
交互式维护菜单，提供以下功能：

```
1. Fix Data Consistency      - 修复数据一致性
2. Verify Data Consistency   - 验证数据一致性
3. View System Status        - 查看系统状态
4. Clean Database            - 清理数据库（重置为演示数据）
5. Backup Database           - 备份数据库
6. Exit                      - 退出
```

**使用场景**：
- 日常维护和检查
- 数据修复（无需重启服务）
- 数据库备份和重置

### 2. **stop.bat v3.0** - 增强版停止脚本
改进点：
- 更详细的停止过程反馈
- 多次重试机制
- 最终验证和错误提示
- 手动清理指南

## 🔄 启动流程对比

### 旧版本（v5.3）
```
1. 环境检查
2. 端口清理
3. 后端环境
4. 数据库检查
5. 代理服务
6. 前端环境
7. 前端构建
→ 启动服务
```

### 新版本（v6.0）
```
1. 环境检查
2. 端口清理
3. 后端环境
4. 数据库初始化
5. 数据一致性修复 ⭐ 新增
6. 代理服务
7. 前端环境
8. 前端构建
9. 启动服务
→ 服务验证 ⭐ 新增
→ 数据一致性验证 ⭐ 新增
```

## 🎯 解决的问题

### 问题 1：F1 8号UPS 不在配电拓扑中显示
**原因**：PowerDevice.circuit_id = NULL

**解决方案**：
- start.bat 启动时自动运行 `fix_circuit_bindings.py`
- 智能推断并分配正确的 circuit_id
- 验证修复结果

### 问题 2：数据不一致难以发现
**原因**：缺少自动化验证机制

**解决方案**：
- 启动后自动运行 `verify_data_consistency.py`
- 检查 5 个维度的数据一致性
- 发现问题时提供明确的修复建议

### 问题 3：维护操作繁琐
**原因**：需要手动运行多个脚本

**解决方案**：
- 提供 `maintain.bat` 交互式维护工具
- 集成所有常用维护操作
- 自动检查前置条件（如服务是否运行）

## 📊 数据一致性检查项

### 1. UPS 设备一致性
- Device 表 UPS 数量
- UPSDevice 扩展表数量
- PowerDevice 表 UPS 数量
- circuit_id 绑定率

### 2. 配电拓扑一致性
- PowerDevice 总数
- 已绑定 circuit_id 的设备数量
- 配电回路总数

### 3. 设备类型分布
- Device 表设备类型统计
- PowerDevice 表设备类型统计

### 4. 关联关系检查
- PowerDevice 关联 Device 的数量
- monitor_device_id 绑定率

### 5. 特定设备验证
- F1 8号UPS 在各表中的存在性
- circuit_id 绑定状态
- 配电回路信息

## 🚀 使用指南

### 正常启动
```bash
start.bat
```
- 自动完成所有检查和修复
- 打开浏览器访问系统
- 服务窗口保持运行

### 停止服务
```bash
stop.bat
```
- 关闭所有服务窗口
- 清理端口占用
- 验证清理结果

### 日常维护
```bash
maintain.bat
```
- 选择需要的维护操作
- 按提示完成操作
- 无需重启服务（除非必要）

### 数据修复（手动）
```bash
# 1. 停止服务
stop.bat

# 2. 运行修复
cd backend
.venv\Scripts\python.exe scripts\fix_circuit_bindings.py

# 3. 验证结果
.venv\Scripts\python.exe scripts\verify_data_consistency.py

# 4. 重启服务
cd ..
start.bat
```

## ⚠️ 注意事项

### 1. 数据库锁定
如果 start.bat 在 Step 5 显示警告：
```
[WARNING] Data fix encountered issues (may be locked)
Will retry after services start
```

**原因**：数据库被其他进程占用

**解决方案**：
- 运行 `stop.bat` 确保所有服务停止
- 等待 5 秒后重新运行 `start.bat`

### 2. 端口占用
如果端口清理失败：
```
[WARNING] Port 8080 still in use!
```

**解决方案**：
- 手动查找占用进程：`netstat -ano | findstr ":8080"`
- 强制结束进程：`taskkill /F /PID [PID]`
- 或使用 `maintain.bat` 的系统状态功能

### 3. 服务启动慢
如果服务验证显示警告：
```
[WARNING] Backend may not be ready yet
```

**原因**：服务启动需要时间

**解决方案**：
- 等待 10-15 秒后刷新浏览器
- 检查服务窗口是否有错误信息
- 如果持续失败，运行 `stop.bat` 后重试

## 📈 性能优化

### 启动时间对比
- **旧版本**：约 20-25 秒
- **新版本**：约 25-30 秒（增加 5 秒用于数据修复和验证）

### 数据修复效率
- **自动修复**：13 个设备（UPS + 制冷）
- **需手动处理**：119 个设备（PDU、CA 等，因缺少对应回路定义）
- **修复时间**：< 5 秒

## 🔮 未来改进

### 短期（可选）
1. 补充 PDU 和 CA 的回路定义
2. 前端删除确认弹窗优化
3. 添加更多维护工具（日志查看、性能监控等）

### 长期（可选）
1. 图形化维护界面
2. 自动化测试集成
3. 健康检查定时任务
4. 远程维护支持

## 📝 版本历史

### v6.0 (2026-02-28)
- ✨ 新增数据一致性修复（Step 5）
- ✨ 新增服务验证（Post-Start）
- ✨ 新增数据一致性验证（Post-Start）
- ✨ 新增 maintain.bat 维护工具
- 🔧 改进 stop.bat 错误处理
- 📝 完善故障排查指南

### v5.3 (之前)
- 基础启动流程
- 环境检查
- 端口清理
- 依赖安装

## 🤝 贡献

如果发现问题或有改进建议，请：
1. 运行 `maintain.bat` → 选项 2（验证数据一致性）
2. 运行 `maintain.bat` → 选项 3（查看系统状态）
3. 记录错误信息和系统状态
4. 提交问题报告

---

**最后更新**：2026-02-28
**版本**：v6.0
**维护者**：DCIM 开发团队
