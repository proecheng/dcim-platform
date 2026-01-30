const express = require('express');
const { createProxyMiddleware } = require('http-proxy-middleware');
const cors = require('cors');
const path = require('path');

const app = express();
const PORT = 3000;
const BACKEND_PORT = 8080;
const BACKEND_URL = 'http://localhost:' + BACKEND_PORT;

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
    ws: true,
    onError: (err, req, res) => {
        console.error('Proxy error: ' + err.message);
        res.status(502).json({ error: 'Backend service unavailable' });
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

// Proxy WebSocket connections
app.use('/ws', createProxyMiddleware({
    target: BACKEND_URL,
    changeOrigin: true,
    ws: true
}));

// Serve static files from frontend dist
const frontendDist = path.join(__dirname, '..', 'frontend', 'dist');
app.use(express.static(frontendDist));

// Fallback to index.html for SPA routing
app.get('*', (req, res) => {
    res.sendFile(path.join(frontendDist, 'index.html'));
});

app.listen(PORT, '0.0.0.0', () => {
    console.log('========================================');
    console.log('   DCIM Proxy Server Started');
    console.log('========================================');
    console.log('   Local:    http://localhost:' + PORT);
    console.log('   Network:  http://0.0.0.0:' + PORT);
    console.log('   Backend:  ' + BACKEND_URL);
    console.log('========================================');
});
