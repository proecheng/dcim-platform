import { defineConfig } from '@playwright/test'

const isCI = !!process.env.CI
const configuredBaseURL = process.env.E2E_BASE_URL || 'http://127.0.0.1:3000'
const parsedBaseURL = new URL(configuredBaseURL)
const loopbackHosts = new Set(['127.0.0.1', 'localhost', '::1', '[::1]'])

if (!['http:', 'https:'].includes(parsedBaseURL.protocol)) {
  throw new Error('E2E_BASE_URL must use HTTP or HTTPS')
}
if (parsedBaseURL.username || parsedBaseURL.password || parsedBaseURL.pathname !== '/' || parsedBaseURL.search || parsedBaseURL.hash) {
  throw new Error('E2E_BASE_URL must be an origin without credentials, path, query, or fragment')
}
if (!loopbackHosts.has(parsedBaseURL.hostname)) {
  throw new Error('E2E_BASE_URL must target a loopback address')
}

const baseURL = parsedBaseURL.origin

export default defineConfig({
  testDir: './e2e',
  timeout: 60000,
  retries: 0,
  use: {
    baseURL,
    screenshot: 'only-on-failure',
    trace: 'retain-on-failure',
  },
  projects: [
    {
      name: 'setup',
      testMatch: /auth\.setup\.ts/,
    },
    {
      name: 'chromium',
      use: {
        browserName: 'chromium',
        headless: isCI,
        launchOptions: isCI ? {} : { slowMo: 300 },
        storageState: './e2e/.auth/admin.json',
      },
      dependencies: ['setup'],
      testIgnore: /auth\.setup\.ts/,
    },
  ],
  outputDir: './e2e/test-results',
})
