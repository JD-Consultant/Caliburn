import { stubHttp } from '../test-http';
import { QueryClientProvider } from '@tanstack/react-query';
import type { QueryClient } from '@tanstack/react-query';
import { act, render, screen, waitFor, within } from '@testing-library/react';
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
      target: { kind: 'profile_field', field: 'job_title', item_id: null },
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

test.each([false, true])(
  'source read failure stays visible and retryable with cached data=%s',
  async (cached) => {
    const client = createAppQueryClient();
    clients.push(client);
    client.setQueryData(['jd-profile', fileId, 'formal'], {
      revision_id: revisionId,
      profile: {
        job_title: '合成工程師',
        organization_unit: null,
        reports_to: null,
        purpose: null,
      },
    });
    client.setQueryData(['jd-work', fileId, 'formal'], {
      revision_id: revisionId,
      areas: [],
      tasks: [],
      capabilities: [],
      task_links: [],
      collaborators: [],
      conditions: [],
    });
    if (cached) client.setQueryData(['jd-sources', fileId], sources);
    const sourceRead = vi
      .fn<() => Promise<Response>>()
      .mockResolvedValueOnce(new Response(null, { status: 503 }))
      .mockImplementation(() => Promise.resolve(Response.json(sources)));
    stubHttp((path: string) => {
      if (path.endsWith('/jd/sources')) return sourceRead();
      const key = path.endsWith('/jd/profile') ? 'jd-profile' : 'jd-work';
      return Promise.resolve(Response.json(client.getQueryData([key, fileId, 'formal'])));
    });
    render(
      <QueryClientProvider client={client}>
        <JdPane jobFileId={fileId} turn={null} turnVerified />
      </QueryClientProvider>,
    );
    expect(await screen.findByRole('alert')).toHaveTextContent('來源');
    expect(screen.getByRole('alert')).toHaveTextContent('重新讀取');
    await userEvent.click(screen.getByRole('button', { name: '重新讀取來源' }));
    expect(await screen.findByRole('button', { name: '來源 1 筆' })).toBeVisible();
    await waitFor(() => expect(screen.queryByRole('alert')).not.toBeInTheDocument());
  },
);

test.each(['present', 'removed', 'hidden', 'disabled'] as const)(
  'closing a badge-opened source sheet restores its trigger or disclosure fallback (%s)',
  async (triggerState) => {
    stubHttp((path: string) => {
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

test('task children resolve to task evidence while shared capability keeps its own evidence', async () => {
  const taskId = '50000000-0000-4000-8000-000000000005';
  const basePath = `/api/job-files/${fileId}/jd/sources`;
  const taskReference = {
    ...sources.references[0],
    target: { kind: 'task', field: null, item_id: taskId },
    target_label: '任務：處理例外',
    source_label: '例外處理理解',
    needs_recheck: true,
    jd_changed: true,
  };
  const root = {
    revision_id: revisionId,
    citation_id: citationId,
    content: {
      kind: 'work_understanding',
      title: '固定理解',
      description: '原引用描述',
      body: '## 原引用正文\n\n處理異常並追蹤。',
      references: [],
    },
  };
  const capabilityId = '60000000-0000-4000-8000-000000000006';
  const capabilityCitation = '70000000-0000-4000-8000-000000000007';
  const responses: Record<string, unknown> = {
    [`/api/job-files/${fileId}/jd/profile`]: {
      revision_id: revisionId,
      profile: { job_title: null, organization_unit: null, reports_to: null, purpose: null },
    },
    [`/api/job-files/${fileId}/jd/work`]: {
      revision_id: revisionId,
      areas: [],
      tasks: [
        {
          task_id: taskId,
          area_id: null,
          title: '處理例外',
          description: '追蹤並核清異常',
          outcomes: [{ detail_id: '80000000-0000-4000-8000-000000000008', text: '例外清單' }],
          requirements: [{ detail_id: '90000000-0000-4000-8000-000000000009', text: '當日完成' }],
        },
      ],
      capabilities: [
        { capability_id: capabilityId, kind: 'skill', name: '核對', description: '逐筆比對' },
      ],
      task_links: [{ task_id: taskId, capability_id: capabilityId }],
      collaborators: [],
      conditions: [],
    },
    [basePath]: {
      ...sources,
      references: [
        taskReference,
        {
          ...taskReference,
          citation_id: capabilityCitation,
          target: { kind: 'capability', field: null, item_id: capabilityId },
          target_label: '技能：核對',
          source_label: '核對能力依據',
          needs_recheck: false,
          source_changed: false,
        },
      ],
    },
    [`${basePath}/${capabilityCitation}?revision_id=${revisionId}`]: {
      ...root,
      citation_id: capabilityCitation,
      content: { ...root.content, body: '共用技能的固定依據' },
    },
    [`${basePath}/${citationId}?revision_id=${revisionId}`]: root,
  };
  stubHttp((path: string) => {
    const response = responses[path];
    if (response === undefined) throw new Error(`Unexpected request: ${path}`);
    return Promise.resolve(Response.json(response));
  });
  const client = createAppQueryClient();
  clients.push(client);
  render(
    <QueryClientProvider client={client}>
      <JdPane jobFileId={fileId} turn={null} turnVerified />
    </QueryClientProvider>,
  );
  const task = await screen.findByRole('article', { name: '處理例外' });
  expect(within(task).getByText('例外清單')).toBeVisible();
  expect(within(task).getByText('當日完成')).toBeVisible();
  expect(within(task).getByText('核對')).toBeVisible();
  const taskBadge = await within(task).findByRole('button', { name: '來源 1 筆，待核對' });
  expect(within(task).getAllByRole('button', { name: /來源 .*筆/ })).toHaveLength(1);
  const capabilityBadge = screen.getByRole('button', { name: '來源 1 筆' });
  await userEvent.click(taskBadge);
  expect(await screen.findByRole('heading', { name: '原引用正文' })).toBeVisible();
  expect(screen.queryByText('核對能力依據')).not.toBeInTheDocument();
  await userEvent.click(screen.getByRole('button', { name: '關閉來源面板' }));
  await userEvent.click(capabilityBadge);
  expect(await screen.findByText('共用技能的固定依據')).toBeVisible();
  expect(screen.queryByRole('heading', { name: '原引用正文' })).not.toBeInTheDocument();
});
