# 部署指南

## 数据库准备

1. 启动数据库服务
2. 执行表创建：
   ```python
   from app.db.base import Base
   from app.db.session import engine
   Base.metadata.create_all(bind=engine)
   ```

## 环境变量

```env
DATABASE_URL=postgresql://user:pass@localhost/vpp
SECRET_KEY=your-secret-key
```

## 启动服务

```bash
cd backend
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

## 验证部署

```bash
# 检查 API
curl http://localhost:8000/api/v1/proposals/

# 生成方案
curl -X POST http://localhost:8000/api/v1/proposals/generate \
  -H "Content-Type: application/json" \
  -d '{"template_id": "A1", "analysis_days": 30}'
```

## 核心文件清单

- `app/models/energy.py` - 数据库模型
- `app/schemas/proposal_schema.py` - Pydantic 模式
- `app/services/formula_calculator.py` - 公式计算器
- `app/services/template_generator.py` - 模板生成器
- `app/services/proposal_executor.py` - 方案执行器
- `app/api/v1/proposal.py` - API 端点
