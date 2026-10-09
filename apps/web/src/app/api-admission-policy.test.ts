/** Exercise the public feature boundaries before remote UUIDs can reach cache or hints. */
import { QueryClient } from '@tanstack/react-query';
import { afterEach, expect, test, vi } from 'vitest';
import { jdSourcesQuery } from '../features/source-viewer/source-api';
import { turnJdChangesQuery } from '../features/jd-editor/turn-jd-changes-api';
import { submitInterviewInput, readTurnHint } from '../features/interview/interview-turn-api';

const id = 'abcdef01-1234-5678-9abc-0123456789ab';
afterEach(() => vi.unstubAllGlobals());

test('source lists reject URN revision IDs before caching', async () => {
  const client = new QueryClient();
  const query = jdSourcesQuery(id);
  vi.stubGlobal(
    'fetch',
    vi.fn().mockResolvedValue(Response.json({ revision_id: `urn:uuid:${id}`, references: [] })),
  );
  await expect(client.query(query)).rejects.toMatchObject({ kind: 'invalid_response' });
  expect(client.getQueryData(query.queryKey)).toBeUndefined();
  client.clear();
});

test('completed turn changes reject a matching URN execution scope', async () => {
  const client = new QueryClient();
  vi.stubGlobal(
    'fetch',
    vi.fn().mockResolvedValue(Response.json({ execution_id: `urn:uuid:${id}`, markdown: '' })),
  );
  await expect(client.query(turnJdChangesQuery(id, `urn:uuid:${id}`))).rejects.toMatchObject({
    kind: 'invalid_response',
  });
  client.clear();
});

test('input acknowledgement rejects URN execution IDs before retaining a hint', async () => {
  localStorage.clear();
  vi.stubGlobal(
    'fetch',
    vi.fn().mockResolvedValue(
      Response.json({
        job_file_id: id,
        command_id: id,
        source_id: id,
        execution_id: `urn:uuid:${id}`,
      }),
    ),
  );
  await expect(
    submitInterviewInput(id, { command_id: id, text: '工作內容' }),
  ).rejects.toMatchObject({ kind: 'invalid_response' });
  expect(readTurnHint(id)).toBeNull();
});

test('uppercase hyphenated UUIDs remain valid and unchanged', async () => {
  const client = new QueryClient();
  vi.stubGlobal(
    'fetch',
    vi.fn().mockResolvedValue(Response.json({ revision_id: id.toUpperCase(), references: [] })),
  );
  expect(await client.query(jdSourcesQuery(id))).toEqual({
    revision_id: id.toUpperCase(),
    references: [],
  });
  client.clear();
});
