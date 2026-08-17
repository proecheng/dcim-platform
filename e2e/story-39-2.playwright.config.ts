import { defineConfig } from '@playwright/test'

export default defineConfig({
  testDir: '.',
  testMatch: /story-39-2-nginx-security\.spec\.ts/,
  timeout: 30_000,
  retries: 0,
  workers: 1,
  use: {
    browserName: 'chromium',
    headless: true,
  },
})
