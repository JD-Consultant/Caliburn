import { stubHttp } from '../../test-http';
import { QueryClient } from '@tanstack/react-query';
import { afterEach, expect, test, vi } from 'vitest';
import { turnToolsQuery } from './turn-tools-api';

afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

test('wrong turn tools preserve HTTP correlation and never expose tool content in logs', async () => {
  const file = '10000000-0000-4000-8000-000000000001';
  const run = '20000000-0000-4000-8000-000000000002';
  const request = '30000000-0000-4000-8000-000000000003';
  const log = vi.spyOn(console, 'warn').mockImplementation(() => {});
  stubHttp(() =>
    Promise.resolve(
      Response.json(
        {
          execution_id: file,
          calls: [
            {
              request_id: request,
              response_id: 'r1',
              call_id: 'c1',
              name: 'private tool name',
              arguments: 'private arguments',
              result_state: 'recorded',
              output: 'private result',
            },
          ],
        },
        { headers: { 'X-Request-ID': request } },
      ),
    ),
  );
  const client = new QueryClient();
  try {
    await expect(client.query(turnToolsQuery(file, run))).rejects.toMatchObject({
      kind: 'invalid_response',
      requestId: request,
    });
    expect(log).toHaveBeenCalledExactlyOnceWith('caliburn', {
      event: 'http_failure',
      kind: 'invalid_response',
      status: 200,
      requestId: request,
      jobFileId: file,
      executionId: run,
    });
    expect(JSON.stringify(log.mock.calls)).not.toContain('private');
  } finally {
    client.clear();
  }
});
