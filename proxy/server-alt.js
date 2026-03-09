const express = require('express'); 
const { createProxyMiddleware } = require('http-proxy-middleware'); 
const httpProxy = require('http-proxy'); 
const cors = require('cors'); 
const path = require('path'); 
 
const app = express(); 
const PORT = 3002; 
const BACKEND_PORT = 8083; 
const BACKEND_URL = 'http://localhost:' + BACKEND_PORT; 
const BACKEND_WS_URL = 'ws://localhost:' + BACKEND_PORT; 
 
app.use(cors({ origin: '*', credentials: true })); 
app.use((req, res, next) => { console.log('[' + new Date().toISOString() + '] ' + req.method + ' ' + req.url); next(); }); 
app.get('/health', (req, res) => { res.json({ status: 'ok', timestamp: new Date().toISOString() }); }); 
app.use('/api', createProxyMiddleware({ target: BACKEND_URL, changeOrigin: true, onError: (err, req, res) => { console.error('Proxy error: ' + err.message); if (res && typeof res.status === 'function') { res.status(502).json({ error: 'Backend service unavailable' }); } else if (res && typeof res.end === 'function') { res.end(); } } })); 
app.use('/docs', createProxyMiddleware({ target: BACKEND_URL, changeOrigin: true })); 
app.use('/openapi.json', createProxyMiddleware({ target: BACKEND_URL, changeOrigin: true })); 
const frontendDist = path.join(__dirname, '..', 'frontend', 'dist'); 
app.use(express.static(frontendDist)); 
app.get('*', (req, res) => { res.sendFile(path.join(frontendDist, 'index.html')); }); 
const server = app.listen(PORT, '0.0.0.0', () => { console.log('========================================'); console.log('   DCIM Proxy Server Started (Alt Ports)'); console.log('========================================'); console.log('   Local:    http://localhost:' + PORT); console.log('   Backend:  http://localhost:' + BACKEND_PORT); console.log('========================================'); }); 
const wsProxy = httpProxy.createProxyServer({ target: BACKEND_WS_URL, ws: true, changeOrigin: true }); 
wsProxy.on('error', (err, req, res) => { console.error('WebSocket proxy error:', err.message); }); 
server.on('upgrade', (req, socket, head) => { if (req.url.startsWith('/ws')) { console.log('[WS] Upgrading:', req.url); wsProxy.ws(req, socket, head); } }); 
