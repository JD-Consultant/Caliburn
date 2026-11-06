import { defineConfig } from '@playwright/test';

function loopbackUrl(name: string): string {
  const value = process.env[name];
  if (!value) throw new Error(`${name} must identify an isolated loopback test service.`);
  const url = new URL(value);
  if (
    url.protocol !== 'http:' ||
    !['127.0.0.1', 'localhost', '[::1]'].includes(url.hostname) ||
    url.username ||
    url.password ||
    url.pathname !== '/' ||
    url.search ||
    url.hash
  ) {
    throw new Error(`${name} must be an HTTP loopback origin without credentials.`);
  }
  return url.origin;
}

// 前後端須明示啟動，並連到獨立的合成資料庫。
const baseURL = loopbackUrl('CALIBURN_E2E_BASE_URL');
loopbackUrl('CALIBURN_E2E_API_URL');

export default defineConfig({
  testDir: './tests/e2e',
  outputDir: './output/e2e-results',
  fullyParallel: false,
  workers: 1,
  retries: 0,
  timeout: 60_000,
  expect: { timeout: 7_000 },
  reporter: [
    ['list'],
    ['html', { outputFolder: 'output/e2e-report', open: 'never' }],
    ['json', { outputFile: 'output/e2e-results.json' }],
  ],
  use: {
    baseURL,
    browserName: 'chromium',
    viewport: { width: 1440, height: 1000 },
    colorScheme: 'light',
    locale: 'zh-TW',
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
    ...(process.env.CALIBURN_E2E_CHROMIUM_PATH
      ? { launchOptions: { executablePath: process.env.CALIBURN_E2E_CHROMIUM_PATH } }
      : {}),
  },
});
