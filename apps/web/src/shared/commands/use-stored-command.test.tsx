import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { act, renderHook, waitFor } from '@testing-library/react';
import type { ReactNode } from 'react';
import { afterEach, expect, test, vi } from 'vitest';
import { createPendingCommandStore } from './pending-command';
import { useStoredCommand } from './use-stored-command';

const storageKey = 'caliburn.pending-jd-profile.10000000-0000-4000-8000-000000000001';
const command = { command_id: '20000000-0000-4000-8000-000000000002' };
function isCommand(value: unknown): value is typeof command {
  return (
    typeof value === 'object' &&
    value !== null &&
    'command_id' in value &&
    typeof value.command_id === 'string'
  );
}

afterEach(() => sessionStorage.clear());

function renderPending<T>(hook: () => T) {
  const client = new QueryClient();
  return renderHook(hook, {
    wrapper: ({ children }: { children: ReactNode }) => (
      <QueryClientProvider client={client}>{children}</QueryClientProvider>
    ),
  });
}

test('a known ACK while mounted refreshes the cache once and tells the editor once', async () => {
  const refresh = vi.fn(),
    onSaved = vi.fn();
  const { result } = renderPending(() =>
    useStoredCommand(
      {
        store: createPendingCommandStore({
          key: storageKey,
          isCommand,
          matches: (left, right) => left.command_id === right.command_id,
        }),
        execute: () => Promise.resolve(),
        refresh,
        classifyRejection: () => null,
      },
      onSaved,
    ),
  );
  await act(() => result.current.send(command));
  expect(sessionStorage.getItem(storageKey)).toBeNull();
  expect(refresh).toHaveBeenCalledOnce();
  expect(onSaved).toHaveBeenCalledOnce();
});

test.each(['refresh', 'storage', 'newer'] as const)(
  'a typed terminal rejection stays known when %s changes during acknowledgement',
  async (failure) => {
    const store = createPendingCommandStore({
      key: storageKey,
      isCommand,
      matches: (left, right) => left.command_id === right.command_id,
    });
    const next = { command_id: 'newer-command' };
    const onSaved = vi.fn();
    const { result } = renderPending(() =>
      useStoredCommand(
        {
          store,
          execute: () => Promise.reject(new Error('terminal')),
          classifyRejection: () => ({ reason: 'deleted' as const, refresh: true }),
          refresh: () => {
            if (failure === 'refresh') throw new Error('refresh unavailable');
            if (failure === 'newer') sessionStorage.setItem(storageKey, JSON.stringify(next));
            if (failure === 'storage')
              vi.spyOn(Storage.prototype, 'removeItem').mockImplementation(() => {
                throw new Error('storage unavailable');
              });
          },
        },
        onSaved,
      ),
    );
    try {
      await act(() => result.current.send(command));
      expect(result.current.outcome).toEqual({
        status: 'rejected',
        reason: 'deleted',
        refreshFailed: failure === 'refresh',
        acknowledgement:
          failure === 'newer' ? 'changed' : failure === 'storage' ? 'unavailable' : 'cleared',
      });
      expect(onSaved).not.toHaveBeenCalled();
      expect(store.read()).toEqual(
        failure === 'newer' ? next : failure === 'storage' ? command : null,
      );
    } finally {
      vi.restoreAllMocks();
    }
  },
);

test('a known ACK after unmount retires the command and refreshes the cache, but does not call the closed editor', async () => {
  let resolve: () => void = () => {};
  const deferred = new Promise<void>((done) => {
    resolve = done;
  });
  const refresh = vi.fn(),
    onSaved = vi.fn();
  const { result, unmount } = renderPending(() =>
    useStoredCommand(
      {
        store: createPendingCommandStore({
          key: storageKey,
          isCommand,
          matches: (left, right) => left.command_id === right.command_id,
        }),
        execute: () => deferred,
        refresh,
        classifyRejection: () => null,
      },
      onSaved,
    ),
  );
  let sending: Promise<void> = Promise.resolve();
  act(() => {
    sending = result.current.send(command);
  });
  expect(sessionStorage.getItem(storageKey)).not.toBeNull();
  unmount();
  resolve();
  await sending;
  expect(sessionStorage.getItem(storageKey)).toBeNull();
  // Cache invalidation is not a screen callback: other observers still hold the old JD.
  expect(refresh).toHaveBeenCalledOnce();
  expect(onSaved).not.toHaveBeenCalled();
});

test('an unknown result after unmount preserves the original command for recovery', async () => {
  let reject: (reason: Error) => void = () => {};
  const deferred = new Promise<void>((_done, fail) => {
    reject = fail;
  });
  const refresh = vi.fn(),
    onSaved = vi.fn();
  const { result, unmount } = renderPending(() =>
    useStoredCommand(
      {
        store: createPendingCommandStore({
          key: storageKey,
          isCommand,
          matches: (left, right) => left.command_id === right.command_id,
        }),
        execute: () => deferred,
        refresh,
        classifyRejection: () => null,
      },
      onSaved,
    ),
  );
  let sending: Promise<void> = Promise.resolve();
  act(() => {
    sending = result.current.send(command);
  });
  unmount();
  reject(new TypeError('synthetic lost acknowledgement'));
  await sending;
  expect(JSON.parse(sessionStorage.getItem(storageKey) ?? 'null')).toEqual(command);
  expect(refresh).not.toHaveBeenCalled();
  expect(onSaved).not.toHaveBeenCalled();
});

