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
const authFile = process.env.E2E_AUTH_FILE || './e2e/.auth/admin.json'
const outputDir = process.env.E2E_OUTPUT_DIR || './e2e/test-results'
const browserChannel = process.env.E2E_BROWSER_CHANNEL as
  | 'chrome'
  | 'chrome-beta'
  | 'chrome-dev'
  | 'chrome-canary'
  | 'msedge'
  | 'msedge-beta'
  | 'msedge-dev'
  | 'msedge-canary'
  | undefined

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
        channel: browserChannel,
        headless: isCI,
        launchOptions: isCI ? {} : { slowMo: 300 },
        storageState: authFile,
      },
      dependencies: ['setup'],
      testIgnore: /auth\.setup\.ts/,
    },
  ],
  outputDir,
})
