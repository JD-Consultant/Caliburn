import type { ReactNode } from 'react';
import { QueryClientProvider, QueryObserver } from '@tanstack/react-query';
import { act, renderHook } from '@testing-library/react';
import { afterEach, expect, test, vi } from 'vitest';
import { creationCommand, pendingCreation } from '../features/job-files/job-file-commands';
import { renameCommand } from '../features/job-files/job-file-commands';
import { ApiError } from '../shared/api/http';
import { pendingProfile, profileCommand, workCommand } from '../features/jd-editor/jd-commands';
import type { WorkCommand } from '../features/jd-editor/jd-work-api';
import { jdSourcesQuery } from '../features/source-viewer/source-api';
import { useStoredCommand } from '../shared/commands/use-stored-command';
import type { ReviseJdProfileRequest } from '../shared/api/generated/revise-jd-profile-request';
import { refreshFormalJd } from './workspace-refresh';
import { createAppQueryClient } from './query-client';

const fileId = '10000000-0000-4000-8000-000000000001';
const commandId = '20000000-0000-4000-8000-000000000002';
const revisionId = '30000000-0000-4000-8000-000000000003';
const creation = { command_id: commandId, display_name: '職務', employee_name: '員工' };

afterEach(() => {
  sessionStorage.clear();
  vi.unstubAllGlobals();
});

test.each([
  ['HTML 422', () => new Response('<html>private error</html>', { status: 422 })],
  [
    'schema 422',
    () => Response.json({ detail: [{ loc: ['body'], msg: 'private' }] }, { status: 422 }),
  ],
  ['unknown 409', () => Response.json({ detail: { code: 'private_code' } }, { status: 409 })],
  ['bare 404', () => new Response(null, { status: 404 })],
  ['unknown 410', () => Response.json({ detail: { code: 'other_deleted' } }, { status: 410 })],
  [
    'wrong status deleted code',
    () => Response.json({ detail: { code: 'creation_result_deleted' } }, { status: 500 }),
  ],
])('a lost creation ACK followed by %s preserves the original command', async (_name, response) => {
  const client = createAppQueryClient();
  const fetcher = vi
    .fn<(url: string, options?: RequestInit) => Promise<Response>>()
    .mockRejectedValueOnce(new TypeError('lost ACK'))
    .mockImplementationOnce(() => Promise.resolve(response()));
  vi.stubGlobal('fetch', fetcher);
  const { result, unmount } = renderHook(() => useStoredCommand(creationCommand(client)), {
    wrapper: ({ children }: { children: ReactNode }) => (
      <QueryClientProvider client={client}>{children}</QueryClientProvider>
    ),
  });
  try {
    await act(() => result.current.send(creation));
    await act(() => result.current.send(creation));
    expect(result.current.outcome?.status).toBe('unknown');
    expect(pendingCreation.read()).toEqual(creation);
    expect(fetcher.mock.calls[1]?.[1]?.body).toBe(JSON.stringify(creation));
  } finally {
    unmount();
    client.clear();
  }
});

test('profile validation before original-result lookup cannot retire an uncertain command', async () => {
  const client = createAppQueryClient();
  const command: ReviseJdProfileRequest = {
    command_id: commandId,
    expected_revision_id: revisionId,
    changes: [{ action: 'set_field', field: 'job_title', value: '新職稱' }],
  };
  vi.stubGlobal(
    'fetch',
    vi
      .fn()
      .mockRejectedValueOnce(new TypeError('lost ACK'))
      .mockResolvedValueOnce(
        Response.json({ detail: { code: 'invalid_profile_changes' } }, { status: 422 }),
      ),
  );
  const { result, unmount } = renderHook(
    () => useStoredCommand(profileCommand(fileId, () => refreshFormalJd(client, fileId))),
    {
      wrapper: ({ children }: { children: ReactNode }) => (
        <QueryClientProvider client={client}>{children}</QueryClientProvider>
      ),
    },
  );
  try {
    await act(() => result.current.send(command));
    await act(() => result.current.send(command));
    expect(result.current.outcome?.status).toBe('unknown');
    expect(pendingProfile(fileId).read()).toEqual(command);
  } finally {
    unmount();
    client.clear();
  }
});

