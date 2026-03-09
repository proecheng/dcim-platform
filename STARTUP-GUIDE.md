# DCIM 系统启动指南

**版本：** v8.0 (模块化重构版)
**更新日期：** 2026-03-09

## 快速开始

### 正常启动

```batch
# 双击运行
start.bat
```

这将执行以下步骤：
1. 检查 Python 和 Node.js 环境
2. 清理占用的端口（8080, 3000）
3. 准备后端环境（检查依赖、数据库）
4. 准备代理环境（检查依赖）
5. 准备前端环境（检查依赖、构建）
6. 启动后端和代理服务

### 快速启动（日常开发）

```batch
# 双击运行
start-quick.bat
```

跳过环境检查和依赖安装，直接启动服务。适合日常开发使用。

### 停止服务

```batch
# 双击运行
stop.bat
```

这将：
1. 关闭服务窗口
2. 清理端口占用
3. 验证清理结果

## 访问系统

启动成功后，浏览器会自动打开：

- **系统首页：** http://localhost:3000
- **API 文档：** http://localhost:8080/docs
- **健康检查：** http://localhost:3000/health

**默认账号：**
- 用户名：admin
- 密码：admin123

## 常见问题

### 问题 1：端口被占用

**症状：**
```
[ERROR] Failed to free ports after 3 attempts

This is likely a zombie port issue (Windows TCP/IP stack problem)
```

**原因：**
- 僵尸端口：进程已终止但端口占用记录未清理
- Windows TCP/IP 栈的已知问题

**解决方案：**

**方案 1：等待自动清理（推荐）**
```batch
# 等待 5-10 分钟
# Windows 会自动清理僵尸端口
# 然后再次运行
start.bat
```

**方案 2：重启计算机（最可靠）**
```batch
# 重启计算机
# 然后运行
start.bat
```

**方案 3：检查隐藏进程**
```batch
# 打开任务管理器（Ctrl+Shift+Esc）
# 查看"详细信息"选项卡
# 搜索 python.exe 或 node.exe
# 结束相关进程
# 然后运行
start.bat
```

**方案 4：使用其他端口**
```batch
# 1. 修改 proxy/server.js
const PORT = 3002;           # 改为 3002
const BACKEND_PORT = 8083;   # 改为 8083

# 2. 修改 scripts/clean-ports.bat 的默认端口（第 7-8 行）
if "%PORT_8080%"=="" set "PORT_8080=8083"
if "%PORT_3000%"=="" set "PORT_3000=3002"

# 3. 修改 scripts/start-services.bat 的端口（第 24、29 行）
... --port 8083"
title Proxy [Port 3002]

# 4. 运行
start.bat
```

### 问题 2：Python 或 Node.js 未找到

**症状：**
```
[ERROR] Python not found. Please install Python 3.9+
[ERROR] Node.js not found. Please install Node.js
```

**解决方案：**
```batch
# 安装 Python 3.9+
# 下载：https://www.python.org/downloads/

# 安装 Node.js
# 下载：https://nodejs.org/

# 确保添加到 PATH
# 重新打开命令行窗口
# 运行
start.bat
```

### 问题 3：依赖安装失败

**症状：**
```
[ERROR] Backend dependency installation failed
[ERROR] Frontend dependency installation failed
```

**解决方案：**
```batch
# 检查网络连接
# 手动安装后端依赖
cd backend
.venv\Scripts\python.exe -m pip install -r requirements.txt

# 手动安装前端依赖
cd frontend
npm install

# 手动安装代理依赖
cd proxy
npm install

# 然后运行
start.bat
```

### 问题 4：数据库初始化失败

**症状：**
```
[ERROR] Database initialization failed
```

**解决方案：**
```batch
# 删除旧数据库
cd backend
del dcim.db

# 重新运行
cd ..
start.bat
```

### 问题 5：前端构建失败

**症状：**
```
[ERROR] Frontend build failed
```

**解决方案：**
```batch
# 清理 node_modules
cd frontend
rmdir /s /q node_modules
rmdir /s /q dist

# 重新安装和构建
npm install
npm run build

# 然后运行
cd ..
start.bat
```

### 问题 6：服务启动后立即退出

**症状：**
- 服务窗口闪退
- 无法访问系统

**解决方案：**
```batch
# 查看服务窗口的错误信息
# 或手动启动查看错误

# 手动启动后端
cd backend
.venv\Scripts\python.exe -m uvicorn app.main:app --host 0.0.0.0 --port 8080

# 手动启动代理
cd proxy
node server.js

# 根据错误信息排查问题
```

## 模块独立使用

### 只检查环境

```batch
scripts\check-env.bat
```

### 只清理端口

```batch
scripts\clean-ports.bat 8080 3000
```

### 只准备后端

```batch
scripts\setup-backend.bat
```

### 只准备前端

```batch
scripts\setup-frontend.bat
```

### 只准备代理

```batch
scripts\setup-proxy.bat
```

## 开发模式

### 前端开发（热更新）

