import { defineConfig, devices } from '@playwright/test';
import process from 'node:process';

// Deliberately no default: these tests create synthetic files in the selected test App.
const baseURL = process.env.CALIBURN_E2E_BASE_URL;
if (!baseURL) throw new Error('Set CALIBURN_E2E_BASE_URL to an isolated local test App.');
const target = new URL(baseURL);
if (target.protocol !== 'http:' || !['127.0.0.1', 'localhost', '[::1]'].includes(target.hostname)) {
  throw new Error('Browser tests only target an explicit loopback HTTP App.');
}
const chromiumPath = process.env.CALIBURN_E2E_CHROMIUM_PATH;

export default defineConfig({
  testDir: './tests/e2e',
  fullyParallel: false,
  workers: 1,
  retries: 0,
  timeout: 30_000,
  use: {
    baseURL,
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
    // Optional verified binary of this Playwright release, not the user's browser profile.
    launchOptions: chromiumPath ? { executablePath: chromiumPath } : {},
  },
  projects: [{ name: 'chromium', use: { ...devices['Desktop Chrome'] } }],
});
