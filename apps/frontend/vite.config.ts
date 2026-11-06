import react from '@vitejs/plugin-react';
import { defineConfig } from 'vitest/config';

export default defineConfig({
  plugins: [react()],
  server: {
    host: '127.0.0.1',
    port: 5174,
    strictPort: true,
    watch: { ignored: ['**/output/**', '**/playwright-report/**', '**/test-results/**'] },
    proxy: {
      '/api': {
        target: process.env.CALIBURN_API_URL ?? 'http://127.0.0.1:8101',
        rewrite: (path) => path.replace(/^\/api/, ''),
      },
    },
  },
  test: {
    maxWorkers: 2,
    environment: 'jsdom',
    setupFiles: ['./tests/setup.ts'],
    include: ['src/**/*.test.{ts,tsx}'],
    restoreMocks: true,
  },
});