```batch
# 启动后端和代理
start-quick.bat

# 在新窗口启动前端开发服务器
cd frontend
npm run dev

# 访问 http://localhost:5173
# 前端代码修改会自动热更新
```

### 后端开发（自动重载）

```batch
# 后端已使用 --reload 模式
# 修改 Python 代码会自动重载
# 无需重启服务
```

## 文件结构

```
mytest1/
├── start.bat              # 主启动脚本 (v8.0)
├── stop.bat               # 停止脚本 (v4.0)
├── start-quick.bat        # 快速启动脚本
├── start-v7.2.bat         # 旧版本备份
├── stop-v3.1.bat          # 旧版本备份
├── scripts/               # 模块目录
│   ├── check-env.bat      # 环境检查模块
│   ├── clean-ports.bat    # 端口清理模块
│   ├── setup-backend.bat  # 后端准备模块
│   ├── setup-proxy.bat    # 代理准备模块
│   ├── setup-frontend.bat # 前端准备模块
│   └── start-services.bat # 服务启动模块
├── backend/               # 后端代码
├── frontend/              # 前端代码
└── proxy/                 # 代理服务
```

## 版本历史

### v8.0 (2026-03-09) - 模块化重构
- 将 389 行的单体脚本拆分为 6 个独立模块
- 主脚本减少到 120 行（-69%）
- 提升可维护性、可测试性、可复用性
- 优化错误信息，提供详细的解决方案

### v7.2 (2026-03-09) - 双重进程终止
- 添加 PowerShell 备用终止方案
- 提高进程终止成功率

### v7.1 (2026-03-09) - 增强端口清理
- 智能等待机制
- 循环重试逻辑（最多 3 次）
- 明确的错误处理

## 技术细节

### 双重进程终止

```batch
# taskkill - Windows 原生命令，快速
taskkill /F /PID %%a >nul 2>&1

# PowerShell Stop-Process - 更强力
powershell -Command "Stop-Process -Id %%a -Force -ErrorAction SilentlyContinue" >nul 2>&1
```

### 循环重试机制

```batch
# 最多重试 2 次（总共 3 次尝试）
set "RETRY_COUNT=0"
:port_check_loop
# ... 检查端口 ...
if !RETRY_COUNT! LEQ 2 (
    # 重试
    goto port_check_loop
)
```

### 模块化设计

- 每个模块职责单一
- 可独立测试和调试
- 可被其他脚本复用
- 使用 exit /b 返回错误码

## 故障排查流程

```
1. 运行 start.bat
   ↓
2. 遇到错误？
   ├─ 端口被占用 → 等待 10 分钟或重启计算机
   ├─ 环境未找到 → 安装 Python/Node.js
   ├─ 依赖安装失败 → 检查网络，手动安装
   ├─ 数据库失败 → 删除 dcim.db 重试
   └─ 其他错误 → 查看错误信息，手动启动排查
   ↓
3. 启动成功
   ↓
4. 访问 http://localhost:3000
```

## 获取帮助

### 查看日志

```batch
# 后端日志
# 查看后端服务窗口的输出

# 代理日志
# 查看代理服务窗口的输出
```

### 查看文档

- `REFACTORING.md` - 重构说明
- `REFACTORING-COMPLETE.md` - 完成报告
- `START-BAT-TEST-REPORT.md` - 详细测试报告
- `START-BAT-FINAL.md` - 测试总结
- `CLAUDE.md` - 项目开发指南

### 回退到旧版本

```batch
# 如果新版本有问题，可以使用旧版本
start-v7.2.bat
stop-v3.1.bat
```

## 最佳实践

### 日常开发

```batch
# 1. 早上启动
start-quick.bat

# 2. 开发过程中
# 后端代码会自动重载
# 前端需要重新构建或使用 npm run dev

# 3. 下班前停止
stop.bat
```

### 首次安装

```batch
# 1. 完整启动（会安装所有依赖）
start.bat

# 2. 等待安装完成
# 3. 访问系统验证
```

### 遇到问题

```batch
# 1. 先尝试停止
stop.bat

# 2. 等待 10 秒
# 3. 再次启动
start.bat

# 4. 如果仍然失败，重启计算机
```

## 注意事项

1. **僵尸端口问题**
   - 这是 Windows 系统问题，不是脚本问题
   - 脚本已经使用了最强的清理逻辑
   - 遇到时请等待或重启计算机

2. **中文乱码**
   - 在 bash 环境下运行时会显示乱码
   - 不影响功能
   - 建议在 cmd.exe 中运行

3. **端口占用**
   - 默认使用 8080 和 3000 端口
   - 如需修改，参考"问题 1：端口被占用"的方案 4

4. **数据库**
   - 使用 SQLite，数据库文件：backend/dcim.db
   - 删除后会自动重新创建

5. **前端构建**
   - start.bat 会检查 dist 目录
   - 如果不存在会自动构建
   - 构建时间约 30 秒

---

**文档版本：** v1.0
**更新日期：** 2026-03-09
**适用版本：** start.bat v8.0, stop.bat v4.0
