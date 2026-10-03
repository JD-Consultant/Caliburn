/** Structure changes that used to need the ✎ form: move, add and remove. Edits to text are in InlineEdit.test. */
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, beforeEach, expect, test, vi } from 'vitest';
import { JdWorkEditor } from './JdWorkEditor';
import type { JdWorkView } from '../../shared/api/generated/jd-work-view';

const fileId = '10000000-0000-4000-8000-000000000001';
const revision = '20000000-0000-4000-8000-000000000002';
const siteId = '30000000-0000-4000-8000-000000000003';
const upkeepId = '31000000-0000-4000-8000-000000000003';
const taskId = '40000000-0000-4000-8000-000000000004';
const outcomeId = '50000000-0000-4000-8000-000000000005';
const conditionId = '60000000-0000-4000-8000-000000000006';
const knowledgeId = '70000000-0000-4000-8000-000000000007';
const collaboratorId = '80000000-0000-4000-8000-000000000008';
const clients: QueryClient[] = [];

const jd: JdWorkView = {
  revision_id: revision,
  areas: [
    { area_id: siteId, title: '網站交付', scope_text: '約定範圍' },
    { area_id: upkeepId, title: '網站維護', scope_text: null },
  ],
  tasks: [
    {
      task_id: taskId,
      area_id: siteId,
      title: '實作網頁',
      description: '依需求實作',
      outcomes: [{ detail_id: outcomeId, text: '可操作頁面' }],
      requirements: [],
    },
  ],
  capabilities: [
    { capability_id: knowledgeId, kind: 'knowledge', name: '資料介面', description: '理解狀態' },
  ],
  task_links: [],
  collaborators: [{ collaborator_id: collaboratorId, name: '設計同事', scope_text: '提供視覺稿' }],
  conditions: [{ condition_id: conditionId, kind: 'schedule_travel', text: '依約支援上線。' }],
};

function renderEditor() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  clients.push(client);
  return render(
    <QueryClientProvider client={client}>
      <JdWorkEditor key={fileId} jobFileId={fileId} />
    </QueryClientProvider>,
  );
}

/** Serves the JD and records every write; each write is accepted with the collection view it names. */
function stubServer() {
  const fetch = vi.fn<(path: string, options?: RequestInit) => Promise<Response>>();
  fetch.mockImplementation((path, options) => {
    if (options?.method !== 'POST') return Promise.resolve(Response.json(jd));
    switch (path.slice(path.lastIndexOf('/') + 1)) {
      case 'conditions':
        return Promise.resolve(Response.json({ revision_id: revision, conditions: jd.conditions }));
      default:
        return Promise.resolve(Response.json({ revision_id: revision, tasks: jd.tasks }));
    }
  });
  vi.stubGlobal('fetch', fetch);
  return {
    writes: () =>
      fetch.mock.calls
        .filter(([, options]) => options?.method === 'POST')
        .map(([, options]) => {
          const body: unknown = typeof options?.body === 'string' ? JSON.parse(options.body) : null;
          return body;
        }),
  };
}

beforeEach(() => sessionStorage.clear());
afterEach(() => {
  clients.splice(0).forEach((client) => client.clear());
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
});

test('a task moves to another responsibility from a menu: one move_task, no dialog', async () => {
  const server = stubServer();
  renderEditor();
  const task = await screen.findByRole('article', { name: '實作網頁' });
  await userEvent.click(within(task).getByRole('button', { name: '移到其他職責' }));

  const menu = screen.getByRole('menu', { name: '移到職責' });
  const choices = within(menu).getAllByRole('menuitemradio');
  expect(choices.map((choice) => choice.textContent)).toEqual([
    '網站交付',
    '網站維護',
    '未歸屬任務',
  ]);
  expect(within(menu).getByRole('menuitemradio', { name: '網站交付' })).toBeChecked();
  await userEvent.click(within(menu).getByRole('menuitemradio', { name: '網站維護' }));

  await waitFor(() => expect(server.writes()).toHaveLength(1));
  expect(server.writes()[0]).toMatchObject({
    expected_revision_id: revision,
    change: {
      action: 'move_task',
      task_id: taskId,
      area_id: upkeepId,
      before_task_id: null,
      changes: [],
    },
  });
  expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
});

test('a task moves out of every responsibility with area_id null, not a made-up group', async () => {
  const server = stubServer();
  renderEditor();
  const task = await screen.findByRole('article', { name: '實作網頁' });
  await userEvent.click(within(task).getByRole('button', { name: '移到其他職責' }));
  await userEvent.click(screen.getByRole('menuitemradio', { name: '未歸屬任務' }));

  await waitFor(() => expect(server.writes()).toHaveLength(1));
  expect(server.writes()[0]).toMatchObject({ change: { action: 'move_task', area_id: null } });
});

