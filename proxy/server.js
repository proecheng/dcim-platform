const express = require('express');
const { createProxyMiddleware } = require('http-proxy-middleware');
const cors = require('cors');
const path = require('path');

const app = express();
const PORT = 3000;
const BACKEND_URL = 'http://localhost:8080';

// 前端静态文件目录
const FRONTEND_DIR = path.join(__dirname, '..', 'frontend', 'dist');

// CORS 配置
app.use(cors());

// API 代理 - 转发到后端
app.use('/api', createProxyMiddleware({
  target: BACKEND_URL,
  changeOrigin: true,
  ws: false,
  onError: (err, req, res) => {
    console.error('Proxy error:', err.message);
    res.status(502).json({ error: 'Backend unavailable', message: err.message });
  },
  onProxyReq: (proxyReq, req, res) => {
    console.log(`[API] ${req.method} ${req.url} -> ${BACKEND_URL}${req.url}`);
  }
}));

// WebSocket 代理
app.use('/ws', createProxyMiddleware({
  target: BACKEND_URL,
  changeOrigin: true,
  ws: true,
  onError: (err, req, res) => {
    console.error('WebSocket proxy error:', err.message);
  }
}));

// 健康检查
app.get('/health', (req, res) => {
  res.json({ status: 'healthy', service: 'proxy', port: PORT });
});

// 静态文件服务（前端资源）
app.use('/assets', express.static(path.join(FRONTEND_DIR, 'assets')));
app.use('/vite.svg', express.static(path.join(FRONTEND_DIR, 'vite.svg')));

// SPA 路由 - 所有其他请求返回 index.html
app.get('*', (req, res) => {
  const indexPath = path.join(FRONTEND_DIR, 'index.html');
  res.sendFile(indexPath, (err) => {
    if (err) {
      console.error('Error serving index.html:', err.message);
      res.status(500).json({ error: 'Frontend not found' });
    }
  });
});

// 启动服务器
const server = app.listen(PORT, '0.0.0.0', () => {
  console.log('========================================');
  console.log('  DCIM Reverse Proxy Server');
  console.log('========================================');
  console.log(`  Proxy Port:   ${PORT}`);
  console.log(`  Backend:      ${BACKEND_URL}`);
  console.log(`  Frontend:     ${FRONTEND_DIR}`);
  console.log(`  Access:       http://localhost:${PORT}`);
  console.log('========================================');
});

// WebSocket 升级处理
server.on('upgrade', (req, socket, head) => {
  if (req.url.startsWith('/ws')) {
    console.log('[WebSocket] Upgrade request:', req.url);
  }
});

// 错误处理
process.on('uncaughtException', (err) => {
  console.error('Uncaught exception:', err);
});

process.on('unhandledRejection', (reason, promise) => {
  console.error('Unhandled rejection:', reason);
});
