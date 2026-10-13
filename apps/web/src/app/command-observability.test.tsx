import { stubHttp } from '../test-http';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { act, renderHook } from '@testing-library/react';
import type { ReactNode } from 'react';
import { afterEach, expect, test, vi } from 'vitest';
import { useStoredCommand } from '../shared/commands/use-stored-command';
import { profileCommand } from '../features/jd-editor/jd-commands';
import type { ReviseJdProfileRequest } from '../shared/api/generated/http/types.gen';

const command = { command_id: '20000000-0000-4000-8000-000000000002' };
afterEach(() => {
  sessionStorage.clear();
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
});
function renderPending<T>(hook: () => T) {
  const client = new QueryClient();
  return renderHook(hook, {
    wrapper: ({ children }: { children: ReactNode }) => (
      <QueryClientProvider client={client}>{children}</QueryClientProvider>
    ),
  });
}
test.each(['restore', 'retain', 'acknowledge', 'refresh', 'display'] as const)(
  '%s failure records only the known file and original command IDs',
  async (stage) => {
    const jobFileId = '10000000-0000-4000-8000-000000000001';
    const diagnostic = vi.spyOn(console, 'warn').mockImplementation(() => {});
    const fail = () => {
      throw new Error('private draft and raw failure');
    };
    const definition = profileCommand(jobFileId, () => {
      if (stage === 'refresh') fail();
      return Promise.resolve();
    });
    const sent: ReviseJdProfileRequest = {
      command_id: command.command_id,
      expected_revision_id: jobFileId,
      changes: [{ action: 'set_field', field: 'job_title', value: 'private draft' }],
    };
    if (stage === 'restore') vi.spyOn(definition.store, 'read').mockImplementation(fail);
    if (stage === 'retain') vi.spyOn(definition.store, 'retain').mockImplementation(fail);
    if (stage === 'acknowledge') vi.spyOn(definition.store, 'acknowledge').mockImplementation(fail);
    stubHttp(
      vi.fn().mockResolvedValue(
        Response.json({
          revision_id: jobFileId,
          profile: { job_title: 'saved', organization_unit: null, reports_to: null, purpose: null },
        }),
      ),
    );
    const { result } = renderPending(() =>
      useStoredCommand(definition, () => {
        if (stage === 'display') fail();
      }),
    );
    if (stage !== 'restore') await act(() => result.current.send(sent));
    expect(diagnostic).toHaveBeenCalledExactlyOnceWith('caliburn', {
      event: 'command_failure',
      kind: stage === 'refresh' || stage === 'display' ? stage : 'storage',
      jobFileId,
      ...(stage === 'restore' ? {} : { commandId: sent.command_id }),
    });
    if (stage === 'restore' || stage === 'retain') expect(fetch).not.toHaveBeenCalled();
    else expect(result.current.outcome?.status).toBe('accepted');
    expect(JSON.stringify(diagnostic.mock.calls)).not.toContain('private');
  },
);
