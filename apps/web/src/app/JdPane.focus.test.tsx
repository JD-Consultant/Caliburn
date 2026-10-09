import { QueryClientProvider } from '@tanstack/react-query';
import type { QueryClient } from '@tanstack/react-query';
import { act, render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, expect, test, vi } from 'vitest';
import { JdPane } from './JdPane';
import { createAppQueryClient } from './query-client';

const fileId = '10000000-0000-4000-8000-000000000001';
const revisionId = '20000000-0000-4000-8000-000000000002';
const citationId = '30000000-0000-4000-8000-000000000003';
const sources = {
  revision_id: revisionId,
  references: [
    {
      citation_id: citationId,
      target: { kind: 'profile_field', field: 'job_title', item_id: null, task_id: null },
      target_label: '職務名稱',
      source_kind: 'interview',
      source_label: '合成訪談',
      needs_recheck: false,
      jd_changed: false,
      source_changed: false,
    },
  ],
};
const clients: QueryClient[] = [];

afterEach(() => {
  clients.splice(0).forEach((client) => client.clear());
  vi.unstubAllGlobals();
});

test.each(['present', 'removed', 'hidden', 'disabled'] as const)(
  'closing a badge-opened source sheet restores its trigger or disclosure fallback (%s)',
  async (triggerState) => {
    vi.stubGlobal('fetch', (path: string) => {
      if (path.endsWith('/jd/profile'))
        return Promise.resolve(
          Response.json({
            revision_id: revisionId,
            profile: {
              job_title: '合成工程師',
              organization_unit: null,
              reports_to: null,
              purpose: null,
            },
          }),
        );
      if (path.endsWith('/jd/work'))
        return Promise.resolve(
          Response.json({
            revision_id: revisionId,
            areas: [],
            tasks: [],
            capabilities: [],
            task_links: [],
            collaborators: [],
            conditions: [],
          }),
        );
      if (path.endsWith('/jd/sources')) return Promise.resolve(Response.json(sources));
      return Promise.resolve(
        Response.json({
          revision_id: revisionId,
          citation_id: citationId,
          content: {
            kind: 'interview',
            interview_sequence: 1,
            speaker: 'employee',
            interview_text: '合成原話',
          },
        }),
      );
    });
    const client = createAppQueryClient();
    clients.push(client);
    render(
      <QueryClientProvider client={client}>
        <JdPane jobFileId={fileId} turn={null} turnVerified />
      </QueryClientProvider>,
    );
    const badge = await screen.findByRole('button', { name: '來源 1 筆' });
    badge.focus();
    await userEvent.keyboard('{Enter}');
    await screen.findByText('合成原話');
    if (triggerState === 'removed')
      act(() => {
        client.setQueryData(['jd-sources', fileId], {
          ...sources,
          references: [],
        });
      });
    if (triggerState === 'hidden') badge.hidden = true;
    if (triggerState === 'disabled') (badge as HTMLButtonElement).disabled = true;
    const close = screen.getByRole('button', { name: '關閉來源面板' });
    close.focus();
    await userEvent.keyboard('{Enter}');
    expect(
      triggerState === 'present'
        ? badge
        : screen.getByRole('button', { name: '正式 JD 來源（唯讀）' }),
    ).toHaveFocus();
  },
);
