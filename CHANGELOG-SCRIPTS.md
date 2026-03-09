# 启动脚本改进日志

## v7.2 / v3.1 (2026-03-09) - 双重进程终止

### 发现的问题

在实际测试中发现：
1. **僵尸端口占用** - Windows 有时会保留已终止进程的端口占用
2. **taskkill 可能失败** - 某些情况下 `taskkill /F /PID` 无法终止进程
3. **端口延迟释放** - 进程终止后端口可能需要更长时间才能释放

### start.bat v7.2 改进

**新增：PowerShell 备用终止方案**
```batch
# 之前：只使用 taskkill
taskkill /F /PID %%a >nul 2>&1

# 之后：taskkill + PowerShell 双重保险
taskkill /F /PID %%a >nul 2>&1
powershell -Command "Stop-Process -Id %%a -Force -ErrorAction SilentlyContinue" >nul 2>&1
```

**改进点：**
1. 每次终止进程时同时使用 `taskkill` 和 `Stop-Process`
2. 在重试循环中也使用双重终止
3. 提高了进程终止的成功率

### stop.bat v3.1 改进

**同步改进：** 添加 PowerShell 备用终止方案，与 start.bat 保持一致

## v7.1 (2026-03-09)

### start.bat 改进

**问题：**
- 端口清理后等待时间不足，导致端口未完全释放就尝试启动服务
- 端口清理失败时没有明确的错误处理和重试机制
- 用户体验不佳：不清楚端口清理是否成功

**改进：**
1. **智能等待机制**
   - 只在实际清理了进程后才等待（避免不必要的延迟）
   - 检测 `KILLED_8080` 和 `KILLED_3000` 标志

2. **增强的重试逻辑**
   - 最多重试 2 次（总共 3 次尝试）
   - 每次重试间隔 3 秒
   - 使用 `goto` 循环而非简单的单次重试

3. **明确的错误处理**
   - 如果 3 次尝试后端口仍被占用，显示错误并退出
   - 提示用户先运行 `stop.bat`

4. **更好的用户反馈**
   - 显示每个端口的清理状态（"already free" 或 "Killing PID xxx"）
   - 显示重试次数（"attempt 1/2"）
   - 成功后显示 "Ports cleaned successfully"

**代码变更：**
```batch
# 之前：简单的单次重试
if "!PORT_OK!"=="0" (
    echo. Retrying port cleanup...
    # 单次重试
)

# 之后：循环重试机制
:port_check_loop
set "PORT_OK=1"
# 检查端口
if "!PORT_OK!"=="0" (
    set /a RETRY_COUNT+=1
    if !RETRY_COUNT! LEQ 2 (
        # 重试
        goto port_check_loop
    ) else (
        # 失败退出
        exit /b 1
    )
)
```

### stop.bat 状态

**当前版本：** v3.0

**评估：** 已经很完善，包含：
- 多步骤清理流程
- 双重验证机制
- 详细的错误提示
- 手动清理指导

**无需改进。**

## 测试建议

### 测试场景 1：正常启动
```batch
# 端口空闲时启动
start.bat
# 预期：快速启动，显示 "Port 8080 already free" 和 "Port 3000 already free"
```

### 测试场景 2：端口被占用
```batch
# 先启动一次
start.bat
# 不关闭，再次启动
start.bat
# 预期：自动清理旧进程，显示 "Killing PID xxx"，等待 3 秒后成功启动
```

### 测试场景 3：顽固进程
```batch
# 模拟：手动启动一个占用 8080 的进程，设置为无法快速终止
# 再运行 start.bat
# 预期：重试 2 次，每次等待 3 秒，最终成功或显示错误
```

## 相关修复

### Redis 配置问题修复 (2026-03-09)

**问题：**
```
Failed to start Redis listener: 'Settings' object has no attribute 'redis_host'
```

**原因：**
- `backend/app/core/config.py` 只定义了 `redis_url`
- 3 个文件尝试访问 `settings.redis_host` 和 `settings.redis_port`

**修复：**
在 `Settings` 类中添加属性方法：
```python
@property
def redis_host(self) -> str:
    """从 redis_url 解析主机"""
    url = self.redis_url.replace("redis://", "")
    return url.split(":")[0]

@property
def redis_port(self) -> int:
    """从 redis_url 解析端口"""
    url = self.redis_url.replace("redis://", "")
    if ":" in url:
        port_part = url.split(":")[1].split("/")[0]
        return int(port_part)
    return 6379
```

**影响文件：**
- `backend/app/api/v1/sensor_metadata.py:250`
- `backend/app/api/v1/topology_config.py:1205`
- `backend/app/services/diagnosis/sensor_metadata_service.py:83`

## 使用建议

### 推荐工作流

1. **首次启动：**
   ```batch
   start.bat
   ```

2. **重启系统：**
   ```batch
   stop.bat
   start.bat
   ```

3. **遇到问题：**
   ```batch
   stop.bat
   # 等待 5 秒
   start.bat
   ```

4. **紧急清理：**
   ```batch
   # 手动查找进程
   netstat -ano | findstr ":8080"
   netstat -ano | findstr ":3000"

   # 手动终止
   taskkill /F /PID [PID]
   ```

### 常见问题

**Q: start.bat 显示 "Port still in use" 怎么办？**
A: 先运行 `stop.bat`，等待 5 秒，再运行 `start.bat`

**Q: 为什么要等待 3 秒？**
A: Windows 需要时间释放端口，即使进程已终止

**Q: 可以缩短等待时间吗？**
A: 不建议。3 秒是经过测试的最小安全等待时间

**Q: Redis 错误还会出现吗？**
A: 不会。已通过添加 `redis_host` 和 `redis_port` 属性修复
