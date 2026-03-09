# 系统启动成功 - 使用指南

**日期：** 2026-03-09
**状态：** ✅ 系统正常运行

## 当前运行状态

### 服务信息

| 服务 | 端口 | 状态 | PID |
|------|------|------|-----|
| 后端 (FastAPI) | 8083 | ✅ 运行中 | 6412 |
| 代理 (Express) | 3002 | ✅ 运行中 | - |

### 访问地址

- **系统首页：** http://localhost:3002
- **API 文档：** http://localhost:8083/docs
- **健康检查：** http://localhost:3002/health

### 默认账号

- **用户名：** admin
- **密码：** admin123

## 为什么使用备用端口？

### 问题原因

- 默认端口 8080 被僵尸进程占用（PID 3916）
- 进程已不存在，但端口显示占用
- 这是 Windows TCP/IP 栈的已知问题
- 远程服务器无法频繁重启

### 解决方案

使用备用端口（8083, 3002）启动服务，避开僵尸端口。

## 启动脚本对比

### 推荐使用的脚本

| 脚本 | 说明 | 推荐度 | 适用场景 |
|------|------|--------|----------|
| **start-smart.bat** | 智能启动，自动处理端口冲突 | ⭐⭐⭐⭐⭐ | 日常使用（最推荐） |
| **start-alt-ports.bat** | 直接使用备用端口 | ⭐⭐⭐⭐ | 快速启动 |
| start.bat | 标准启动（v8.0） | ⭐⭐⭐ | 端口空闲时 |
| start-quick.bat | 快速启动（跳过检查） | ⭐⭐⭐ | 开发环境 |

### 脚本说明

#### start-smart.bat（最推荐）⭐⭐⭐⭐⭐

**特点：**
- 自动检测端口冲突
- 失败时自动切换到备用端口
- 动态生成代理配置
- 完全自动化

**使用：**
```batch
start-smart.bat
```

**工作流程：**
1. 尝试清理默认端口（8080, 3000）
2. 如果失败，自动切换到备用端口（8083, 3002）
3. 动态生成代理配置
4. 启动服务

#### start-alt-ports.bat（推荐）⭐⭐⭐⭐

**特点：**
- 直接使用备用端口
- 跳过端口清理
- 启动更快

**使用：**
```batch
start-alt-ports.bat
```

**适用场景：**
- 知道默认端口被占用
- 需要快速启动
- 远程服务器环境

#### start.bat（标准）⭐⭐⭐

**特点：**
- 模块化设计
- 完整的环境检查
- 端口清理

**使用：**
```batch
start.bat
```

**限制：**
- 遇到僵尸端口会失败
- 需要端口空闲

#### start-quick.bat（快速）⭐⭐⭐

**特点：**
- 跳过环境检查
- 跳过依赖安装
- 快速启动

**使用：**
```batch
start-quick.bat
```

**限制：**
- 遇到僵尸端口会失败
- 需要端口空闲

## 停止服务

### 使用 stop.bat

```batch
stop.bat
```

**功能：**
- 关闭服务窗口
- 清理端口占用
- 验证清理结果

### 手动停止

```batch
# 查找进程
netstat -ano | findstr ":8083"
netstat -ano | findstr ":3002"

# 终止进程
taskkill /F /PID [PID]
```

## 日常使用建议

### 场景 1：首次启动

```batch
# 使用智能启动
start-smart.bat
```

### 场景 2：日常开发

```batch
# 早上启动
start-alt-ports.bat

# 开发过程中
# 后端代码会自动重载
# 前端需要重新构建

# 下班前停止
stop.bat
```

### 场景 3：端口已释放

```batch
# 如果僵尸端口已自动清理
start.bat

# 或使用智能启动（自动检测）
start-smart.bat
```

## 常见问题

### Q1：为什么不能使用默认端口？

**A：** 端口 8080 被僵尸进程占用，无法清理。使用备用端口可以避开这个问题。

### Q2：备用端口会一直使用吗？

**A：** 不一定。如果僵尸端口自动清理了（通常 5-10 分钟），可以使用 `start.bat` 或 `start-smart.bat` 恢复使用默认端口。

### Q3：如何知道默认端口是否可用？

**A：** 运行以下命令检查：
```batch
netstat -ano | findstr ":8080" | findstr "LISTENING"
```
如果没有输出，说明端口可用。

### Q4：备用端口也被占用怎么办？

**A：** 修改 `start-alt-ports.bat` 中的端口号：
```batch
# 第 24 行
... --port 8084"  # 改为 8084

# 第 29 行
const PORT = 3003;  # 改为 3003
```

### Q5：如何访问系统？

**A：**
- 当前使用备用端口：http://localhost:3002
- 如果使用默认端口：http://localhost:3000

### Q6：API 文档在哪里？

**A：**
- 当前使用备用端口：http://localhost:8083/docs
- 如果使用默认端口：http://localhost:8080/docs

## 端口映射参考

### 默认端口

| 服务 | 端口 | 说明 |
|------|------|------|
| 后端 | 8080 | FastAPI |
| 代理 | 3000 | Express |

### 备用端口（当前使用）

| 服务 | 端口 | 说明 |
|------|------|------|
| 后端 | 8083 | FastAPI |
| 代理 | 3002 | Express |

### 备用端口 2

| 服务 | 端口 | 说明 |
|------|------|------|
| 后端 | 8084 | FastAPI |
| 代理 | 3003 | Express |

## 验证系统状态

### 检查服务是否运行

```batch
# 检查端口
netstat -ano | findstr "LISTENING" | findstr ":8083"
netstat -ano | findstr "LISTENING" | findstr ":3002"

# 测试健康检查
curl http://localhost:3002/health

# 测试 API
curl http://localhost:8083/docs
```

### 测试登录

```batch
curl -X POST http://localhost:3002/api/v1/auth/login ^
  -H "Content-Type: application/x-www-form-urlencoded" ^
  -d "username=admin&password=admin123"
```

**预期输出：**
```json
{"access_token":"eyJhbGci...","token_type":"bearer"}
```

## 文档参考

- `REMOTE-SERVER-SOLUTION.md` - 远程服务器解决方案
- `STARTUP-GUIDE.md` - 完整启动指南
- `REFACTORING-COMPLETE.md` - 重构完成报告
- `CLAUDE.md` - 项目开发指南

## 技术支持

### 查看日志

- 后端日志：查看后端服务窗口
- 代理日志：查看代理服务窗口

### 回退到旧版本

```batch
# 如果新脚本有问题
start-v7.2.bat
stop-v3.1.bat
```

## 总结

### ✅ 当前状态

- 系统正常运行在备用端口
- 所有功能正常
- 可以正常访问和使用

### 📋 推荐操作

**日常使用：**
```batch
start-smart.bat  # 或 start-alt-ports.bat
```

**停止服务：**
```batch
stop.bat
```

### 🎯 核心优势

1. **无需重启服务器** - 使用备用端口避开僵尸端口
2. **自动化处理** - 智能脚本自动检测和切换
3. **完全兼容** - 所有功能正常工作
4. **易于使用** - 双击启动，简单方便

---

**文档版本：** v1.0
**更新日期：** 2026-03-09
**系统状态：** ✅ 正常运行
**访问地址：** http://localhost:3002
**推荐脚本：** start-smart.bat 或 start-alt-ports.bat
