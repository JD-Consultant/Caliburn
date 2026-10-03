/** Only the new collection behavior is tested here; recovery uses the shared command owner. */
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, beforeEach, expect, test, vi } from 'vitest';
import type { JdWorkView } from '../../shared/api/generated/jd-work-view';
import { JdWorkEditor } from './JdWorkEditor';
import { isWorkCommand } from './jd-work-api';

const fileId = '10000000-0000-4000-8000-000000000001';
const revision = '20000000-0000-4000-8000-000000000002';
const collaboratorId = '30000000-0000-4000-8000-000000000003';
const conditionId = '40000000-0000-4000-8000-000000000004';
const original: JdWorkView = {
  revision_id: revision,
  areas: [],
  tasks: [],
  capabilities: [],
  task_links: [],
  collaborators: [
    { collaborator_id: collaboratorId, name: '設計同事', scope_text: '確認交付範圍' },
  ],
  conditions: [{ condition_id: conditionId, kind: 'schedule_travel', text: '依約支援上線。' }],
};
const clients: QueryClient[] = [];
function renderEditor() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  clients.push(client);
  return render(
    <QueryClientProvider client={client}>
      <JdWorkEditor jobFileId={fileId} />
    </QueryClientProvider>,
  );
}
function mockServer() {
  const fetch = vi.fn<(path: string, options?: RequestInit) => Promise<Response>>();
  fetch.mockImplementation((path, options) =>
    Promise.resolve(
      Response.json(
        options?.method !== 'POST'
          ? original
          : path.endsWith('/collaborators')
            ? { revision_id: revision, collaborators: original.collaborators }
            : { revision_id: revision, conditions: original.conditions },
      ),
    ),
  );
  vi.stubGlobal('fetch', fetch);
  return fetch;
}
beforeEach(() => sessionStorage.clear());
afterEach(() => {
  clients.splice(0).forEach((client) => client.clear());
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
});

test('協作對象可先填範圍不猜名稱，送出目前基底', async () => {
  const fetch = mockServer();
  renderEditor();
  await userEvent.click(await screen.findByRole('button', { name: '新增協作對象' }));
  await userEvent.type(screen.getByRole('textbox', { name: '協作範圍' }), '協助確認介面狀態');
  await userEvent.click(screen.getByRole('button', { name: '儲存協作對象' }));
  await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument());
  const write = fetch.mock.calls.find(([, options]) => options?.method === 'POST');
  expect(write?.[0]).toBe(`/api/job-files/${fileId}/jd/collaborators`);
  expect(typeof write?.[1]?.body === 'string' ? JSON.parse(write[1].body) : null).toMatchObject({
    expected_revision_id: revision,
    change: { action: 'create_collaborator', name: null, scope_text: '協助確認介面狀態' },
  });
});

test('條件只有空白時不送出，草稿不污染讀取資料', async () => {
  const fetch = mockServer();
  renderEditor();
  await userEvent.click(await screen.findByText('依約支援上線。'));
  const field = await screen.findByRole('textbox', { name: '條件內容' });
  await userEvent.clear(field);
  await userEvent.type(field, '   ');
  await userEvent.click(screen.getByRole('button', { name: '儲存' }));
  expect(screen.getByRole('alert')).toHaveTextContent('不能是空白');
  expect(fetch.mock.calls.filter(([, options]) => options?.method === 'POST')).toHaveLength(0);
  await userEvent.click(screen.getByRole('button', { name: '取消' }));
  expect(
    within(screen.getByRole('region', { name: '工時與出差' })).getByText('依約支援上線。'),
  ).toBeVisible();
});

test.each(['collaborators', 'conditions'] as const)(
  '%s 未確認命令重開後仍原樣接續',
  async (collection) => {
    const pending = {
      collection,
      request: {
        command_id: '50000000-0000-4000-8000-000000000005',
        expected_revision_id: revision,
        change:
          collection === 'collaborators'
            ? { action: 'delete_collaborator', collaborator_id: collaboratorId }
            : { action: 'delete_condition', condition_id: conditionId },
      },
    };
    expect(isWorkCommand(pending)).toBe(true);
    sessionStorage.setItem(`caliburn.pending-jd-work.${fileId}`, JSON.stringify(pending));
    const fetch = mockServer();
    renderEditor();
    expect(await screen.findByRole('button', { name: '新增協作對象' })).toBeDisabled();
    expect(screen.getByRole('button', { name: '新增條件' })).toBeDisabled();
    await userEvent.click(screen.getByRole('button', { name: '重新確認修改結果' }));
    await waitFor(() =>
      expect(sessionStorage.getItem(`caliburn.pending-jd-work.${fileId}`)).toBeNull(),
    );
    const write = fetch.mock.calls.find(([, options]) => options?.method === 'POST');
    expect(write?.[0]).toBe(`/api/job-files/${fileId}/jd/${collection}`);
    expect(typeof write?.[1]?.body === 'string' ? JSON.parse(write[1].body) : null).toEqual(
      pending.request,
    );
  },
);