test('an old editor ACK does not clear a newer command in the same storage slot', async () => {
  let resolve: () => void = () => {};
  const deferred = new Promise<void>((done) => {
    resolve = done;
  });
  const { result, unmount } = renderPending(() =>
    useStoredCommand(
      {
        store: createPendingCommandStore({
          key: storageKey,
          isCommand,
          matches: (left, right) => left.command_id === right.command_id,
        }),
        execute: () => deferred,
        refresh: () => {},
        classifyRejection: () => null,
      },
      () => {},
    ),
  );
  let sending: Promise<void> = Promise.resolve();
  act(() => {
    sending = result.current.send(command);
  });
  unmount();
  const next = { command_id: '30000000-0000-4000-8000-000000000003' };
  sessionStorage.setItem(storageKey, JSON.stringify(next));
  resolve();
  await sending;
  expect(JSON.parse(sessionStorage.getItem(storageKey) ?? 'null')).toEqual(next);
});

test('an old ACK while mounted preserves the newer command and does not close its editor', async () => {
  let resolve: () => void = () => {};
  const deferred = new Promise<void>((done) => {
    resolve = done;
  });
  const refresh = vi.fn();
  const onSaved = vi.fn();
  const { result } = renderPending(() =>
    useStoredCommand(
      {
        store: createPendingCommandStore({
          key: storageKey,
          isCommand,
          matches: (left, right) => left.command_id === right.command_id,
        }),
        execute: () => deferred,
        refresh,
        classifyRejection: () => null,
      },
      onSaved,
    ),
  );
  let sending: Promise<void> = Promise.resolve();
  act(() => {
    sending = result.current.send(command);
  });
  const next = { command_id: '30000000-0000-4000-8000-000000000003' };
  sessionStorage.setItem(storageKey, JSON.stringify(next));
  await act(async () => {
    resolve();
    await sending;
  });
  expect(JSON.parse(sessionStorage.getItem(storageKey) ?? 'null')).toEqual(next);
  expect(refresh).toHaveBeenCalledOnce();
  expect(onSaved).not.toHaveBeenCalled();
  expect(result.current.locked).toBe(true);
});

test('a cache refresh failure cannot change an accepted write into an unknown result', async () => {
  const onSaved = vi.fn();
  const { result } = renderPending(() =>
    useStoredCommand(
      {
        store: createPendingCommandStore({
          key: storageKey,
          isCommand,
          matches: (left, right) => left.command_id === right.command_id,
        }),
        execute: () => Promise.resolve('saved'),
        refresh: () => {
          throw new Error('Synthetic cache refresh failure');
        },
        classifyRejection: () => null,
      },
      onSaved,
    ),
  );
  await act(() => result.current.send(command));
  expect(result.current.outcome).toEqual({
    status: 'accepted',
    data: 'saved',
    acknowledgement: 'cleared',
    refreshFailed: true,
  });
  expect(sessionStorage.getItem(storageKey)).toBeNull();
  expect(onSaved).not.toHaveBeenCalled();
});

test('a screen callback failure leaves the accepted result visible and blocks another write', async () => {
  const { result } = renderPending(() =>
    useStoredCommand(
      {
        store: createPendingCommandStore({
          key: storageKey,
          isCommand,
          matches: (left, right) => left.command_id === right.command_id,
        }),
        execute: () => Promise.resolve('saved'),
        refresh: () => {},
        classifyRejection: () => null,
      },
      () => {
        throw new Error('Synthetic screen callback failure');
      },
    ),
  );
  await act(() => result.current.send(command));
  expect(result.current.outcome?.status).toBe('accepted');
  expect(result.current.issue).toBe('display');
  expect(result.current.locked).toBe(true);
  expect(sessionStorage.getItem(storageKey)).toBeNull();
});

test('a command replaced while accepted data refreshes cannot close the newer editor', async () => {
  let finishRefresh: () => void = () => {};
  const refreshed = new Promise<void>((resolve) => {
    finishRefresh = resolve;
  });
  const refresh = vi.fn(() => refreshed);
  const onSaved = vi.fn();
  const { result } = renderPending(() =>
    useStoredCommand(
      {
        store: createPendingCommandStore({
          key: storageKey,
          isCommand,
          matches: (left, right) => left.command_id === right.command_id,
        }),
        execute: () => Promise.resolve(),
        refresh,
        classifyRejection: () => null,
      },
      onSaved,
    ),
  );
  let sending: Promise<void> = Promise.resolve();
  act(() => {
    sending = result.current.send(command);
  });
  await waitFor(() => expect(refresh).toHaveBeenCalledOnce());
  const next = { command_id: '30000000-0000-4000-8000-000000000003' };
  sessionStorage.setItem(storageKey, JSON.stringify(next));
  await act(async () => {
    finishRefresh();
    await sending;
  });
  expect(onSaved).not.toHaveBeenCalled();
  expect(result.current.locked).toBe(true);
  expect(JSON.parse(sessionStorage.getItem(storageKey) ?? 'null')).toEqual(next);
});
