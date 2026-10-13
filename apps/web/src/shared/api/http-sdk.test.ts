import { afterEach, expect, test, vi } from 'vitest';
import './http';
import { exportJdPdf, readJobFile } from './generated/http/sdk.gen';
import { client } from './generated/http/client.gen';
import { QueryClient } from '@tanstack/react-query';

const fileId = '12345678-1234-4234-8234-1234567890ab';
const file = {
  job_file_id: fileId,
  display_name: '合成工作',
  name_revision: 1,
  employee_name: '合成員工',
  created_at: '2026-10-10T00:00:00Z',
};
const options = {
  path: { job_file_id: fileId },
  baseUrl: 'http://localhost',
  throwOnError: true as const,
};

afterEach(() => vi.unstubAllGlobals());

test('generated SDK rejects extra remote fields before returning data', async () => {
  vi.stubGlobal('fetch', () => Promise.resolve(Response.json({ ...file, private_extra: '原話' })));
  await expect(readJobFile(options)).rejects.toMatchObject({ kind: 'invalid_response' });
});

test('generated SDK rejects a valid shape from the wrong scope', async () => {
  vi.stubGlobal('fetch', () => Promise.resolve(Response.json(file)));
  await expect(readJobFile({ ...options, meta: { scope: () => false } })).rejects.toMatchObject({
    kind: 'invalid_response',
  });
});

test.each([201, 204])('JSON operation rejects undeclared successful status %s', async (status) => {
  vi.stubGlobal('fetch', () =>
    Promise.resolve(
      status === 204 ? new Response(null, { status }) : Response.json(file, { status }),
    ),
  );
  await expect(readJobFile(options)).rejects.toMatchObject({ kind: 'invalid_response' });
});

test.each([
  { status: 200, contentType: 'text/html' },
  { status: 202, contentType: 'application/pdf' },
  { status: 204, contentType: 'application/pdf' },
])('PDF rejects undeclared status/media $status $contentType', async ({ status, contentType }) => {
  vi.stubGlobal('fetch', () =>
    Promise.resolve(
      new Response(status === 204 ? null : 'private body', {
        status,
        headers: { 'Content-Type': contentType },
      }),
    ),
  );
  await expect(exportJdPdf(options)).rejects.toMatchObject({ kind: 'invalid_response' });
});

test('declared PDF stays binary', async () => {
  vi.stubGlobal('fetch', () =>
    Promise.resolve(
      new Response('%PDF-synthetic', {
        headers: { 'Content-Type': 'application/pdf' },
      }),
    ),
  );
  const { data } = await exportJdPdf(options);
  expect(data).toBeInstanceOf(Blob);
  expect(await data.text()).toBe('%PDF-synthetic');
});

test('declared stream policy does not consume event bytes', async () => {
  const response = new Response('event: reasoning\ndata: {}\n\n', {
    headers: { 'Content-Type': 'text/event-stream; charset=utf-8' },
  });
  vi.stubGlobal('fetch', () => Promise.resolve(response));
  const result = await client.get({
    url: '/api/job-files/{job_file_id}/consultant-turns/{execution_id}/activity-stream',
    path: { job_file_id: fileId, execution_id: fileId },
    parseAs: 'stream',
    throwOnError: true,
  });
  expect(result.data).toBe(response.body);
  expect(response.bodyUsed).toBe(false);
});

test.each(['application/json', 'text/html'])(
  'malformed %s success neither exposes private text nor enters query cache',
  async (contentType) => {
    vi.stubGlobal('fetch', () =>
      Promise.resolve(
        new Response('{"private text', {
          headers: { 'Content-Type': contentType },
        }),
      ),
    );
    const queries = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    const error = await queries
      .query({
        queryKey: ['synthetic-file'],
        queryFn: () => readJobFile(options).then(({ data }) => data),
      })
      .catch((failure: unknown) => failure);
    expect(error).toMatchObject({ kind: 'invalid_json' });
    expect(String(error)).not.toContain('private');
    expect(queries.getQueryData(['synthetic-file'])).toBeUndefined();
    queries.clear();
  },
);
