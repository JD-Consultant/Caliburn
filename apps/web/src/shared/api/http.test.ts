import { afterEach, expect, test, vi } from 'vitest';
import { requestJson } from './http';

afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

test('a bodyless deletion validates undefined without attempting JSON parsing', async () => {
  vi.stubGlobal('fetch', () => Promise.resolve(new Response(null, { status: 204 })));
  await expect(
    requestJson('/api/job-files/example', (value): value is undefined => value === undefined, {
      method: 'DELETE',
    }),
  ).resolves.toBeUndefined();
});

test('transport retains a bounded classification code but no error body', async () => {
  vi.stubGlobal('fetch', () =>
    Promise.resolve(
      Response.json(
        { detail: { code: 'job_file_busy', debug: 'private content' } },
        { status: 409 },
      ),
    ),
  );
  await expect(requestJson('/api/example', Array.isArray)).rejects.toMatchObject({
    status: 409,
    code: 'job_file_busy',
  });
});

test.each([
  { body: { detail: { code: 'not_found' } }, name: 'unknown resource' },
  { body: { detail: { code: 'consultant_turn_not_found' } }, name: 'missing turn' },
  { body: { detail: 'private diagnostic' }, name: 'unstructured error' },
])('a 404 for $name does not claim that the job file is missing', async ({ body }) => {
  vi.stubGlobal('fetch', () => Promise.resolve(Response.json(body, { status: 404 })));
  await expect(
    requestJson('/api/example/reasoning-summaries', Array.isArray),
  ).rejects.toMatchObject({
    status: 404,
    message: '找不到這項資料或服務。請重新讀取；若持續發生，請確認本機服務。',
  });
});

test('a missing-file code is retained for the owner without putting business copy in transport', async () => {
  vi.stubGlobal('fetch', () =>
    Promise.resolve(
      Response.json(
        {
          detail: { code: 'job_file_not_found', debug: 'private diagnostic' },
        },
        { status: 404 },
      ),
    ),
  );
  await expect(requestJson('/api/example', Array.isArray)).rejects.toMatchObject({
    status: 404,
    code: 'job_file_not_found',
    message: '找不到這項資料或服務。請重新讀取；若持續發生，請確認本機服務。',
  });
});

test('HTTP read preserves caller cancellation when combining the timeout signal', async () => {
  const diagnostic = vi.spyOn(console, 'warn').mockImplementation(() => {});
  const controller = new AbortController();
  let observed: AbortSignal | null | undefined;
  vi.stubGlobal(
    'fetch',
    (_path: string, options?: RequestInit) =>
      new Promise<Response>((_resolve, reject) => {
        observed = options?.signal;
        options?.signal?.addEventListener(
          'abort',
          () => reject(new DOMException('synthetic abort', 'AbortError')),
          { once: true },
        );
      }),
  );
  const result = requestJson('/api/example', Array.isArray, { signal: controller.signal });
  const rejection = expect(result).rejects.toMatchObject({ kind: 'cancelled' });
  controller.abort();
  await rejection;
  expect(observed?.aborted).toBe(true);
  expect(diagnostic).not.toHaveBeenCalled();
});

test('safe diagnostics connect failure to IDs without retaining response, URL or exception content', async () => {
  const requestId = '10000000-0000-4000-8000-000000000001';
  const commandId = '20000000-0000-4000-8000-000000000002';
  const diagnostic = vi.spyOn(console, 'warn').mockImplementation(() => {});
  vi.stubGlobal(
    'fetch',
    vi
      .fn()
      .mockResolvedValue(
        Response.json(
          { detail: { code: 'private_provider_message', body: 'private-body' } },
          { status: 500, headers: { 'X-Request-ID': requestId } },
        ),
      ),
  );
  await expect(
    requestJson('/api/private-path?secret=private-query', Array.isArray, {
      method: 'POST',
      body: 'private-input',
      correlation: { commandId },
    }),
  ).rejects.toMatchObject({
    kind: 'http',
    status: 500,
    code: 'private_provider_message',
    requestId,
  });
  expect(diagnostic).toHaveBeenCalledExactlyOnceWith('caliburn', {
    event: 'http_failure',
    kind: 'http',
    status: 500,
    requestId,
    commandId,
  });
  expect(JSON.stringify(diagnostic.mock.calls)).not.toContain('private');
  expect(vi.mocked(fetch).mock.calls[0]?.[1]).not.toHaveProperty('correlation');
});

