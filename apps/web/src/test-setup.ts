import '@testing-library/jest-dom/vitest';
import { cleanup } from '@testing-library/react';
import { afterEach } from 'vitest';

afterEach(cleanup);

// Browser I/O boundary: serialize named locks and abort queued acquisition like Web Locks.
const queues = new Map<string, Promise<unknown>>();
Object.defineProperty(navigator, 'locks', {
  configurable: true,
  value: {
    async request<T>(
      name: string,
      options: { signal?: AbortSignal },
      action: () => T | Promise<T>,
    ): Promise<T> {
      const previous = queues.get(name) ?? Promise.resolve();
      let release: () => void = () => {};
      const current = new Promise<void>((resolve) => {
        release = resolve;
      });
      const tail = previous.catch(() => {}).then(() => current);
      queues.set(name, tail);
      void tail.then(() => {
        if (queues.get(name) === tail) queues.delete(name);
      });
      try {
        await new Promise<void>((resolve, reject) => {
          const abort = () => reject(new DOMException('Lock acquisition aborted', 'AbortError'));
          options.signal?.addEventListener('abort', abort, { once: true });
          void previous.then(() => {
            options.signal?.removeEventListener('abort', abort);
            if (options.signal?.aborted) abort();
            else resolve();
          });
        });
        return await action();
      } finally {
        release();
      }
    },
  },
});
