# 故障排查手册

本文档提供算力中心智能监控系统 (DCIM) 常见问题的诊断和解决方案。

## 快速诊断工具

### 系统健康检查脚本

**Windows (diagnostic.bat):**
```bash
diagnostic.bat
```

**Linux/Mac:**
```bash
#!/bin/bash
echo "=== DCIM 系统诊断 ==="

# 检查端口占用
echo "检查端口占用..."
netstat -tuln | grep -E ":(8080|3000)"

# 检查进程
echo "检查进程..."
ps aux | grep -E "(uvicorn|node)"

# 检查数据库
echo "检查数据库..."
ls -lh dcim.db

# 检查日志
echo "最近错误日志..."
tail -n 20 backend/logs/error.log
```

### 日志位置

| 组件 | 日志路径 | 说明 |
|------|---------|------|
| 后端应用 | `backend/logs/app.log` | 应用运行日志 |
| 后端错误 | `backend/logs/error.log` | 错误和异常 |
| 前端构建 | `frontend/dist/build.log` | 构建日志 |
| Nginx | `/var/log/nginx/error.log` | Nginx 错误 |
| 数据库 | `backend/logs/db.log` | 数据库查询日志 |

## 启动失败问题

### 1. 登录失败 - 500 Internal Server Error

**症状:**
- 浏览器输入用户名密码后返回 500 错误
- 后端日志显示 `ValueError` 或 `AttributeError`

**原因:**
`bcrypt` 库版本 5.0+ 与 `passlib 1.7.4` 不兼容。

**诊断方法:**
```bash
# 测试登录 API
curl -X POST "http://localhost:8080/api/v1/auth/login" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=admin&password=admin123"

# 检查 bcrypt 版本
cd backend
.venv\Scripts\python.exe -c "import bcrypt; print(bcrypt.__version__)"
```

**解决方法:**
```bash
cd backend
.venv\Scripts\python.exe -m pip install "bcrypt==4.0.1"
# 重启后端服务
```

**预防措施:**
在 `requirements.txt` 中锁定版本:
```
bcrypt==4.0.1
passlib==1.7.4
```

### 2. 端口被占用

**症状:**
- 启动时提示 `Address already in use`
- 端口 8080 或 3000 无法绑定

**诊断方法:**
```bash
# Windows
netstat -ano | findstr ":8080" | findstr "LISTENING"
netstat -ano | findstr ":3000" | findstr "LISTENING"

# Linux/Mac
lsof -i :8080
lsof -i :3000
```

**解决方法:**
```bash
# Windows - 杀掉占用进程
taskkill /F /PID <PID>

# Linux/Mac
kill -9 <PID>

# 或使用停止脚本
stop.bat  # Windows
./stop.sh # Linux/Mac
```

**自动化解决:**
在 `start.bat` 中添加端口清理逻辑（已内置）:
```batch
@echo off
echo 清理端口占用...
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":8080" ^| findstr "LISTENING"') do taskkill /F /PID %%a 2>nul
timeout /t 2 /nobreak >nul
```

### 3. 数据库初始化失败

**症状:**
- 启动时报错 `no such table`
- 数据库文件不存在或损坏

**诊断方法:**
```bash
# 检查数据库文件
ls -lh dcim.db

# 检查表结构
sqlite3 dcim.db ".tables"
```

**解决方法:**
```bash
# 方法 1: 运行数据库迁移
cd backend
alembic upgrade head

# 方法 2: 删除数据库重新初始化（会丢失数据）
rm dcim.db
# 重启后端，会自动创建表和初始数据
```

**数据恢复:**
```bash
# 从备份恢复
cp dcim.db.backup dcim.db
```

### 4. Python 虚拟环境问题

**症状:**
- 提示找不到模块 `ModuleNotFoundError`
- 依赖版本冲突

**诊断方法:**
```bash
# 检查虚拟环境是否激活
which python  # Linux/Mac
where python  # Windows

# 检查已安装包
pip list
```

**解决方法:**
```bash
# 重新创建虚拟环境
cd backend
rm -rf .venv
python -m venv .venv
source .venv/bin/activate  # Linux/Mac
.venv\Scripts\activate     # Windows

# 重新安装依赖
pip install -r requirements.txt
```

### 5. Node.js 依赖问题

**症状:**
- `npm install` 失败
- 前端启动报错 `Cannot find module`

**诊断方法:**
```bash
# 检查 Node.js 版本
node --version  # 需要 18+

# 检查 npm 版本
npm --version
```

