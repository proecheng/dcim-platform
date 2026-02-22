#!/bin/bash
# DCIM HTTPS + WSS 部署脚本
# 在 powerlab.cn 服务器上以 root 执行
#
# 用法：bash deploy-https.sh [域名]
# 示例：bash deploy-https.sh dcim.powerlab.cn

set -e

DOMAIN="${1:-dcim.powerlab.cn}"
NGINX_CONF="/etc/nginx/conf.d/dcim.conf"
CERTBOT_WEBROOT="/var/www/certbot"

echo "========================================="
echo "  DCIM HTTPS 部署"
echo "  域名: $DOMAIN"
echo "========================================="

# ── 1. 检查 nginx ──
if ! command -v nginx &>/dev/null; then
    echo "[1/5] 安装 nginx..."
    if command -v apt &>/dev/null; then
        apt update && apt install -y nginx
    elif command -v yum &>/dev/null; then
        yum install -y nginx
    else
        echo "错误：无法识别包管理器，请手动安装 nginx"
        exit 1
    fi
else
    echo "[1/5] nginx 已安装: $(nginx -v 2>&1)"
fi

# ── 2. 安装 certbot ──
if ! command -v certbot &>/dev/null; then
    echo "[2/5] 安装 certbot..."
    if command -v apt &>/dev/null; then
        apt install -y certbot python3-certbot-nginx
    elif command -v yum &>/dev/null; then
        yum install -y certbot python3-certbot-nginx
    fi
else
    echo "[2/5] certbot 已安装: $(certbot --version 2>&1)"
fi

# ── 3. 先部署 HTTP-only 配置（用于 certbot 验证）──
echo "[3/5] 部署临时 HTTP 配置..."
mkdir -p "$CERTBOT_WEBROOT"

cat > "$NGINX_CONF" <<NGINX_HTTP
server {
    listen 80;
    server_name $DOMAIN;

    location /.well-known/acme-challenge/ {
        root $CERTBOT_WEBROOT;
    }

    location / {
        proxy_pass http://127.0.0.1:3000;
        proxy_http_version 1.1;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header Upgrade \$http_upgrade;
        proxy_set_header Connection "upgrade";
    }
}
NGINX_HTTP

nginx -t && systemctl reload nginx
echo "  临时 HTTP 配置已生效"

# ── 4. 申请 SSL 证书 ──
echo "[4/5] 申请 Let's Encrypt 证书..."
if [ -d "/etc/letsencrypt/live/$DOMAIN" ]; then
    echo "  证书已存在，跳过申请"
else
    certbot certonly \
        --webroot \
        --webroot-path "$CERTBOT_WEBROOT" \
        -d "$DOMAIN" \
        --non-interactive \
        --agree-tos \
        --email admin@powerlab.cn \
        --no-eff-email

    if [ $? -ne 0 ]; then
        echo ""
        echo "========================================="
        echo "  证书申请失败！"
        echo "  请确认："
        echo "  1. 域名 $DOMAIN 已解析到本服务器 IP"
        echo "  2. 80 端口可从外网访问"
        echo "  3. 防火墙允许 80/443 入站"
        echo "========================================="
        exit 1
    fi
fi

# ── 5. 部署完整 HTTPS + WSS 配置 ──
echo "[5/5] 部署 HTTPS + WSS 配置..."

cat > "$NGINX_CONF" <<'NGINX_HTTPS'
# DCIM HTTPS + WSS 反向代理
# 自动生成，请勿手动编辑

server {
    listen 80;
    server_name DOMAIN_PLACEHOLDER;

    location /.well-known/acme-challenge/ {
        root /var/www/certbot;
    }

    location / {
        return 301 https://$host$request_uri;
    }
}

server {
    listen 443 ssl http2;
    server_name DOMAIN_PLACEHOLDER;

    ssl_certificate     /etc/letsencrypt/live/DOMAIN_PLACEHOLDER/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/DOMAIN_PLACEHOLDER/privkey.pem;

    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers ECDHE-ECDSA-AES128-GCM-SHA256:ECDHE-RSA-AES128-GCM-SHA256:ECDHE-ECDSA-AES256-GCM-SHA384:ECDHE-RSA-AES256-GCM-SHA384;
    ssl_prefer_server_ciphers on;
    ssl_session_cache shared:SSL:10m;
    ssl_session_timeout 10m;

    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;
    add_header X-Content-Type-Options nosniff always;
    add_header X-Frame-Options SAMEORIGIN always;

    access_log /var/log/nginx/dcim_access.log;
    error_log  /var/log/nginx/dcim_error.log;

    # WebSocket（WSS）转发 — 关键配置
    location /ws/ {
        proxy_pass http://127.0.0.1:3000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 86400s;
        proxy_send_timeout 86400s;
    }

    # API 转发
    location /api/ {
        proxy_pass http://127.0.0.1:3000;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 60s;
        proxy_connect_timeout 10s;
    }

    # Swagger
    location /docs {
        proxy_pass http://127.0.0.1:3000;
        proxy_set_header Host $host;
    }

    location /openapi.json {
        proxy_pass http://127.0.0.1:3000;
        proxy_set_header Host $host;
    }

    # 前端静态文件
    location / {
        proxy_pass http://127.0.0.1:3000;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
NGINX_HTTPS

# 替换域名占位符
sed -i "s/DOMAIN_PLACEHOLDER/$DOMAIN/g" "$NGINX_CONF"

nginx -t && systemctl reload nginx

# ── 6. 设置证书自动续期 ──
if ! crontab -l 2>/dev/null | grep -q certbot; then
    (crontab -l 2>/dev/null; echo "0 3 * * * certbot renew --quiet --post-hook 'systemctl reload nginx'") | crontab -
    echo "  已添加证书自动续期 cron（每天凌晨3点）"
fi

echo ""
echo "========================================="
echo "  部署完成！"
echo "========================================="
echo "  HTTPS:  https://$DOMAIN"
echo "  WSS:    wss://$DOMAIN/ws/system"
echo "  API:    https://$DOMAIN/api/v1/"
echo "  Swagger: https://$DOMAIN/docs"
echo ""
echo "  验证命令："
echo "    curl -sI https://$DOMAIN/"
echo "    curl -sv -H 'Upgrade: websocket' -H 'Connection: Upgrade' \\"
echo "      -H 'Sec-WebSocket-Version: 13' -H 'Sec-WebSocket-Key: dGVzdA==' \\"
echo "      https://$DOMAIN/ws/system"
echo "========================================="
