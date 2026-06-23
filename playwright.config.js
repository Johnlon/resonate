import { defineConfig } from '@playwright/test';

export default defineConfig({
  testDir: './test',
  testMatch: '**/*.browser.spec.js',
  timeout: 15000,
  use: {
    browserName: 'chromium',
    headless: true,
    baseURL: 'http://localhost:7788',
  },
  webServer: {
    command: 'node server.js',
    url: 'http://localhost:7788',
    reuseExistingServer: true,
    timeout: 5000,
  },
});
