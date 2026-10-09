import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { act, renderHook } from '@testing-library/react';
import type { ReactNode } from 'react';
import type { ConsultantTurn } from '../../shared/api/generated/consultant-turn';
import { afterEach, beforeEach, expect, test, vi } from 'vitest';
import { useConsultantActivityStream } from './use-consultant-activity-stream';
import { clearDeletedInterview, consultantTurnQuery } from './interview-turn-api';

const file = '10000000-0000-4000-8000-000000000001';
const execution = '20000000-0000-4000-8000-000000000002';
const active: ConsultantTurn = {
  job_file_id: file,
  execution_id: execution,
  status: 'active',
  pause_requested: false,
  input_text: '工作內容',
  commentary: [],
  candidate: null,
  plan_preview: null,
  allowed_controls: [],
};
class Source extends EventTarget {
  static CONNECTING = 0;
  static OPEN = 1;
  static CLOSED = 2;
  static instances: Source[] = [];
  readyState = 0;
  close = vi.fn(() => {
    this.readyState = 2;
  });
  constructor(readonly url: string) {
    super();
    Source.instances.push(this);
  }
  error(state = 2) {
    this.readyState = state;
    this.dispatchEvent(new Event('error'));
  }
}
let client: QueryClient;
let read: ReturnType<typeof vi.fn<(path: string, options?: RequestInit) => Promise<Response>>>;
beforeEach(() => {
  vi.useFakeTimers();
  Source.instances = [];
  client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  read = vi.fn(() => Promise.resolve(Response.json(active)));
  vi.stubGlobal('fetch', read);
  vi.stubGlobal('EventSource', Source);
});
afterEach(() => {
  client.clear();
  vi.useRealTimers();
  vi.unstubAllGlobals();
});
function sourceAt(index: number): Source {
  const source = Source.instances[index];
  if (!source) throw new Error('Expected an active source');
  return source;
}
function mount() {
  return renderHook(({ id }) => useConsultantActivityStream(file, id), {
    initialProps: { id: execution },
    wrapper: ({ children }: { children: ReactNode }) => (
      <QueryClientProvider client={client}>{children}</QueryClientProvider>
    ),
  });
}
async function tick(ms = 0) {
  await act(async () => {
    await vi.advanceTimersByTimeAsync(ms);
  });
}

test('CLOSED verifies active via GET then recreates after backoff; CONNECTING has one native owner', async () => {
  mount();
  act(() => sourceAt(0).error(0));
  await tick(8_000);
  expect(Source.instances).toHaveLength(1);
  act(() => sourceAt(0).error());
  await tick();
  expect(read).toHaveBeenCalled();
  expect(Source.instances).toHaveLength(1);
  await tick(1_000);
  expect(Source.instances).toHaveLength(2);
  expect(read.mock.calls.every(([, options]) => !options?.method || options.method === 'GET')).toBe(
    true,
  );
});

test.each(['completed', 'paused', 'cancelled', 'failed', '404'])(
  'CLOSED stops on confirmed %s',
  async (status) => {
    read.mockImplementation(() =>
      Promise.resolve(
        status === '404'
          ? new Response(null, { status: 404 })
          : Response.json({ ...active, status }),
      ),
    );
    mount();
    act(() => sourceAt(0).error());
    await tick(30_000);
    expect(read).toHaveBeenCalledTimes(1);
    expect(Source.instances).toHaveLength(1);
  },
);

test('unknown GET failure retries finitely without opening a stream or resetting on renders', async () => {
  read.mockImplementation(() => Promise.resolve(new Response(null, { status: 503 })));
  const view = mount();
  act(() => sourceAt(0).error());
  await tick(30_000);
  const attempts = read.mock.calls.length;
  expect(attempts).toBeGreaterThan(1);
  expect(attempts).toBeLessThanOrEqual(4);
  view.rerender({ id: execution });
  await tick(30_000);
  expect(read).toHaveBeenCalledTimes(attempts);
  expect(Source.instances).toHaveLength(1);
  expect(view.result.current.disconnected).toBe(true);
});

test('repeated short OPEN/CLOSED cycles exhaust the same recovery budget', async () => {
  mount();
  for (let index = 0; index < 6; index++) {
    const source = sourceAt(Source.instances.length - 1);
    act(() => {
      source.readyState = 1;
      source.dispatchEvent(new Event('open'));
      source.error();
    });
    await tick(8_000);
  }
  expect(Source.instances).toHaveLength(4);
});

test('unmount aborts its in-flight recovery read and cannot reopen from a late response', async () => {
  let signal: AbortSignal | undefined;
  let resolve!: (value: Response) => void;
  read.mockImplementation((_path: string, options?: RequestInit) => {
    signal = options?.signal ?? undefined;
    return new Promise<Response>((done) => {
      resolve = done;
    });
  });
  const view = mount();
  act(() => sourceAt(0).error());
  await tick();
  expect(signal).toBeDefined();
  view.unmount();
  expect(signal?.aborted).toBe(true);
  resolve(Response.json(active));
  await tick(30_000);
  expect(Source.instances).toHaveLength(1);
});

test('scope change clears pending reconstruction and ignores old events', async () => {
  const view = mount();
  act(() => sourceAt(0).error());
  await tick();
  view.rerender({ id: file });
  await tick(30_000);
  expect(Source.instances).toHaveLength(2);
  expect(sourceAt(1).url).toContain(`/consultant-turns/${file}/`);
});

test('existing query owner publishing a terminal status closes the live source', () => {
  mount();
  act(() => {
    client.setQueryData(consultantTurnQuery(file, execution).queryKey, {
      ...active,
      status: 'completed',
    });
  });
  expect(sourceAt(0).close).toHaveBeenCalled();
});

test('a stable OPEN resets the recovery budget', async () => {
  mount();
  for (let index = 0; index < 3; index++) {
    act(() => sourceAt(index).error());
    await tick(8_000);
  }
  act(() => {
    const source = sourceAt(3);
    source.readyState = 1;
    source.dispatchEvent(new Event('open'));
  });
  await tick(10_000);
  act(() => sourceAt(3).error());
  await tick(1_000);
  expect(Source.instances).toHaveLength(5);
});

test('confirmed deletion cancels pending reconstruction', async () => {
  mount();
  act(() => sourceAt(0).error());
  await tick();
  await act(async () => {
    await clearDeletedInterview(file);
  });
  await tick(30_000);
  expect(Source.instances).toHaveLength(1);
});

test('unmount preserves a read already owned by another query caller', async () => {
  let signal: AbortSignal | undefined;
  let resolve!: (value: Response) => void;
  read.mockImplementation((_path, options) => {
    signal = options?.signal ?? undefined;
    return new Promise<Response>((done) => {
      resolve = done;
    });
  });
  const borrowed = client.query(consultantTurnQuery(file, execution));
  const view = mount();
  act(() => sourceAt(0).error());
  await tick();
  view.unmount();
  expect(signal?.aborted).toBe(false);
  resolve(Response.json(active));
  await expect(borrowed).resolves.toEqual(active);
  await tick(30_000);
  expect(Source.instances).toHaveLength(1);
});

test('a disposed recovery does not leave an aborted signal in the shared cache query function', async () => {
  const view = mount();
  act(() => sourceAt(0).error());
  await tick();
  view.unmount();
  read.mockImplementation((_path, options) => {
    expect(options?.signal?.aborted).toBe(false);
    return Promise.resolve(Response.json(active));
  });
  await client.refetchQueries({ queryKey: consultantTurnQuery(file, execution).queryKey });
});
