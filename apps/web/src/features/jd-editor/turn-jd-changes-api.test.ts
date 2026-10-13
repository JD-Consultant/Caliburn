import { stubHttp } from '../../test-http';
import { QueryClient } from '@tanstack/react-query';
import { afterEach, expect, test, vi } from 'vitest';
import { turnJdChangesQuery } from './turn-jd-changes-api';

afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

test('a foreign round diff is refused with request correlation and without exposing content', async () => {
  const jobFileId = '10000000-0000-4000-8000-000000000001';
  const executionId = '20000000-0000-4000-8000-000000000002';
  const requestId = '30000000-0000-4000-8000-000000000003';
  const diagnostic = vi.spyOn(console, 'warn').mockImplementation(() => {});
  stubHttp(() =>
    Promise.resolve(
      Response.json(
        { execution_id: jobFileId, markdown: 'private diff' },
        { headers: { 'X-Request-ID': requestId } },
      ),
    ),
  );
  const client = new QueryClient();
  try {
    await expect(client.query(turnJdChangesQuery(jobFileId, executionId))).rejects.toMatchObject({
      kind: 'invalid_response',
      requestId,
    });
    expect(diagnostic).toHaveBeenCalledExactlyOnceWith('caliburn', {
      event: 'http_failure',
      kind: 'invalid_response',
      status: 200,
      requestId,
      jobFileId,
      executionId,
    });
    expect(JSON.stringify(diagnostic.mock.calls)).not.toContain('private diff');
  } finally {
    client.clear();
  }
});