test.each([
  ['a'.repeat(64), true],
  ['a'.repeat(65), false],
  ['UPPER_PRIVATE_CODE', false],
  ['private\ncode', false],
  ['<private>', false],
] as const)('an untrusted error token is bounded (%s)', async (code, retained) => {
  vi.spyOn(console, 'warn').mockImplementation(() => {});
  vi.stubGlobal(
    'fetch',
    vi.fn().mockResolvedValue(Response.json({ detail: { code } }, { status: 409 })),
  );
  await expect(requestJson('/api/example', Array.isArray)).rejects.toMatchObject({
    code: retained ? code : undefined,
  });
});

test('invalid request IDs are discarded, and a broken sink cannot change the failure category', async () => {
  const diagnostic = vi.spyOn(console, 'warn').mockImplementation(() => {
    throw new Error('sink failure');
  });
  vi.stubGlobal(
    'fetch',
    vi
      .fn()
      .mockResolvedValue(
        Response.json({}, { status: 200, headers: { 'X-Request-ID': 'private-token' } }),
      ),
  );
  await expect(
    requestJson('/api/example', Array.isArray, { correlation: { commandId: 'private-command' } }),
  ).rejects.toMatchObject({ kind: 'invalid_response', requestId: undefined });
  expect(diagnostic).toHaveBeenCalledExactlyOnceWith('caliburn', {
    event: 'http_failure',
    kind: 'invalid_response',
    status: 200,
  });
});

test('network exception text and stack never reach the diagnostic sink or public error', async () => {
  const diagnostic = vi.spyOn(console, 'warn').mockImplementation(() => {});
  vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error('private-network-payload')));
  const error = await requestJson('/api/example', Array.isArray).catch((error: unknown) => error);
  expect(error).toMatchObject({ kind: 'network' });
  expect(String(error)).not.toContain('private');
  expect(diagnostic).toHaveBeenCalledExactlyOnceWith('caliburn', {
    event: 'http_failure',
    kind: 'network',
  });
});

test('cancellation while reading an error body remains a quiet cancellation', async () => {
  const controller = new AbortController();
  const diagnostic = vi.spyOn(console, 'warn').mockImplementation(() => {});
  const response = new Response(null, { status: 409 });
  let rejectBody: (reason: Error) => void = () => {};
  vi.spyOn(response, 'json').mockReturnValue(
    new Promise((_resolve, reject) => {
      rejectBody = reject;
    }),
  );
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue(response));
  const result = requestJson('/api/example', Array.isArray, { signal: controller.signal });
  await Promise.resolve();
  controller.abort();
  rejectBody(new DOMException('private aborted body', 'AbortError'));
  await expect(result).rejects.toMatchObject({ kind: 'cancelled', code: undefined });
  expect(diagnostic).not.toHaveBeenCalled();
});

test('HTTP request applies the 15 second timeout without turning it into an admission rejection', async () => {
  const controller = new AbortController();
  const timeout = vi.spyOn(AbortSignal, 'timeout').mockReturnValue(controller.signal);
  vi.stubGlobal(
    'fetch',
    (_path: string, options?: RequestInit) =>
      new Promise<Response>((_resolve, reject) => {
        options?.signal?.addEventListener(
          'abort',
          () => reject(new DOMException('synthetic timeout', 'TimeoutError')),
          {
            once: true,
          },
        );
      }),
  );
  try {
    const result = requestJson('/api/example', Array.isArray, { method: 'POST' });
    const rejection = expect(result).rejects.toMatchObject({ kind: 'timeout' });
    controller.abort(new DOMException('synthetic timeout', 'TimeoutError'));
    await rejection;
    expect(timeout).toHaveBeenCalledWith(15_000);
  } finally {
    timeout.mockRestore();
  }
});

test('a non-JSON success is unconfirmed and never admitted as a result', async () => {
  vi.stubGlobal('fetch', () =>
    Promise.resolve(new Response('<html>unknown</html>', { status: 200 })),
  );
  await expect(
    requestJson('/api/example', Array.isArray, { method: 'POST' }),
  ).rejects.toMatchObject({ kind: 'invalid_json' });
});
