# 后端 Dockerfile — 多阶段构建
FROM python:3.11-slim AS base

ARG VCS_REF=unknown
ARG STORY_SOURCE_SNAPSHOT=unknown
LABEL org.opencontainers.image.revision="${VCS_REF}" \
      io.dcim.story-39-1.source-snapshot-sha256="${STORY_SOURCE_SNAPSHOT}"

WORKDIR /app

# 官方源是可审计默认值；受控环境可显式传入内部镜像。
ARG DEBIAN_MIRROR=
ARG PIP_INDEX_URL=https://pypi.org/simple

# 安装系统依赖（curl 用于健康检查，libpq-dev 用于 psycopg2）
RUN if [ -n "${DEBIAN_MIRROR}" ]; then \
      sed -i "s|http://deb.debian.org|${DEBIAN_MIRROR}|g; s|https://deb.debian.org|${DEBIAN_MIRROR}|g" \
        /etc/apt/sources.list.d/debian.sources; \
    fi && \
    apt-get update && \
    apt-get install -y --no-install-recommends curl libpq-dev && \
    rm -rf /var/lib/apt/lists/*

# 安装 Python 依赖（不含 ML 可选包，见 requirements-ml.txt）
COPY requirements.lock .
RUN pip install --no-cache-dir --require-hashes --index-url "${PIP_INDEX_URL}" -r requirements.lock

# 复制应用代码
COPY . .

# 暴露端口
EXPOSE 8080

# 健康检查
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD curl -f http://localhost:8080/api/health || exit 1

# 启动命令
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080", "--workers", "2"]
