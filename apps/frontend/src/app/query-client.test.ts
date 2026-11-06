import { onlineManager } from '@tanstack/react-query';
import { expect, it, vi } from 'vitest';
import { createQueryClient } from './query-client';

it('離線寫入立即嘗試並回報失敗，不留待復線後暗中執行', async () => {
  const cache = createQueryClient();
  const write = vi.fn(() => Promise.reject(new TypeError('Failed to fetch')));
  onlineManager.setOnline(false);
  try {
    const mutation = cache.getMutationCache().build(cache, { mutationFn: write });
    const result = mutation.execute(undefined).catch((error: unknown) => error);
    await Promise.resolve();
    await Promise.resolve();
    expect(mutation.state.isPaused).toBe(false);
    expect(await result).toBeInstanceOf(TypeError);
    onlineManager.setOnline(true);
    await Promise.resolve();
    expect(write).toHaveBeenCalledTimes(1);
  } finally {
    onlineManager.setOnline(true);
    cache.clear();
  }
});
