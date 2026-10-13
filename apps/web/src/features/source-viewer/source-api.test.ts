import { stubHttp } from '../../test-http';
import { QueryClient } from '@tanstack/react-query';
import { afterEach, expect, test, vi } from 'vitest';
import { jdSourceChangesQuery, jdSourceContentQuery } from './source-api';

const scope = {
  jobFileId: '10000000-0000-4000-8000-000000000001',
  revisionId: '20000000-0000-4000-8000-000000000002',
  citationId: '30000000-0000-4000-8000-000000000003',
};
const foreignId = '40000000-0000-4000-8000-000000000004';
const requestId = '50000000-0000-4000-8000-000000000005';

afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

test.each(['content', 'changes'] as const)(
  '%s identity rejection keeps correlation without exposing source content',
  async (route) => {
    const diagnostic = vi.spyOn(console, 'warn').mockImplementation(() => {});
    const body = {
      revision_id: foreignId,
      citation_id: scope.citationId,
      ...(route === 'content'
        ? {
            content: {
              kind: 'interview',
              interview_sequence: 1,
              speaker: 'employee',
              interview_text: 'private source',
            },
          }
        : {
            jd_markdown: 'private source',
            source_version: null,
            comparison_version: null,
            source_markdown: null,
          }),
    };
    stubHttp(() =>
      Promise.resolve(Response.json(body, { headers: { 'X-Request-ID': requestId } })),
    );
    const client = new QueryClient();
    try {
      const response =
        route === 'content'
          ? client.query(jdSourceContentQuery(scope, null))
          : client.query(jdSourceChangesQuery(scope));
      await expect(response).rejects.toMatchObject({ kind: 'invalid_response', requestId });
      expect(diagnostic).toHaveBeenCalledExactlyOnceWith('caliburn', {
        event: 'http_failure',
        kind: 'invalid_response',
        status: 200,
        requestId,
        jobFileId: scope.jobFileId,
      });
      expect(JSON.stringify(diagnostic.mock.calls)).not.toContain('private source');
    } finally {
      client.clear();
    }
  },
);
