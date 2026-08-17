const express = require('express');
const { createProxyMiddleware } = require('http-proxy-middleware');
const httpProxy = require('http-proxy');
const cors = require('cors');
const path = require('path');

const CONTENT_SECURITY_POLICY = [
    "default-src 'self'",
    "script-src 'self'",
    "style-src 'self' 'unsafe-inline'",
    "img-src 'self' data: blob:",
    "font-src 'self' data:",
    "connect-src 'self' ws: wss:",
    "object-src 'none'",
    "base-uri 'self'",
    "frame-ancestors 'none'",
    "form-action 'self'"
].join('; ');

function validatePort(value, name) {
    if (!Number.isInteger(value) || value < 1 || value > 65535) {
        throw new Error(`Invalid ${name}: must be 1-65535`);
    }
}

function isLoopback(hostname) {
    const value = hostname.toLowerCase().replace(/^\[|\]$/g, '');
    return value === 'localhost'
        || value === '::1'
        || value.startsWith('127.')
        || value.startsWith('::ffff:7f');
}

function parseAllowedOrigins(rawOrigins, appEnv = 'development') {
    const environment = String(appEnv).trim().toLowerCase();
    if (!['development', 'test', 'production'].includes(environment)) {
        throw new Error('APP_ENV must be development, test, or production');
    }
    const origins = String(rawOrigins || '').split(',').map(value => value.trim()).filter(Boolean);
    if (origins.length === 0) {
        throw new Error('CORS_ORIGINS must contain at least one origin');
    }
    for (const origin of origins) {
        if (origin === '*' || origin === 'null') {
            throw new Error('CORS_ORIGINS cannot contain wildcard or null');
        }
        let parsed;
        try {
            parsed = new URL(origin);
        } catch {
            throw new Error('CORS_ORIGINS contains an invalid origin');
        }
        if (!['http:', 'https:'].includes(parsed.protocol)
            || parsed.username || parsed.password
            || parsed.pathname !== '/' || parsed.search || parsed.hash
            || parsed.origin !== origin) {
            throw new Error('CORS_ORIGINS entries must be exact HTTP(S) origins');
        }
        if (environment === 'production' && isLoopback(parsed.hostname)) {
            throw new Error('Production CORS_ORIGINS cannot contain loopback origins');
        }
    }
    return origins;
}

function createApp({ allowedOrigins, backendUrl, frontendDist }) {
    const app = express();
    const allowedOriginSet = new Set(allowedOrigins);

    app.use((req, res, next) => {
        res.setHeader('Content-Security-Policy', CONTENT_SECURITY_POLICY);
        res.setHeader('X-Content-Type-Options', 'nosniff');
        res.setHeader('X-Frame-Options', 'DENY');
        res.setHeader('Referrer-Policy', 'strict-origin-when-cross-origin');
        res.setHeader('Permissions-Policy', 'camera=(), microphone=(), geolocation=(), payment=(), usb=()');
        next();
    });

    app.use((req, res, next) => {
        const origin = req.get('Origin');
        if (req.method === 'OPTIONS' && origin && !allowedOriginSet.has(origin)) {
            return res.status(403).json({ error: 'Origin not allowed' });
        }
        next();
    });

    app.use(cors({
        origin(origin, callback) {
            callback(null, !origin || allowedOriginSet.has(origin));
        },
        credentials: true,
        methods: ['GET', 'POST', 'PUT', 'DELETE', 'PATCH', 'OPTIONS'],
        allowedHeaders: ['Authorization', 'Content-Type', 'X-Requested-With']
    }));

    app.use((req, res, next) => {
        console.log(`[${new Date().toISOString()}] ${req.method} ${req.url}`);
        next();
    });

    app.get('/health', (req, res) => {
        res.json({ status: 'ok', timestamp: new Date().toISOString() });
    });

    for (const route of ['/api', '/docs', '/openapi.json']) {
        app.use(route, createProxyMiddleware({
            target: backendUrl,
            changeOrigin: true,
            onError: (err, req, res) => {
                console.error(`Proxy error: ${err.message}`);
                if (res && typeof res.status === 'function') {
                    res.status(502).json({ error: 'Backend service unavailable' });
                } else if (res && typeof res.end === 'function') {
                    res.end();
                }
            }
        }));
    }

    app.use(express.static(frontendDist));
    app.get('*', (req, res) => {
        res.sendFile(path.join(frontendDist, 'index.html'));
    });
    return app;
}

function startServer(options = {}) {
    const port = options.port ?? Number.parseInt(process.env.PROXY_PORT || '3000', 10);
    const backendPort = options.backendPort ?? Number.parseInt(process.env.BACKEND_PORT || '8080', 10);
    validatePort(port, 'PROXY_PORT');
    validatePort(backendPort, 'BACKEND_PORT');
    if (port === backendPort) throw new Error('PROXY_PORT and BACKEND_PORT must differ');

    const backendUrl = options.backendUrl || `http://localhost:${backendPort}`;
    const backendWsUrl = options.backendWsUrl || `ws://localhost:${backendPort}`;
    const allowedOrigins = options.allowedOrigins || parseAllowedOrigins(
        process.env.CORS_ORIGINS || 'http://localhost:3000',
        process.env.APP_ENV || 'development'
    );
    const frontendDist = options.frontendDist || path.join(__dirname, '..', 'frontend', 'dist');
    const app = createApp({ allowedOrigins, backendUrl, frontendDist });
    const host = options.host || '0.0.0.0';
    const server = app.listen(port, host, () => {
        console.log(`DCIM proxy listening on http://${host}:${port}, backend=${backendUrl}`);
    });

    const wsProxy = httpProxy.createProxyServer({ target: backendWsUrl, ws: true, changeOrigin: true });
    wsProxy.on('error', (err) => console.error('WebSocket proxy error:', err.message));
    server.on('upgrade', (req, socket, head) => {
        const origin = req.headers.origin;
        if (!req.url.startsWith('/ws') || !origin || !allowedOrigins.includes(origin)) {
            socket.end('HTTP/1.1 403 Forbidden\r\nConnection: close\r\nContent-Length: 0\r\n\r\n');
            return;
        }
        wsProxy.ws(req, socket, head);
    });
    return server;
}

if (require.main === module) {
    try {
        startServer();
    } catch (error) {
        console.error(`[FATAL] ${error.message}`);
        process.exit(1);
    }
}

module.exports = { CONTENT_SECURITY_POLICY, createApp, parseAllowedOrigins, startServer };
