# 远程服务器端口冲突解决方案

**问题：** 僵尸端口占用，无法频繁重启服务器
**日期：** 2026-03-09

## 问题分析

### 根本原因
- Windows TCP/IP 栈的僵尸端口问题
- 进程已终止但端口占用记录未清理
- 远程服务器无法频繁重启

### 当前状态
- 端口 8080 被僵尸进程占用（PID 3916）
- 无法通过 taskkill 或 PowerShell 清理
- 需要不重启服务器的解决方案

## 解决方案

### 方案 1：使用智能启动脚本（推荐）⭐

**文件：** `start-smart.bat`

**特点：**
- 自动检测端口冲突
- 失败时自动切换到备用端口
- 动态生成代理配置
- 无需手动干预

**使用方法：**
```batch
# 双击运行
start-smart.bat
```

**工作流程：**
1. 尝试清理默认端口（8080, 3000）
2. 如果清理失败，自动切换到备用端口（8083, 3002）
3. 动态生成代理配置文件
4. 启动服务

### 方案 2：使用备用端口启动

**文件：** `start-alt-ports.bat`

**特点：**
- 直接使用备用端口（8083, 3002）
- 跳过端口清理步骤
- 快速启动

**使用方法：**
```batch
# 双击运行
start-alt-ports.bat
```

**访问地址：**
- 系统：http://localhost:3002
- API：http://localhost:8083/docs

### 方案 3：手动指定端口

**步骤：**

1. **修改后端端口**
```batch
# 手动启动后端
cd backend
.venv\Scripts\python.exe -m uvicorn app.main:app --host 0.0.0.0 --port 8083
```

2. **修改代理配置**
```javascript
// 编辑 proxy/server.js
const PORT = 3002;           // 改为 3002
const BACKEND_PORT = 8083;   // 改为 8083
```

3. **启动代理**
```batch
cd proxy
node server.js
```

## 文件说明

### 新创建的文件

| 文件 | 说明 | 推荐度 |
|------|------|--------|
| `start-smart.bat` | 智能启动脚本，自动处理端口冲突 | ⭐⭐⭐⭐⭐ |
| `start-alt-ports.bat` | 直接使用备用端口启动 | ⭐⭐⭐⭐ |
| `scripts/clean-ports-enhanced.bat` | 增强的端口清理模块（支持回退） | ⭐⭐⭐⭐⭐ |

### 现有文件

| 文件 | 说明 | 状态 |
|------|------|------|
| `start.bat` (v8.0) | 标准启动脚本 | 遇到僵尸端口会失败 |
| `start-quick.bat` | 快速启动脚本 | 遇到僵尸端口会失败 |
| `stop.bat` (v4.0) | 停止脚本 | 正常工作 |

## 使用建议

### 日常使用（推荐）

```batch
# 使用智能启动脚本
start-smart.bat
```

**优点：**
- 自动处理端口冲突
- 无需手动干预
- 适合远程服务器

### 快速启动

```batch
# 使用备用端口
start-alt-ports.bat
```

**优点：**
- 跳过端口清理
- 启动更快
- 适合开发环境

### 停止服务

```batch
# 使用标准停止脚本
stop.bat
```

## 端口映射

### 默认端口（如果可用）
- 后端：8080
- 代理：3000
- 访问：http://localhost:3000

### 备用端口（冲突时）
- 后端：8083
- 代理：3002
- 访问：http://localhost:3002

### 备用端口 2（如果备用端口也被占用）
- 后端：8084
- 代理：3003
- 访问：http://localhost:3003

## 技术实现

### 智能端口清理

```batch
# 调用增强的端口清理模块
call scripts\clean-ports-enhanced.bat 8080 3000 1
#                                                 ^
#                                                 启用回退模式

# 返回值：
# 0 = 成功清理，使用默认端口
# 2 = 清理失败，切换到备用端口
# 1 = 失败且无回退
```

### 动态代理配置

```batch
# 根据实际端口动态生成 server-dynamic.js
call :create_proxy_config !BACKEND_PORT! !PROXY_PORT!
```

## 故障排查

### 问题 1：智能启动脚本失败

**症状：**
```
[ERROR] Failed to free ports after 3 attempts
```

**解决：**
```batch
# 使用备用端口启动
start-alt-ports.bat
```

### 问题 2：备用端口也被占用

**症状：**
```
Error: listen EADDRINUSE: address already in use 0.0.0.0:8083
```

**解决：**
```batch
# 手动指定更高的端口号
cd backend
.venv\Scripts\python.exe -m uvicorn app.main:app --host 0.0.0.0 --port 8085

# 修改 proxy/server.js 中的 BACKEND_PORT 为 8085
# 然后启动代理
cd proxy
node server.js
```

### 问题 3：服务启动但无法访问

**症状：**
- 服务窗口显示正常
- 浏览器无法访问

**解决：**
```batch
# 检查防火墙设置
# 检查端口是否真的在监听
netstat -ano | findstr "LISTENING" | findstr ":3002"

# 尝试直接访问后端
curl http://localhost:8083/docs
```

## 长期解决方案

### 方案 A：定期清理（推荐）

```batch
# 每天下班前运行
stop.bat

# 等待 10 分钟让 Windows 清理僵尸端口
# 第二天使用智能启动
start-smart.bat
```

### 方案 B：使用不同的端口范围

```batch
# 修改默认端口为更高的端口号
# 例如：18080, 13000
# 这些端口不太可能被其他程序占用
```

### 方案 C：使用 Docker（终极方案）

```dockerfile
# 使用 Docker 容器
# 完全隔离端口问题
# 但需要安装 Docker
```

## 监控和维护

### 检查端口状态

```batch
# 查看所有监听端口
netstat -ano | findstr "LISTENING"

# 查看特定端口
netstat -ano | findstr ":8080"
netstat -ano | findstr ":3000"
```

### 查找僵尸端口

```batch
# 查看端口占用
netstat -ano | findstr ":8080" | findstr "LISTENING"

# 查看进程是否存在
tasklist | findstr "3916"

# 如果进程不存在但端口显示占用 = 僵尸端口
```

### 清理僵尸端口

```batch
# 方法 1：等待（5-10 分钟）
# Windows 会自动清理

# 方法 2：重启网络服务
netsh winsock reset
netsh int ip reset

# 方法 3：重启计算机（最可靠）
```

## 总结

### ✅ 推荐方案

**日常使用：**
```batch
start-smart.bat
```

**优点：**
- 自动处理端口冲突
- 适合远程服务器
- 无需手动干预
- 可靠性高

### 📋 备选方案

**快速启动：**
```batch
start-alt-ports.bat
```

**优点：**
- 跳过端口检查
- 启动更快
- 适合开发环境

### 🎯 核心改进

1. **智能端口管理** - 自动检测和切换
2. **动态配置生成** - 根据实际端口生成配置
3. **无需重启服务器** - 适合远程环境
4. **向后兼容** - 保留所有旧脚本

---

**文档版本：** v1.0
**更新日期：** 2026-03-09
**适用场景：** 远程服务器、无法频繁重启的环境
**推荐脚本：** start-smart.bat ⭐⭐⭐⭐⭐
