import react from '@vitejs/plugin-react';
import process from 'node:process';
import { defineConfig } from 'vitest/config';

// Browser tests point a second dev server at an isolated backend. The backend only trusts the
// default dev origin, so that proxy (and only that one) forwards it; the backend stays strict.
const isolatedApi = process.env.CALIBURN_API_PROXY;

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      '/api': isolatedApi
        ? { target: isolatedApi, headers: { Origin: 'http://127.0.0.1:5173' } }
        : 'http://127.0.0.1:8100',
    },
  },
  test: {
    include: ['src/**/*.test.{ts,tsx}'],
    environment: 'jsdom',
    setupFiles: ['./src/test-setup.ts'],
    restoreMocks: true,
  },
});