**解决方法:**
```bash
# 清理缓存
cd frontend
rm -rf node_modules package-lock.json
npm cache clean --force

# 重新安装
npm install

# 如果仍失败，尝试使用 yarn
npm install -g yarn
yarn install
```

## 运行时问题

### 6. 前端修改后不生效

**症状:**
- 修改了前端代码，刷新浏览器没有变化
- 看到的是旧版本页面

**原因:**
`start.bat` 使用静态文件模式，不会自动热更新。

**诊断方法:**
```bash
# 检查 dist 构建时间
ls -la frontend/dist/index.html

# 检查源码修改时间
ls -la frontend/src/views/xxx.vue
```

**解决方法:**
```bash
# 方法 1: 重新构建（适用于演示/测试）
cd frontend
npm run build
# 然后 Ctrl+Shift+R 强制刷新浏览器

# 方法 2: 使用开发模式（推荐前端开发）
cd frontend
npm run dev
# 访问 http://localhost:5173
```

**最佳实践:**
| 场景 | 启动方式 | 更新方式 |
|------|---------|---------|
| 前端开发 | `npm run dev` | 自动热更新 |
| 后端开发 | `start.bat` | 手动 `npm run build` |
| 演示测试 | `start.bat` | 手动 `npm run build` |

### 7. 实时数据不更新

**症状:**
- 仪表盘数据静止不动
- WebSocket 连接失败

**诊断方法:**
```bash
# 检查 WebSocket 连接
# 浏览器控制台查看 Network -> WS 标签

# 检查后端 WebSocket 服务
curl -i -N -H "Connection: Upgrade" \
  -H "Upgrade: websocket" \
  -H "Sec-WebSocket-Version: 13" \
  -H "Sec-WebSocket-Key: test" \
  http://localhost:8080/ws/realtime
```

**常见原因和解决方法:**

**原因 1: JWT Token 过期**
```javascript
// 前端检查 Token
const token = localStorage.getItem('token')
console.log('Token:', token)

// 重新登录获取新 Token
```

**原因 2: 模拟数据未启用**
```env
# .env 文件
SIMULATION_ENABLED=true
DEMO_ENABLED=true
```

**原因 3: Nginx 代理配置错误**
```nginx
# 确保 WebSocket 代理配置正确
location /ws/ {
    proxy_pass http://localhost:8080;
    proxy_http_version 1.1;
    proxy_set_header Upgrade $http_upgrade;
    proxy_set_header Connection "Upgrade";
}
```

### 8. API 请求失败 - CORS 错误

**症状:**
- 浏览器控制台显示 CORS 错误
- API 请求被阻止

**诊断方法:**
```bash
# 检查 CORS 配置
grep CORS_ORIGINS backend/.env
```

**解决方法:**
```env
# 添加前端地址到 CORS 白名单
CORS_ORIGINS=http://localhost:5173,http://localhost:3000,http://your-domain.com
```

重启后端服务生效。

### 9. 数据库查询慢

**症状:**
- 页面加载缓慢
- API 响应时间 > 1 秒

**诊断方法:**
```bash
# 检查数据库大小
ls -lh dcim.db

# 检查表记录数
sqlite3 dcim.db "SELECT COUNT(*) FROM point_history;"
```

**解决方法:**

**方法 1: 清理历史数据**
```bash
# 删除 90 天前的数据
sqlite3 dcim.db "DELETE FROM point_history WHERE timestamp < datetime('now', '-90 days');"

# 优化数据库
sqlite3 dcim.db "VACUUM;"
```

**方法 2: 添加索引**
```sql
CREATE INDEX IF NOT EXISTS idx_point_history_timestamp 
ON point_history(timestamp);

CREATE INDEX IF NOT EXISTS idx_point_history_point_id 
ON point_history(point_id);
```

**方法 3: 升级到 PostgreSQL**
参考 [部署指南](deployment-guide.md) 的数据库配置章节。

### 10. 内存占用过高

**症状:**
- 系统内存占用 > 2 GB
- 服务响应变慢

**诊断方法:**
```bash
# 检查进程内存
ps aux | grep uvicorn
ps aux | grep node

# Linux 查看详细内存
top -p <PID>
```

**解决方法:**

**方法 1: 调整数据保留策略**
```env
DATA_RETENTION_DAYS=30  # 减少到 30 天
```

**方法 2: 启用 Redis 缓存**
```env
REDIS_ENABLED=true
REDIS_URL=redis://localhost:6379/0
```

**方法 3: 限制 Uvicorn Workers**
```bash
# 减少 Worker 数量
uvicorn app.main:app --workers 2
```

