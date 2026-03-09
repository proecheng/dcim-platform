# 系统当前状态

**更新时间：** 2026-03-10
**状态：** ✅ 正常运行

## 服务配置

| 服务 | 端口 | 状态 | 说明 |
|------|------|------|------|
| 后端 (FastAPI) | 8083 | ✅ 运行中 | 使用备用端口避开僵尸端口 8080 |
| 代理 (Express) | 3000 | ✅ 运行中 | **固定端口，不再变动** |

## 访问地址

- **本地访问：** http://localhost:3000
- **远程访问：** http://powerlab.cn:3000
- **API 文档：** http://localhost:8083/docs
- **健康检查：** http://localhost:3000/health

## 关键配置

### 代理配置 (proxy/server.js)

```javascript
const PORT = 3000;           // 固定端口，不变
const BACKEND_PORT = 8083;   // 连接到备用后端端口
```

### 防火墙规则

已配置以下端口的入站规则：
- ✅ 3000 (代理 - 默认端口)
- ✅ 3002 (代理 - 备用端口)
- ✅ 8080 (后端 - 默认端口)
- ✅ 8083 (后端 - 备用端口)

## 端口策略

### 代理端口（固定）
- **始终使用 3000 端口**
- 确保远程访问地址不变
- 用户无需记忆多个端口

### 后端端口（灵活）
- 默认使用 8080
- 遇到僵尸端口时自动切换到 8083
- 代理会自动连接到正确的后端端口

## 启动脚本

### 推荐使用

```batch
start-smart.bat
```

**特点：**
- 自动检测端口冲突
- 代理始终使用 3000 端口
- 后端根据情况选择端口
- 动态生成代理配置

### 备选方案

```batch
start-alt-ports.bat
```

**注意：** 此脚本会将代理启动在 3002 端口，不推荐用于远程访问场景。

## 停止服务

```batch
stop.bat
```

## 问题解决

### 僵尸端口问题

**现象：** 端口 8080 被占用，但进程不存在

**解决方案：**
1. 使用 `start-smart.bat` 自动切换到备用端口
2. 代理保持在 3000 端口不变
3. 只有后端使用备用端口 8083

### 远程访问失败

**检查清单：**
1. 确认代理运行在 3000 端口：`netstat -ano | findstr ":3000"`
2. 确认防火墙规则已启用：`netsh advfirewall firewall show rule name="DCIM Frontend 3000"`
3. 测试本地访问：`curl http://localhost:3000/health`

## 技术细节

### 代理配置逻辑

1. **固定代理端口**
   - proxy/server.js 中 PORT 固定为 3000
   - 不受后端端口变化影响

2. **动态后端连接**
   - BACKEND_PORT 根据实际情况配置
   - 当前连接到 8083

3. **WebSocket 代理**
   - 使用 http-proxy 直接处理 WebSocket 升级
   - 支持 /ws/realtime, /ws/alarms, /ws/system

### 防火墙配置

```batch
# 查看规则
netsh advfirewall firewall show rule name="DCIM Frontend 3000"

# 重新配置（需要管理员权限）
configure-firewall.bat
```

## 验证步骤

### 1. 检查服务状态

```batch
netstat -ano | findstr "LISTENING" | findstr ":3000"
netstat -ano | findstr "LISTENING" | findstr ":8083"
```

### 2. 测试健康检查

```batch
curl http://localhost:3000/health
```

预期输出：
```json
{"status":"ok","timestamp":"2026-03-10T..."}
```

### 3. 测试登录

```batch
curl -X POST http://localhost:3000/api/v1/auth/login ^
  -H "Content-Type: application/x-www-form-urlencoded" ^
  -d "username=admin&password=admin123"
```

预期输出：
```json
{"access_token":"eyJ...","token_type":"bearer",...}
```

### 4. 测试浏览器访问

```batch
start "" "http://localhost:3000"
```

## 相关文档

- `SYSTEM-RUNNING.md` - 系统运行指南
- `REMOTE-SERVER-SOLUTION.md` - 远程服务器解决方案
- `start-smart.bat` - 智能启动脚本
- `configure-firewall.bat` - 防火墙配置脚本

---

**核心原则：** 代理端口固定为 3000，确保远程访问地址不变。后端端口灵活调整，避开僵尸端口问题。
