# 后端 Dockerfile — 多阶段构建
FROM python:3.11-slim AS base

WORKDIR /app

# 安装系统依赖（curl 用于健康检查，libpq-dev 用于 psycopg2）
RUN apt-get update && \
    apt-get install -y --no-install-recommends curl libpq-dev && \
    rm -rf /var/lib/apt/lists/*

# 安装 Python 依赖（不含 ML 可选包，见 requirements-ml.txt）
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 复制应用代码
COPY . .

# 暴露端口
EXPOSE 8080

# 健康检查
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD curl -f http://localhost:8080/api/health || exit 1

# 启动命令
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080", "--workers", "2"]
