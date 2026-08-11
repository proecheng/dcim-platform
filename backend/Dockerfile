# 后端 Dockerfile — 多阶段构建
FROM python:3.11-slim AS base

WORKDIR /app

# 允许按构建环境覆盖 Debian 镜像，避免默认 CDN 不可达时阻塞构建
ARG DEBIAN_MIRROR=https://mirrors.tuna.tsinghua.edu.cn
ARG PIP_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple

# 安装系统依赖（curl 用于健康检查，libpq-dev 用于 psycopg2）
RUN sed -i "s|http://deb.debian.org|${DEBIAN_MIRROR}|g" /etc/apt/sources.list.d/debian.sources && \
    apt-get update && \
    apt-get install -y --no-install-recommends curl libpq-dev && \
    rm -rf /var/lib/apt/lists/*

# 安装 Python 依赖（不含 ML 可选包，见 requirements-ml.txt）
COPY requirements.txt .
RUN pip install --no-cache-dir --index-url "${PIP_INDEX_URL}" -r requirements.txt

# 复制应用代码
COPY . .

# 暴露端口
EXPOSE 8080

# 健康检查
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD curl -f http://localhost:8080/api/health || exit 1

# 启动命令
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080", "--workers", "2"]
