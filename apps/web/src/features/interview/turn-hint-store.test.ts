/** The tab's tracked Turn identity is an external store: readers subscribe instead of copying it. */
import { beforeEach, expect, test, vi } from 'vitest';
import {
  clearTurnHint,
  readTurnHintSnapshot,
  retainTurnHint,
  resolveTurnHint,
  clearDeletedInterview,
  subscribeTurnHint,
} from './interview-turn-api';

const fileId = '10000000-0000-4000-8000-000000000001';
const hint = {
  command_id: '60000000-0000-4000-8000-000000000006',
  execution_id: '50000000-0000-4000-8000-000000000005',
};

beforeEach(() => {
  localStorage.clear();
});

test('an empty store reads as null and an unchanged stored hint keeps one snapshot object', async () => {
  expect(readTurnHintSnapshot(fileId)).toBeNull();
  await retainTurnHint(fileId, hint);
  const first = readTurnHintSnapshot(fileId);
  expect(first).toEqual(hint);
  expect(readTurnHintSnapshot(fileId)).toBe(first);
});

test('writing or clearing the hint notifies subscribers; clearing another command does not', async () => {
  const listener = vi.fn();
  const unsubscribe = subscribeTurnHint(listener);
  await retainTurnHint(fileId, hint);
  expect(listener).toHaveBeenCalledTimes(1);
  await clearTurnHint(fileId, '70000000-0000-4000-8000-000000000007');
  expect(listener).toHaveBeenCalledTimes(1);
  await clearTurnHint(fileId, hint.command_id);
  expect(listener).toHaveBeenCalledTimes(2);
  expect(readTurnHintSnapshot(fileId)).toBeNull();
  unsubscribe();
  await retainTurnHint(fileId, hint);
  expect(listener).toHaveBeenCalledTimes(2);
});

test('another tab writing the hint reaches subscribers through the storage event', () => {
  const listener = vi.fn();
  const unsubscribe = subscribeTurnHint(listener);
  window.dispatchEvent(new StorageEvent('storage', { key: `caliburn:interview-turn:${fileId}` }));
  expect(listener).toHaveBeenCalledTimes(1);
  unsubscribe();
});

test('a corrupt stored hint reads as null; the composer reports that corruption itself', () => {
  localStorage.setItem(`caliburn:interview-turn:${fileId}`, '{not json');
  expect(readTurnHintSnapshot(fileId)).toBeNull();
});

test('a competing reservation never replaces an unresolved command', async () => {
  await retainTurnHint(fileId, hint);
  await expect(
    retainTurnHint(fileId, { ...hint, command_id: '70000000-0000-4000-8000-000000000007' }),
  ).rejects.toThrow();
  expect(readTurnHintSnapshot(fileId)).toEqual(hint);
});

test('retrying a command preserves its already resolved execution', async () => {
  await retainTurnHint(fileId, hint);
  await retainTurnHint(fileId, { ...hint, execution_id: null });
  expect(readTurnHintSnapshot(fileId)).toEqual(hint);
});

test('two simultaneous pages reserve only one original command', async () => {
  const second = { ...hint, command_id: '70000000-0000-4000-8000-000000000007' };
  const results = await Promise.allSettled([
    retainTurnHint(fileId, hint),
    retainTurnHint(fileId, second),
  ]);
  expect(results.map((result) => result.status)).toEqual(['fulfilled', 'rejected']);
  expect(readTurnHintSnapshot(fileId)).toEqual(hint);
});

test('an old ACK neither recreates a cleared hint nor replaces a newer command', async () => {
  await retainTurnHint(fileId, { ...hint, execution_id: null });
  await clearTurnHint(fileId, hint.command_id);
  await resolveTurnHint(fileId, hint);
  expect(readTurnHintSnapshot(fileId)).toBeNull();
  const next = { ...hint, command_id: '70000000-0000-4000-8000-000000000007', execution_id: null };
  await retainTurnHint(fileId, next);
  await resolveTurnHint(fileId, hint);
  expect(readTurnHintSnapshot(fileId)).toEqual(next);
});

test('resolved execution is never replaced by a different execution ACK', async () => {
  await retainTurnHint(fileId, hint);
  await resolveTurnHint(fileId, { ...hint, execution_id: '80000000-0000-4000-8000-000000000008' });
  expect(readTurnHintSnapshot(fileId)).toEqual(hint);
});

test('a completed hint may be replaced only if both stored identities still match', async () => {
  await retainTurnHint(fileId, hint);
  const next = { command_id: '70000000-0000-4000-8000-000000000007', execution_id: null };
  await expect(retainTurnHint(fileId, next, { ...hint, execution_id: null })).rejects.toThrow();
  await retainTurnHint(fileId, next, hint);
  expect(readTurnHintSnapshot(fileId)).toEqual(next);
});

test('confirmed deletion and a late ACK share the same lock and leave no hint', async () => {
  await retainTurnHint(fileId, { ...hint, execution_id: null });
  await Promise.all([clearDeletedInterview(fileId), resolveTurnHint(fileId, hint)]);
  expect(readTurnHintSnapshot(fileId)).toBeNull();
});

test('an unavailable Web Locks API blocks writes while reads remain available', async () => {
  const original = navigator.locks;
  Object.defineProperty(navigator, 'locks', { configurable: true, value: undefined });
  try {
    expect(readTurnHintSnapshot(fileId)).toBeNull();
    await expect(retainTurnHint(fileId, hint)).rejects.toThrow('Web Locks unavailable');
    expect(readTurnHintSnapshot(fileId)).toBeNull();
  } finally {
    Object.defineProperty(navigator, 'locks', { configurable: true, value: original });
  }
});

test('waiting for a held hint lock aborts after five seconds without writing', async () => {
  vi.useFakeTimers();
  let release: () => void = () => {};
  const held = navigator.locks.request(
    `caliburn:interview-turn:${fileId}`,
    { mode: 'exclusive' },
    () =>
      new Promise<void>((resolve) => {
        release = resolve;
      }),
  );
  await Promise.resolve();
  await Promise.resolve();
  const rejected = expect(retainTurnHint(fileId, hint)).rejects.toMatchObject({
    name: 'AbortError',
  });
  try {
    await vi.advanceTimersByTimeAsync(5_000);
    await rejected;
    expect(readTurnHintSnapshot(fileId)).toBeNull();
  } finally {
    release();
    await held;
    vi.useRealTimers();
  }
});

test('aborting a queued waiter does not release another page held lock', async () => {
  vi.useFakeTimers();
  let release: () => void = () => {};
  const held = navigator.locks.request(
    'caliburn:interview-turn:' + fileId,
    { mode: 'exclusive' },
    () =>
      new Promise<void>((resolve) => {
        release = resolve;
      }),
  );
  await Promise.resolve();
  await Promise.resolve();
  const rejected = expect(retainTurnHint(fileId, hint)).rejects.toMatchObject({
    name: 'AbortError',
  });
  let next: Promise<void> = Promise.resolve();
  try {
    await vi.advanceTimersByTimeAsync(5_000);
    await rejected;
    next = retainTurnHint(fileId, hint);
    await vi.advanceTimersByTimeAsync(0);
    expect(readTurnHintSnapshot(fileId)).toBeNull();
  } finally {
    release();
    await held;
    await next;
    vi.useRealTimers();
  }
});
