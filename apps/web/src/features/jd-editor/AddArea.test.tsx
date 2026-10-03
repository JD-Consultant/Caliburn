/** A responsibility is added where it will appear (Things, Notion, Linear): a row at the end of the list becomes a field. */
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, beforeEach, expect, test, vi } from 'vitest';
import type { JdWorkView } from '../../shared/api/generated/jd-work-view';
import { JdWorkEditor } from './JdWorkEditor';

const fileId = '10000000-0000-4000-8000-000000000001';
const revision = '20000000-0000-4000-8000-000000000002';
const areaId = '30000000-0000-4000-8000-000000000003';
const empty: JdWorkView = {
  revision_id: revision,
  areas: [],
  tasks: [],
  capabilities: [],
  task_links: [],
  collaborators: [],
  conditions: [],
};
const clients: QueryClient[] = [];

function renderEditor(readOnly = false) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  clients.push(client);
  return render(
    <QueryClientProvider client={client}>
      <JdWorkEditor key={fileId} jobFileId={fileId} readOnly={readOnly} />
    </QueryClientProvider>,
  );
}

type Answer = (attempt: number) => Promise<Response>;

/** Serves `view`, answers each write with `answer` and, once a write was accepted, serves the saved view. */
function stubServer(view: JdWorkView = empty, answer?: Answer) {
  let attempt = 0;
  let saved = false;
  const created: JdWorkView = {
    ...view,
    areas: [{ area_id: areaId, title: '網站交付', scope_text: null }],
  };
  const fetch = vi.fn<(path: string, options?: RequestInit) => Promise<Response>>();
  fetch.mockImplementation((_path, options) => {
    if (options?.method !== 'POST') return Promise.resolve(Response.json(saved ? created : view));
    attempt += 1;
    if (answer) return answer(attempt);
    saved = true;
    return Promise.resolve(Response.json({ revision_id: revision, areas: created.areas }));
  });
  vi.stubGlobal('fetch', fetch);
  return {
    writes: () =>
      fetch.mock.calls
        .filter(([, options]) => options?.method === 'POST')
        .map(([path, options]) => {
          const body: unknown = typeof options?.body === 'string' ? JSON.parse(options.body) : null;
          return { path, body };
        }),
    markSaved: () => {
      saved = true;
    },
  };
}

beforeEach(() => sessionStorage.clear());
afterEach(() => {
  clients.splice(0).forEach((client) => client.clear());
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
});

test('「新增職責」在列表末端變成欄位：Enter 只送職責名稱與開啟時的修訂，不開對話框，焦點回到新增鈕', async () => {
  const server = stubServer();
  renderEditor();
  await userEvent.click(await screen.findByRole('button', { name: '新增職責' }));
  const field = await screen.findByRole('textbox', { name: '職責名稱' });
  expect(field).toHaveFocus();
  expect(screen.queryByRole('dialog')).not.toBeInTheDocument();

  await userEvent.type(field, '網站交付{Enter}');

  expect(await screen.findByRole('heading', { name: '網站交付' })).toBeVisible();
  expect(server.writes()).toHaveLength(1);
  expect(server.writes()[0]).toMatchObject({
    path: `/api/job-files/${fileId}/jd/areas`,
    body: {
      expected_revision_id: revision,
      change: { action: 'create_area', title: '網站交付', scope_text: null },
    },
  });
  // Ready for the next one: the editor is gone and the add button has focus again.
  await waitFor(() =>
    expect(screen.queryByRole('textbox', { name: '職責名稱' })).not.toBeInTheDocument(),
  );
  await waitFor(() => expect(screen.getByRole('button', { name: '新增職責' })).toHaveFocus());
});

test('an empty name closes without a request, white space is refused with a reason, and Esc leaves', async () => {
  const server = stubServer();
  renderEditor();
  await userEvent.click(await screen.findByRole('button', { name: '新增職責' }));
  await userEvent.click(await screen.findByRole('button', { name: '儲存' }));
  expect(screen.queryByRole('textbox', { name: '職責名稱' })).not.toBeInTheDocument();

  await userEvent.click(screen.getByRole('button', { name: '新增職責' }));
  const field = await screen.findByRole('textbox', { name: '職責名稱' });
  await userEvent.type(field, '   ');
  await userEvent.click(screen.getByRole('button', { name: '儲存' }));
  expect(screen.getByRole('alert')).toHaveTextContent('不能是空白');
  expect(field).toHaveValue('   ');

  await userEvent.keyboard('{Escape}');
  expect(screen.queryByRole('textbox', { name: '職責名稱' })).not.toBeInTheDocument();
  expect(screen.getByRole('button', { name: '新增職責' })).toHaveFocus();
  expect(server.writes()).toHaveLength(0);
});

test('a lost response keeps the name in the field, which re-confirms the same command from there', async () => {
  const server = stubServer(empty, (attempt) =>
    attempt === 1
      ? Promise.reject(new TypeError('lost response'))
      : Promise.resolve(Response.json({ revision_id: revision, areas: [] })),
  );
  renderEditor();
  await userEvent.click(await screen.findByRole('button', { name: '新增職責' }));
  const field = await screen.findByRole('textbox', { name: '職責名稱' });
  await userEvent.type(field, '網站交付{Enter}');

  expect(await screen.findByRole('alert')).toHaveTextContent('JD 修改結果尚未確認');
  expect(field).toHaveValue('網站交付');
  expect(field).toBeDisabled();
  await userEvent.click(screen.getByRole('button', { name: '重新確認修改結果' }));
  await waitFor(() =>
    expect(screen.queryByRole('textbox', { name: '職責名稱' })).not.toBeInTheDocument(),
  );
  expect(server.writes()).toHaveLength(2);
  expect(server.writes()[1]).toEqual(server.writes()[0]);
  expect(sessionStorage.length).toBe(0);
});

test('the add button waits while the JD is read-only or another command is unconfirmed', async () => {
  stubServer();
  const { unmount } = renderEditor(true);
  expect(await screen.findByRole('button', { name: '新增職責' })).toHaveAttribute(
    'aria-disabled',
    'true',
  );
  await userEvent.click(screen.getByRole('button', { name: '新增職責' }));
  expect(screen.queryByRole('textbox', { name: '職責名稱' })).not.toBeInTheDocument();
  unmount();

  sessionStorage.setItem(`caliburn.pending-jd-work.${fileId}`, '{broken');
  renderEditor();
  expect(await screen.findByRole('alert')).toHaveTextContent('無法讀取待確認修改');
  expect(await screen.findByRole('button', { name: '新增職責' })).toHaveAttribute(
    'aria-disabled',
    'true',
  );
});
