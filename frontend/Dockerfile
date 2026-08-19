# 前端 Dockerfile — 多阶段构建
FROM node:22-alpine AS build

ARG VCS_REF=unknown
ARG STORY_SOURCE_SNAPSHOT=unknown

WORKDIR /app

# 安装依赖
COPY package*.json ./
RUN npm ci

# 复制源码并构建
COPY . .
RUN npm run build

# 生产阶段 — Nginx
FROM nginx:alpine

ARG VCS_REF=unknown
ARG STORY_SOURCE_SNAPSHOT=unknown
ARG STORY_39_2_SOURCE_SNAPSHOT=unknown
LABEL org.opencontainers.image.revision="${VCS_REF}" \
      io.dcim.story-39-1.source-snapshot-sha256="${STORY_SOURCE_SNAPSHOT}" \
      io.dcim.story-39-2.source-snapshot-sha256="${STORY_39_2_SOURCE_SNAPSHOT}"

# 复制构建产物
COPY --from=build /app/dist /usr/share/nginx/html

# 复制 Nginx 配置
COPY nginx.conf /etc/nginx/conf.d/default.conf

# 暴露端口
EXPOSE 80

# 健康检查
HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD wget -qO- http://localhost:80/ || exit 1

CMD ["nginx", "-g", "daemon off;"]
