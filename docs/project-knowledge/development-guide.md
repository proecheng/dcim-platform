# 开发指南

生成时间: 2026-03-01  
项目版本: V3.2.1

## 环境搭建

### 后端

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate  # Windows
pip install -r requirements.txt
alembic upgrade head
uvicorn app.main:app --reload --host 0.0.0.0 --port 8080
```

### 前端

```bash
cd frontend
npm install
npm run dev  # 开发模式 (http://localhost:5173)
npm run build  # 生产构建
```

## 开发规范

### 后端

- 使用异步数据库操作 (async/await)
- 所有 API 需要权限装饰器
- 使用 Pydantic Schema 验证数据
- 遵循 PEP 8 代码风格
- 编写单元测试 (pytest)

### 前端

- 使用组合式 API (setup script)
- TypeScript 类型安全
- 组件命名: PascalCase
- 文件命名: kebab-case
- 编写单元测试 (vitest)

## 常见问题

### 登录失败 500 错误

原因: bcrypt 版本不兼容  
解决: `pip install "bcrypt==4.0.1"`

### 端口被占用

解决: 运行 `stop.bat` 清理端口

### 前端修改不生效

原因: 使用静态文件模式  
解决: 重新构建 `npm run build` 或使用开发模式 `npm run dev`

## 测试

### 后端测试

```bash
cd backend
pytest  # 全部测试
pytest tests/api/  # API 测试
pytest tests/services/  # 服务层测试
```

### 前端测试

```bash
cd frontend
npm run test  # 运行测试
npm run test:watch  # 监听模式
```

## 更新记录

2026-03-01: 初始版本