test('choosing where the task already is, or pressing Esc, sends nothing', async () => {
  const server = stubServer();
  renderEditor();
  const task = await screen.findByRole('article', { name: '實作網頁' });
  const trigger = within(task).getByRole('button', { name: '移到其他職責' });

  await userEvent.click(trigger);
  await userEvent.click(screen.getByRole('menuitemradio', { name: '網站交付' }));
  await waitFor(() => expect(screen.queryByRole('menu')).not.toBeInTheDocument());

  await userEvent.click(trigger);
  expect(screen.getByRole('menu', { name: '移到職責' })).toBeVisible();
  await userEvent.keyboard('{Escape}');
  await waitFor(() => expect(screen.queryByRole('menu')).not.toBeInTheDocument());
  expect(server.writes()).toHaveLength(0);
});

test('a condition is moved to another category from the same kind of menu', async () => {
  const server = stubServer();
  renderEditor();
  const condition = await screen.findByRole('article', { name: '工時與出差 1' });
  await userEvent.click(within(condition).getByRole('button', { name: '移到其他分類' }));

  const menu = screen.getByRole('menu', { name: '移到分類' });
  expect(within(menu).getByRole('menuitemradio', { name: '工時與出差' })).toBeChecked();
  await userEvent.click(within(menu).getByRole('menuitemradio', { name: '共通協作界線' }));

  await waitFor(() => expect(server.writes()).toHaveLength(1));
  expect(server.writes()[0]).toMatchObject({
    expected_revision_id: revision,
    change: {
      action: 'revise_condition',
      condition_id: conditionId,
      changes: [{ field: 'kind', value: 'shared_collaboration' }],
    },
  });
});

test('an outcome is added at the end of its list: the add button opens an empty editor', async () => {
  const server = stubServer();
  renderEditor();
  const task = await screen.findByRole('article', { name: '實作網頁' });
  await userEvent.click(within(task).getByRole('button', { name: '新增工作成果' }));
  const field = await screen.findByRole('textbox', { name: '工作成果 2' });
  expect(field).toHaveValue('');
  expect(field).toHaveFocus();

  await userEvent.type(field, '交接說明{Control>}{Enter}{/Control}');
  await waitFor(() => expect(server.writes()).toHaveLength(1));
  expect(server.writes()[0]).toMatchObject({
    expected_revision_id: revision,
    change: {
      action: 'revise_task',
      task_id: taskId,
      changes: [{ action: 'add_detail', kind: 'outcome', text: '交接說明' }],
    },
  });
  expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
});

test('a requirement can be added to an empty list, and an empty or abandoned draft sends nothing', async () => {
  const server = stubServer();
  renderEditor();
  const task = await screen.findByRole('article', { name: '實作網頁' });
  await userEvent.click(within(task).getByRole('button', { name: '新增工作要求' }));
  expect(await screen.findByRole('textbox', { name: '工作要求 1' })).toHaveFocus();

  await userEvent.click(screen.getByRole('button', { name: '儲存' }));
  expect(screen.queryByRole('textbox', { name: '工作要求 1' })).not.toBeInTheDocument();
  await userEvent.click(within(task).getByRole('button', { name: '新增工作要求' }));
  await userEvent.type(await screen.findByRole('textbox', { name: '工作要求 1' }), '草稿{Escape}');
  expect(screen.queryByRole('textbox', { name: '工作要求 1' })).not.toBeInTheDocument();
  expect(server.writes()).toHaveLength(0);
});

test('removing an outcome asks first, then sends one remove_detail', async () => {
  const server = stubServer();
  renderEditor();
  const task = await screen.findByRole('article', { name: '實作網頁' });
  await userEvent.click(within(task).getByRole('button', { name: '刪除工作成果 1' }));

  const dialog = screen.getByRole('dialog');
  expect(dialog).toHaveTextContent('可操作頁面');
  expect(server.writes()).toHaveLength(0);
  await userEvent.click(within(dialog).getByRole('button', { name: '確認刪除工作成果' }));

  await waitFor(() => expect(server.writes()).toHaveLength(1));
  expect(server.writes()[0]).toMatchObject({
    expected_revision_id: revision,
    change: {
      action: 'revise_task',
      task_id: taskId,
      changes: [{ action: 'remove_detail', detail_id: outcomeId }],
    },
  });
});

test('no item has an edit-everything button any more; text is edited where it is', async () => {
  stubServer();
  renderEditor();
  await screen.findByRole('article', { name: '實作網頁' });

  expect(screen.queryAllByRole('button', { name: /^編輯/ })).toHaveLength(0);
  expect(screen.getByText('點任何文字即可直接修改。')).toBeInTheDocument();
});
