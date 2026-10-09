import react from '@vitejs/plugin-react';
import process from 'node:process';
import { defineConfig } from 'vitest/config';

// An isolated backend explicitly trusts its frontend via CALIBURN_DEV_ORIGIN.
// Preserve the real Origin so the backend can reject untrusted requests.
const isolatedApi = process.env.CALIBURN_API_PROXY;

export default defineConfig({
  plugins: [react()],
  server: {
    headers: { 'Content-Security-Policy': "frame-ancestors 'none'" },
    proxy: {
      '/api': isolatedApi ?? 'http://127.0.0.1:8100',
    },
  },
  test: {
    include: ['src/**/*.test.{ts,tsx}'],
    environment: 'jsdom',
    setupFiles: ['./src/test-setup.ts'],
    restoreMocks: true,
  },
});
