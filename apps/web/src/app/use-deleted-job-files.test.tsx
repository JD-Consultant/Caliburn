import type { ReactNode } from 'react';
import { QueryClientProvider, type QueryClient } from '@tanstack/react-query';
import { act, renderHook, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, expect, test, vi } from 'vitest';
import { retainTurnHint } from '../features/interview/interview-turn-api';
import { createAppQueryClient } from './query-client';
import { useDeletedJobFiles } from './use-deleted-job-files';

const firstId = '10000000-0000-4000-8000-000000000001';
const secondId = '20000000-0000-4000-8000-000000000002';
const clients: QueryClient[] = [];

function pendingKey(jobFileId: string) {
  return `caliburn.pending-jd-profile.${jobFileId}`;
}

function mountDeletion() {
  const client = createAppQueryClient();
  clients.push(client);
  const view = renderHook(useDeletedJobFiles, {
    wrapper: ({ children }: { children: ReactNode }) => (
      <QueryClientProvider client={client}>{children}</QueryClientProvider>
    ),
    reactStrictMode: true,
  });
  return { ...view, client };
}

/** Native messaging boundary; feature cleanup and QueryClient remain real. */
function stubChannel() {
  const connections: {
    onmessage: ((event: MessageEvent<unknown>) => void) | null;
    postMessage: ReturnType<typeof vi.fn>;
    close: ReturnType<typeof vi.fn>;
  }[] = [];
  vi.stubGlobal(
    'BroadcastChannel',
    vi.fn(function () {
      const connection = { onmessage: null, postMessage: vi.fn(), close: vi.fn() };
      connections.push(connection);
      return connection;
    }),
  );
  return connections;
}

function denySessionRemoval(keys: ReadonlySet<string>) {
  const removeSession = Storage.prototype.removeItem.bind(sessionStorage);
  const removeLocal = Storage.prototype.removeItem.bind(localStorage);
  return vi.spyOn(Storage.prototype, 'removeItem').mockImplementation(function (
    this: Storage,
    key: string,
  ) {
    if (this === sessionStorage && keys.has(key)) throw new DOMException('denied', 'SecurityError');
    if (this === sessionStorage) removeSession(key);
    else removeLocal(key);
  });
}

beforeEach(() => {
  sessionStorage.clear();
  localStorage.clear();
});

afterEach(() => {
  clients.splice(0).forEach((client) => client.clear());
  vi.unstubAllGlobals();
});

test('later confirmation retries partial cleanup while the file remains deleted', async () => {
  const connections = stubChannel();
  sessionStorage.setItem(pendingKey(firstId), '{}');
  sessionStorage.setItem(pendingKey(secondId), '{}');
  await retainTurnHint(firstId, {
    command_id: '30000000-0000-4000-8000-000000000003',
    execution_id: null,
  });
  const removal = denySessionRemoval(new Set([pendingKey(firstId)]));
  const { result, client } = mountDeletion();
  client.setQueryData(['jd-work', firstId], 'deleted content');
  client.setQueryData(['jd-work', secondId], 'other content');

  await act(() => result.current.context.confirmDeleted(firstId));
  expect(result.current.context.deleted.has(firstId)).toBe(true);
  expect(result.current.warning).toMatch(/瀏覽器資料未能完整清理/);
  expect(sessionStorage.getItem(pendingKey(firstId))).toBe('{}');
  expect(localStorage.getItem(`caliburn:interview-turn:${firstId}`)).toBeNull();
  expect(client.getQueryData(['jd-work', firstId])).toBeUndefined();

  removal.mockRestore();
  await act(() => result.current.context.confirmDeleted(firstId));
  expect(sessionStorage.getItem(pendingKey(firstId))).toBeNull();
  expect(result.current.context.deleted.has(firstId)).toBe(true);
  expect(result.current.warning).toBeNull();
  expect(sessionStorage.getItem(pendingKey(secondId))).toBe('{}');
  expect(client.getQueryData(['jd-work', secondId])).toBe('other content');
  expect(connections.at(-1)?.postMessage).toHaveBeenCalledTimes(1);
});

test('same-file callers await one cleanup while another file can finish independently', async () => {
  stubChannel();
  const { result } = mountDeletion();
  let release = () => {};
  const barrier = new Promise<void>((resolve) => {
    release = resolve;
  });
  const heldLock = navigator.locks.request(`caliburn:interview-turn:${firstId}`, {}, () => barrier);
  const removed = vi.spyOn(Storage.prototype, 'removeItem');
  let repeatedFinished = false;
  let first = Promise.resolve();
  let repeated = Promise.resolve();
  act(() => {
    first = result.current.context.confirmDeleted(firstId);
    repeated = result.current.context.confirmDeleted(firstId).then(() => {
      repeatedFinished = true;
    });
  });
  try {
    await act(() => result.current.context.confirmDeleted(secondId));
    expect(result.current.context.deleted.has(firstId)).toBe(true);
    expect(result.current.context.deleted.has(secondId)).toBe(true);
    expect(repeatedFinished).toBe(false);
    expect(removed.mock.calls.filter(([key]) => key === pendingKey(firstId))).toHaveLength(1);
  } finally {
    await act(async () => {
      release();
      await Promise.all([first, repeated, heldLock]);
    });
  }
  expect(repeatedFinished).toBe(true);
  await act(() => result.current.context.confirmDeleted(firstId));
  expect(removed.mock.calls.filter(([key]) => key === pendingKey(firstId))).toHaveLength(1);
});

test('recovering one file keeps another file cleanup warning until both recover', async () => {
  stubChannel();
  const failures = new Set([firstId, secondId].map(pendingKey));
  denySessionRemoval(failures);
  const { result } = mountDeletion();
  await act(() => Promise.all([firstId, secondId].map(result.current.context.confirmDeleted)));
  failures.delete(pendingKey(firstId));
  await act(() => result.current.context.confirmDeleted(firstId));
  expect(result.current.warning).toMatch(/瀏覽器資料未能完整清理/);
  failures.delete(pendingKey(secondId));
  await act(() => result.current.context.confirmDeleted(secondId));
  expect(result.current.warning).toBeNull();
});

test('unmount closes the channel and a new mount can recover failed cleanup', async () => {
  const connections = stubChannel();
  sessionStorage.setItem(pendingKey(firstId), '{}');
  const removal = denySessionRemoval(new Set([pendingKey(firstId)]));
  const original = mountDeletion();
  await act(() => original.result.current.context.confirmDeleted(firstId));
  const previousConnection = connections.at(-1);
  original.unmount();
  expect(previousConnection?.close).toHaveBeenCalledTimes(1);
  removal.mockRestore();

  const reopened = mountDeletion();
  act(() => {
    connections.at(-1)?.onmessage?.(
      new MessageEvent('message', {
        data: { type: 'job_file_deleted', job_file_id: firstId },
      }),
    );
  });
  await waitFor(() => expect(sessionStorage.getItem(pendingKey(firstId))).toBeNull());
  expect(reopened.result.current.context.deleted.has(firstId)).toBe(true);
  expect(reopened.result.current.warning).toBeNull();
  expect(connections.at(-1)?.postMessage).not.toHaveBeenCalled();
});
