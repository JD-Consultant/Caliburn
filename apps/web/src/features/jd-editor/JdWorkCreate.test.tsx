import { formalJdQueries } from './jd-queries';
import { refreshQueries } from '../../shared/api/refresh-queries';
/** New items still come from a form (Linear keeps creation apart from in-place editing); edits do not. */
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
const clients: QueryClient[] = [];

const jd: JdWorkView = {
  revision_id: revision,
  areas: [
    { area_id: siteId, title: '網站交付', scope_text: null },
    { area_id: upkeepId, title: '網站維護', scope_text: null },
  ],
  tasks: [],
  capabilities: [],
  task_links: [],
  collaborators: [],
  conditions: [],
};

function renderEditor() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  clients.push(client);
  return render(
    <QueryClientProvider client={client}>
      <JdWorkEditor
        refresh={() => refreshQueries(client, formalJdQueries(fileId))}
        key={fileId}
        jobFileId={fileId}
      />
    </QueryClientProvider>,
  );
}

function stubServer() {
  const fetch = vi.fn<(path: string, options?: RequestInit) => Promise<Response>>();
  fetch.mockImplementation((path, options) => {
    if (options?.method !== 'POST') return Promise.resolve(Response.json(jd));
    return Promise.resolve(
      Response.json(
        path.endsWith('/conditions')
          ? { revision_id: revision, conditions: [] }
          : { revision_id: revision, tasks: [] },
      ),
    );
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

// About a dozen interactions with a dialog: 2-3 s alone, past the default 5 s when the whole suite shares a busy machine.
test(
  'a new task starts in the responsibility it was added from and is sent as one create_task',
  { timeout: 15_000 },
  async () => {
    const server = stubServer();
    renderEditor();
    const upkeep = await screen.findByRole('region', { name: '網站維護' });
    await userEvent.click(within(upkeep).getByRole('button', { name: '新增任務' }));

    expect(screen.getByRole('dialog', { name: '新增任務' })).toBeVisible();
    expect(screen.getByRole('combobox', { name: '所屬職責' })).toHaveTextContent('網站維護');
    // Pasting keeps this long form quick enough for a busy machine; typing is covered elsewhere.
    async function fill(name: string, text: string): Promise<void> {
      await userEvent.click(screen.getByRole('textbox', { name }));
      await userEvent.paste(text);
    }
    await fill('任務名稱', '維護網頁');
    await fill('工作內容', '修正已知缺陷');
    await userEvent.click(screen.getByRole('button', { name: '新增工作成果' }));
    await fill('工作成果 1', '缺陷已修正');
    await userEvent.click(screen.getByRole('button', { name: '新增工作成果' }));
    await fill('工作成果 2', '之後會移除');
    await userEvent.click(screen.getByRole('button', { name: '移除工作成果 2' }));
    await userEvent.click(screen.getByRole('button', { name: '新增工作要求' }));
    await fill('工作要求 1', '核對主要流程');
    await userEvent.click(screen.getByRole('button', { name: '儲存任務' }));

    await waitFor(() => expect(server.writes()).toHaveLength(1));
    expect(server.writes()[0]).toMatchObject({
      expected_revision_id: revision,
      change: {
        action: 'create_task',
        area_id: upkeepId,
        title: '維護網頁',
        description: '修正已知缺陷',
        outcomes: ['缺陷已修正'],
        requirements: ['核對主要流程'],
      },
    });
  },
);

test('a new condition needs a category and a text, and is sent as one create_condition', async () => {
  const server = stubServer();
  renderEditor();
  await userEvent.click(await screen.findByRole('button', { name: '新增條件' }));

  expect(screen.getByRole('dialog', { name: '新增條件' })).toBeVisible();
  await userEvent.click(screen.getByRole('button', { name: '儲存條件' }));
  expect(screen.getByRole('alert')).toHaveTextContent('請選擇條件分類並填寫內容');
  expect(server.writes()).toHaveLength(0);

  await userEvent.click(screen.getByRole('combobox', { name: '條件分類' }));
  await userEvent.click(screen.getByRole('option', { name: '必要資格' }));
  await userEvent.type(screen.getByRole('textbox', { name: '條件內容' }), '具備相關證照');
  await userEvent.click(screen.getByRole('button', { name: '儲存條件' }));

  await waitFor(() => expect(server.writes()).toHaveLength(1));
  expect(server.writes()[0]).toMatchObject({
    change: { action: 'create_condition', kind: 'qualification', text: '具備相關證照' },
  });
});