## 数据问题

### 11. 告警数据丢失

**症状:**
- 历史告警记录消失
- 告警统计数据不准确

**诊断方法:**
```bash
# 检查告警表
sqlite3 dcim.db "SELECT COUNT(*) FROM alarms;"

# 检查最近告警
sqlite3 dcim.db "SELECT * FROM alarms ORDER BY created_at DESC LIMIT 10;"
```

**可能原因:**
1. 数据库被误删或覆盖
2. 数据保留策略自动清理
3. 数据库迁移失败

**解决方法:**
```bash
# 从备份恢复
cp dcim.db.backup dcim.db

# 检查备份策略
crontab -l | grep backup
```

### 12. 点位数据异常

**症状:**
- 点位值显示为 0 或 null
- 数据突变或跳变

**诊断方法:**
```bash
# 检查点位配置
curl http://localhost:8080/api/v1/points/<point_id>

# 检查最近数据
sqlite3 dcim.db "SELECT * FROM point_history WHERE point_id='<point_id>' ORDER BY timestamp DESC LIMIT 10;"
```

**常见原因:**

**原因 1: 设备通信中断**
- 检查设备在线状态
- 检查网络连接

**原因 2: 点位配置错误**
- 检查点位地址、数据类型
- 检查量程配置

**原因 3: 模拟数据异常**
```bash
# 重启模拟器
curl -X POST http://localhost:8080/api/v1/simulation/restart
```

### 13. 能耗统计不准确

**症状:**
- PUE 值异常（< 1.0 或 > 5.0）
- 能耗统计与实际不符

**诊断方法:**
```bash
# 检查能耗设备配置
curl http://localhost:8080/api/v1/energy/devices

# 检查电价配置
curl http://localhost:8080/api/v1/energy/pricing
```

**解决方法:**
1. 检查 IT 负载和总负载点位配置
2. 确认电价时段配置正确
3. 重新计算统计数据:
   ```bash
   curl -X POST http://localhost:8080/api/v1/energy/recalculate
   ```

## 网络问题

### 14. 无法访问外网 API

**症状:**
- 天气数据获取失败
- 第三方服务调用超时

**诊断方法:**
```bash
# 测试网络连接
ping api.openweathermap.org

# 测试 DNS 解析
nslookup api.openweathermap.org

# 测试 HTTP 请求
curl -v https://api.openweathermap.org
```

**解决方法:**

**方法 1: 配置代理**
```env
HTTP_PROXY=http://proxy.company.com:8080
HTTPS_PROXY=http://proxy.company.com:8080
```

**方法 2: 配置防火墙**
```bash
# 允许出站 HTTPS 连接
sudo ufw allow out 443/tcp
```

### 15. 内网设备无法访问

**症状:**
- Modbus/SNMP 设备连接失败
- 网关离线

**诊断方法:**
```bash
# 测试设备连通性
ping <device_ip>

# 测试端口
telnet <device_ip> 502  # Modbus TCP
nc -zv <device_ip> 161  # SNMP
```

**解决方法:**
1. 检查设备 IP 地址配置
2. 检查防火墙规则
3. 检查网络路由
4. 检查设备协议配置

## 性能问题

### 16. 页面加载慢

**症状:**
- 首次加载时间 > 5 秒
- 页面切换卡顿

**诊断方法:**
```bash
# 浏览器开发者工具 -> Network
# 查看资源加载时间

# 检查静态资源大小
du -sh frontend/dist/*
```

**解决方法:**

**方法 1: 启用 Gzip 压缩**
```nginx
gzip on;
gzip_types text/css application/javascript application/json;
gzip_min_length 1000;
```

**方法 2: 使用 CDN**
```javascript
// vite.config.ts
export default {
  build: {
    rollupOptions: {
      external: ['vue', 'element-plus']
    }
  }
}
```

**方法 3: 代码分割**
```javascript
// router/index.ts
const Dashboard = () => import('@/views/Dashboard.vue')
```

### 17. 大屏卡顿

**症状:**
- 3D 场景帧率低
- ECharts 图表渲染慢

**诊断方法:**
```javascript
// 浏览器控制台
console.log(performance.memory)
```

**解决方法:**

**方法 1: 降低数据更新频率**
```javascript
// 从 1 秒改为 5 秒
const updateInterval = 5000
```

**方法 2: 减少图表数据点**
```javascript
// 只显示最近 100 个点
const maxDataPoints = 100
```

**方法 3: 使用 Canvas 渲染**
```javascript
// ECharts 配置
{
  renderer: 'canvas'  // 替代 'svg'
}
```