test('manual JD refresh replaces a first source GET started before the commit', async () => {
  const client = createAppQueryClient();
  let release!: (response: Response) => void;
  const before = new Promise<Response>((resolve) => {
    release = resolve;
  });
  const sources = (revision: string) => ({ revision_id: revision, references: [] });
  const nextRevision = '40000000-0000-4000-8000-000000000004';
  const fetcher = vi
    .fn()
    .mockReturnValueOnce(before)
    .mockResolvedValue(Response.json(sources(nextRevision)));
  vi.stubGlobal('fetch', fetcher);
  const query = jdSourcesQuery(fileId);
  const observer = new QueryObserver(client, query);
  const unsubscribe = observer.subscribe(() => {});
  try {
    const refresh = profileCommand(fileId, () => refreshFormalJd(client, fileId)).refresh();
    release(Response.json(sources(revisionId)));
    await refresh;
    expect(fetcher).toHaveBeenCalledTimes(2);
    expect(client.getQueryData(query.queryKey)?.revision_id).toBe(nextRevision);
  } finally {
    unsubscribe();
    client.clear();
  }
});

test('only operation-specific rejection codes retire the original payload', () => {
  const client = createAppQueryClient();
  try {
    const create = creationCommand(client);
    const rename = renameCommand(fileId, client);
    const profile = profileCommand(fileId, () => refreshFormalJd(client, fileId));
    const error = (code: string, status = 409) =>
      new ApiError('public', { kind: 'http', status, code });
    const renameInput = {
      command_id: commandId,
      display_name: '新名稱',
      expected_name_revision: 1,
    };
    const profileInput: ReviseJdProfileRequest = {
      command_id: commandId,
      expected_revision_id: revisionId,
      changes: [{ action: 'clear_field', field: 'job_title' }],
    };
    expect(create.classifyRejection(error('creation_command_conflict'), creation)).not.toBeNull();
    expect(create.classifyRejection(error('stale_job_file_name'), creation)).toBeNull();
    expect(rename.classifyRejection(error('rename_command_conflict'), renameInput)).not.toBeNull();
    expect(rename.classifyRejection(error('stale_job_file_name'), renameInput)).not.toBeNull();
    expect(rename.classifyRejection(error('job_file_not_found', 404), renameInput)).toBeNull();
    for (const code of ['jd_command_conflict', 'jd_revision_stale', 'consultant_turn_active'])
      expect(profile.classifyRejection(error(code), profileInput)).not.toBeNull();
    expect(
      profile.classifyRejection(error('invalid_profile_changes', 422), profileInput),
    ).toBeNull();
    expect(profile.classifyRejection(error('jd_revision_stale', 500), profileInput)).toBeNull();
  } finally {
    client.clear();
  }
});

test('work rejection checks the collection and phase of a public code', () => {
  const definition = workCommand(fileId, () => Promise.resolve());
  const base = { command_id: commandId, expected_revision_id: revisionId };
  const commands: [WorkCommand, string][] = [
    [
      {
        collection: 'areas',
        request: { ...base, change: { action: 'delete_area', area_id: fileId } },
      },
      'jd_area_not_found',
    ],
    [
      {
        collection: 'tasks',
        request: { ...base, change: { action: 'delete_task', task_id: fileId } },
      },
      'jd_task_target_not_found',
    ],
    [
      {
        collection: 'capabilities',
        request: { ...base, change: { action: 'delete_capability', capability_id: fileId } },
      },
      'jd_capability_target_not_found',
    ],
    [
      {
        collection: 'collaborators',
        request: { ...base, change: { action: 'delete_collaborator', collaborator_id: fileId } },
      },
      'jd_collaborator_not_found',
    ],
    [
      {
        collection: 'conditions',
        request: { ...base, change: { action: 'delete_condition', condition_id: fileId } },
      },
      'jd_condition_not_found',
    ],
  ];
  for (const [command, code] of commands) {
    expect(
      definition.classifyRejection(new ApiError('public', { status: 404, code }), command),
    ).not.toBeNull();
    expect(
      definition.classifyRejection(
        new ApiError('public', { status: 404, code: 'job_file_not_found' }),
        command,
      ),
    ).toBeNull();
    expect(
      definition.classifyRejection(
        new ApiError('public', { status: 422, code: 'invalid_task_change' }),
        command,
      ),
    ).toBeNull();
    expect(
      definition.classifyRejection(
        new ApiError('public', { status: 409, code: 'capability_in_use' }),
        command,
      ),
    ).toEqual(command.collection === 'capabilities' ? { reason: 'refused' } : null);
    for (const [, otherCode] of commands) {
      expect(
        definition.classifyRejection(
          new ApiError('public', { status: 404, code: otherCode }),
          command,
        ),
      ).toEqual(code === otherCode ? { reason: 'refused' } : null);
    }
  }
});
