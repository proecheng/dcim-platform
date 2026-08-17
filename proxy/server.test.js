const assert = require('node:assert/strict');
const http = require('node:http');
const { after, before, describe, it } = require('node:test');

const { createApp, parseAllowedOrigins, startServer } = require('./server');

function websocketUpgrade(port, origin) {
    return new Promise((resolve, reject) => {
        const request = http.request({
            host: '127.0.0.1',
            port,
            path: '/ws/realtime',
            headers: {
                Connection: 'Upgrade',
                Upgrade: 'websocket',
                Origin: origin,
                'Sec-WebSocket-Key': 'dGhlIHNhbXBsZSBub25jZQ==',
                'Sec-WebSocket-Version': '13'
            }
        });
        request.on('response', response => resolve(response.statusCode));
        request.on('upgrade', () => resolve(101));
        request.on('error', reject);
        request.end();
    });
}

describe('proxy security boundary', () => {
    let baseUrl;
    let server;

    before(async () => {
        const app = createApp({
            allowedOrigins: ['https://dcim.example.com'],
            backendUrl: 'http://127.0.0.1:1',
            frontendDist: __dirname
        });
        await new Promise(resolve => {
            server = app.listen(0, '127.0.0.1', () => {
                baseUrl = `http://127.0.0.1:${server.address().port}`;
                resolve();
            });
        });
    });

    after(async () => {
        await new Promise(resolve => server.close(resolve));
    });

    it('allows configured credentialed origins and emits security headers', async () => {
        const response = await fetch(`${baseUrl}/health`, {
            headers: { Origin: 'https://dcim.example.com' }
        });

        assert.equal(response.status, 200);
        assert.equal(response.headers.get('access-control-allow-origin'), 'https://dcim.example.com');
        assert.equal(response.headers.get('access-control-allow-credentials'), 'true');
        assert.match(response.headers.get('vary'), /Origin/);
        assert.match(response.headers.get('content-security-policy'), /script-src 'self'/);
        assert.doesNotMatch(response.headers.get('content-security-policy'), /script-src[^;]*'unsafe-inline'/);
        assert.equal(response.headers.get('x-content-type-options'), 'nosniff');
        assert.equal(response.headers.get('x-frame-options'), 'DENY');
        assert.equal(response.headers.get('referrer-policy'), 'strict-origin-when-cross-origin');
        assert.ok(response.headers.get('permissions-policy'));
    });

    it('allows configured preflight without using wildcard ACAO', async () => {
        const response = await fetch(`${baseUrl}/health`, {
            method: 'OPTIONS',
            headers: {
                Origin: 'https://dcim.example.com',
                'Access-Control-Request-Method': 'GET'
            }
        });

        assert.equal(response.status, 204);
        assert.equal(response.headers.get('access-control-allow-origin'), 'https://dcim.example.com');
        assert.notEqual(response.headers.get('access-control-allow-origin'), '*');
    });

    it('rejects unconfigured preflight and withholds ACAO from simple requests', async () => {
        const preflight = await fetch(`${baseUrl}/health`, {
            method: 'OPTIONS',
            headers: {
                Origin: 'https://evil.example',
                'Access-Control-Request-Method': 'GET'
            }
        });
        const simple = await fetch(`${baseUrl}/health`, {
            headers: { Origin: 'https://evil.example' }
        });

        assert.equal(preflight.status, 403);
        assert.equal(preflight.headers.get('access-control-allow-origin'), null);
        assert.equal(simple.status, 200);
        assert.equal(simple.headers.get('access-control-allow-origin'), null);
    });
});

describe('proxy origin parser', () => {
    it('rejects wildcards, null, paths, credentials, and production loopback', () => {
        for (const value of [
            '*',
            'null',
            'https://good.example/path',
            'https://good.example/',
            'https://good.example:443',
            'https://GOOD.example',
            'https://user@good.example'
        ]) {
            assert.throws(() => parseAllowedOrigins(value, 'development'));
        }
        assert.throws(() => parseAllowedOrigins('http://localhost:3000', 'production'));
        assert.throws(() => parseAllowedOrigins('http://[::1]:3000', 'production'));
        assert.throws(() => parseAllowedOrigins('http://127.1:3000', 'production'));
        assert.throws(() => parseAllowedOrigins('http://2130706433:3000', 'production'));
        assert.throws(() => parseAllowedOrigins('http://localhost:3000', ' Production '));
        assert.throws(() => parseAllowedOrigins('https://dcim.example.com', 'prod'), /APP_ENV/);
    });
});

describe('proxy WebSocket origin boundary', () => {
    it('rejects unconfigured WebSocket origins before proxying upstream', async () => {
        const server = startServer({
            port: 31992,
            host: '127.0.0.1',
            backendPort: 31993,
            allowedOrigins: ['https://dcim.example.com'],
            frontendDist: __dirname
        });
        try {
            const status = await websocketUpgrade(31992, 'https://evil.example');
            assert.equal(status, 403);
        } finally {
            await new Promise(resolve => server.close(resolve));
        }
    });
});