## 日志分析

### 常见错误日志

**错误 1: Database is locked**
```
sqlalchemy.exc.OperationalError: (sqlite3.OperationalError) database is locked
```
**原因:** SQLite 并发写入冲突  
**解决:** 升级到 PostgreSQL 或减少并发写入

**错误 2: Connection pool exhausted**
```
sqlalchemy.exc.TimeoutError: QueuePool limit of size 5 overflow 10 reached
```
**原因:** 数据库连接池耗尽  
**解决:** 增加连接池大小或检查连接泄漏

**错误 3: JWT token expired**
```
fastapi.exceptions.HTTPException: 401 Unauthorized
```
**原因:** Token 过期  
**解决:** 前端自动刷新 Token 或重新登录

**错误 4: WebSocket connection closed**
```
websockets.exceptions.ConnectionClosed: code = 1006
```
**原因:** 网络中断或服务重启  
**解决:** 前端实现自动重连机制

## 紧急恢复流程

### 系统完全无法访问

1. **检查服务状态**
   ```bash
   ps aux | grep -E "(uvicorn|node)"
   ```

2. **重启所有服务**
   ```bash
   stop.bat
   start.bat
   ```

3. **检查日志**
   ```bash
   tail -f backend/logs/error.log
   ```

4. **从备份恢复**
   ```bash
   cp dcim.db.backup dcim.db
   ```

### 数据库损坏

1. **尝试修复**
   ```bash
   sqlite3 dcim.db "PRAGMA integrity_check;"
   ```

2. **导出数据**
   ```bash
   sqlite3 dcim.db .dump > dcim_dump.sql
   ```

3. **重建数据库**
   ```bash
   rm dcim.db
   sqlite3 dcim.db < dcim_dump.sql
   ```

### 配置文件丢失

1. **从示例恢复**
   ```bash
   cp .env.example .env
   ```

2. **重新配置关键参数**
   - `SECRET_KEY`
   - `DATABASE_URL`
   - `CORS_ORIGINS`

## 性能调优建议

### 数据库优化

```sql
-- 添加索引
CREATE INDEX idx_alarms_status ON alarms(status);
CREATE INDEX idx_alarms_level ON alarms(level);
CREATE INDEX idx_point_history_timestamp ON point_history(timestamp);

-- 定期清理
DELETE FROM point_history WHERE timestamp < datetime('now', '-90 days');
VACUUM;
```

### 缓存策略

```python
# 启用 Redis 缓存
REDIS_ENABLED=true

# 缓存 TTL 配置
CACHE_TTL_REALTIME=10      # 实时数据 10 秒
CACHE_TTL_STATISTICS=300   # 统计数据 5 分钟
CACHE_TTL_CONFIG=3600      # 配置数据 1 小时
```

### 前端优化

```javascript
// 虚拟滚动（大列表）
import { ElTableV2 } from 'element-plus'

// 防抖/节流
import { debounce, throttle } from 'lodash-es'

// 懒加载
const BigScreen = () => import('@/views/BigScreen.vue')
```

## 监控指标

### 关键指标

| 指标 | 正常范围 | 告警阈值 |
|------|---------|---------|
| CPU 使用率 | < 50% | > 80% |
| 内存使用率 | < 60% | > 85% |
| 磁盘使用率 | < 70% | > 90% |
| API 响应时间 | < 200ms | > 1000ms |
| 数据库连接数 | < 10 | > 20 |
| WebSocket 连接数 | < 100 | > 500 |

### 监控脚本

```bash
#!/bin/bash
# monitor.sh

# CPU
cpu=$(top -bn1 | grep "Cpu(s)" | awk '{print $2}')
echo "CPU: $cpu%"

# 内存
mem=$(free | grep Mem | awk '{print ($3/$2) * 100.0}')
echo "Memory: $mem%"

# 磁盘
disk=$(df -h / | tail -1 | awk '{print $5}')
echo "Disk: $disk"

# 后端进程
backend=$(ps aux | grep uvicorn | grep -v grep | wc -l)
echo "Backend processes: $backend"
```

## 获取帮助

如果以上方法无法解决问题，请:

1. 收集诊断信息:
   ```bash
   diagnostic.bat > diagnostic_report.txt
   ```

2. 导出日志:
   ```bash
   tar -czf logs.tar.gz backend/logs/
   ```

3. 联系技术支持，提供:
   - 问题描述和复现步骤
   - 诊断报告
   - 错误日志
   - 系统环境信息

技术支持邮箱: support@example.com
