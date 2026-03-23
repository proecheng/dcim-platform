const express = require('express');
const { createProxyMiddleware } = require('http-proxy-middleware');
const httpProxy = require('http-proxy');
const cors = require('cors');
const path = require('path');

const app = express();
const PORT = parseInt(process.env.PROXY_PORT || '3000', 10);
const BACKEND_PORT = parseInt(process.env.BACKEND_PORT || '8080', 10);

// Validate port values
function validatePort(value, name) {
    if (isNaN(value) || value < 1 || value > 65535) {
        console.error('[FATAL] Invalid ' + name + ': ' + process.env[name] + ' (must be 1-65535)');
        process.exit(1);
    }
}
validatePort(PORT, 'PROXY_PORT');
validatePort(BACKEND_PORT, 'BACKEND_PORT');
if (PORT === BACKEND_PORT) {
    console.error('[FATAL] PROXY_PORT and BACKEND_PORT must differ (both are ' + PORT + ')');
    process.exit(1);
}

const BACKEND_URL = 'http://localhost:' + BACKEND_PORT;
const BACKEND_WS_URL = 'ws://localhost:' + BACKEND_PORT;

// CORS configuration
app.use(cors({
    origin: '*',
    credentials: true
}));

// Logging middleware
app.use((req, res, next) => {
    console.log('[' + new Date().toISOString() + '] ' + req.method + ' ' + req.url);
    next();
});

// Health check endpoint
app.get('/health', (req, res) => {
    res.json({ status: 'ok', timestamp: new Date().toISOString() });
});

// Proxy all /api requests to backend
app.use('/api', createProxyMiddleware({
    target: BACKEND_URL,
    changeOrigin: true,
    onError: (err, req, res) => {
        console.error('Proxy error: ' + err.message);
        if (res && typeof res.status === 'function') {
            res.status(502).json({ error: 'Backend service unavailable' });
        } else if (res && typeof res.end === 'function') {
            res.end();
        }
    }
}));

// Proxy /docs (Swagger) to backend
app.use('/docs', createProxyMiddleware({
    target: BACKEND_URL,
    changeOrigin: true
}));

// Proxy /openapi.json to backend
app.use('/openapi.json', createProxyMiddleware({
    target: BACKEND_URL,
    changeOrigin: true
}));

// Serve static files from frontend dist
const frontendDist = path.join(__dirname, '..', 'frontend', 'dist');
app.use(express.static(frontendDist));

// Fallback to index.html for SPA routing
app.get('*', (req, res) => {
    res.sendFile(path.join(frontendDist, 'index.html'));
});

const server = app.listen(PORT, '0.0.0.0', () => {
    console.log('========================================');
    console.log('   DCIM Proxy Server Started');
    console.log('========================================');
    console.log('   Local:    http://localhost:' + PORT);
    console.log('   Network:  http://0.0.0.0:' + PORT);
    console.log('   Backend:  ' + BACKEND_URL);
    console.log('========================================');
});

// WebSocket proxy using http-proxy directly
const wsProxy = httpProxy.createProxyServer({
    target: BACKEND_WS_URL,
    ws: true,
    changeOrigin: true
});

wsProxy.on('error', (err, req, res) => {
    console.error('WebSocket proxy error:', err.message);
});

server.on('upgrade', (req, socket, head) => {
    if (req.url.startsWith('/ws')) {
        console.log('[WS] Upgrading:', req.url);
        wsProxy.ws(req, socket, head);
    }
});
