import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, beforeEach, expect, test, vi } from 'vitest';
import { JdWorkEditor } from './JdWorkEditor';
import { jdWorkQuery } from './jd-work-api';
import type { JdWorkView } from '../../shared/api/generated/jd-work-view';

const fileId = '10000000-0000-4000-8000-000000000001';
const revision = '20000000-0000-4000-8000-000000000002';
const areaId = '30000000-0000-4000-8000-000000000003';
const taskId = '40000000-0000-4000-8000-000000000004';
const clients: QueryClient[] = [];

const jd: JdWorkView = {
  revision_id: revision,
  areas: [{ area_id: areaId, title: '網站交付', scope_text: '原範圍' }],
  tasks: [
    {
      task_id: taskId,
      area_id: areaId,
      title: '實作網頁',
      description: '原工作內容',
      outcomes: [],
      requirements: [],
    },
  ],
  capabilities: [],
  task_links: [],
  collaborators: [],
  conditions: [],
};

function renderEditor(readOnly = false) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  clients.push(client);
  const page = (locked: boolean) => (
    <QueryClientProvider client={client}>
      <JdWorkEditor key={fileId} jobFileId={fileId} readOnly={locked} />
    </QueryClientProvider>
  );
  const view = render(page(readOnly));
  return { client, setReadOnly: (locked: boolean) => view.rerender(page(locked)) };
}

type Answer = (attempt: number, path: string) => Promise<Response>;

/** What the server returns for an accepted write: the collection view the endpoint is named after. */
function accepted(path: string, view: JdWorkView): Response {
  switch (path.slice(path.lastIndexOf('/') + 1)) {
    case 'areas':
      return Response.json({ revision_id: revision, areas: view.areas });
    case 'capabilities':
      return Response.json({
        revision_id: revision,
        capabilities: view.capabilities,
        task_links: view.task_links,
      });
    case 'collaborators':
      return Response.json({ revision_id: revision, collaborators: view.collaborators });
    case 'conditions':
      return Response.json({ revision_id: revision, conditions: view.conditions });
    default:
      return Response.json({ revision_id: revision, tasks: view.tasks });
  }
}

/** Serves `view` and records every write; each write is answered by `answer` (default: accepted). */
function stubServer(answer?: Answer, view: JdWorkView = jd) {
  let attempt = 0;
  const fetch = vi.fn<(path: string, options?: RequestInit) => Promise<Response>>();
  fetch.mockImplementation((path, options) => {
    if (options?.method !== 'POST') return Promise.resolve(Response.json(view));
    attempt += 1;
    return answer ? answer(attempt, path) : Promise.resolve(accepted(path, view));
  });
  vi.stubGlobal('fetch', fetch);
  const posts = () => fetch.mock.calls.filter(([, options]) => options?.method === 'POST');
  return {
    writes: () =>
      posts().map(([, options]) => {
        const body: unknown = typeof options?.body === 'string' ? JSON.parse(options.body) : null;
        return body;
      }),
    paths: () => posts().map(([path]) => path),
  };
}

beforeEach(() => sessionStorage.clear());
afterEach(() => {
  clients.splice(0).forEach((client) => client.clear());
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
});

test('click a task name to edit it in place: Enter sends one change for that field at the opening revision, no dialog', async () => {
  const server = stubServer();
  renderEditor();
  await userEvent.click(await screen.findByRole('heading', { name: '實作網頁' }));
  const field = await screen.findByRole('textbox', { name: '任務名稱' });
  expect(field).toHaveValue('實作網頁');
  expect(screen.queryByRole('dialog')).not.toBeInTheDocument();

  await userEvent.clear(field);
  await userEvent.type(field, '改寫網頁{Enter}');

  await waitFor(() =>
    expect(screen.queryByRole('textbox', { name: '任務名稱' })).not.toBeInTheDocument(),
  );
  expect(server.writes()).toHaveLength(1);
  expect(server.writes()[0]).toMatchObject({
    expected_revision_id: revision,
    change: {
      action: 'revise_task',
      task_id: taskId,
      changes: [{ action: 'set_field', field: 'title', value: '改寫網頁' }],
    },
  });
});

test('Esc abandons the edit without any request', async () => {
  const server = stubServer();
  renderEditor();
  await userEvent.click(await screen.findByRole('heading', { name: '實作網頁' }));
  await userEvent.type(await screen.findByRole('textbox', { name: '任務名稱' }), '草稿{Escape}');

  expect(screen.queryByRole('textbox', { name: '任務名稱' })).not.toBeInTheDocument();
  expect(screen.getByRole('heading', { name: '實作網頁' })).toBeVisible();
  expect(server.writes()).toHaveLength(0);
});

test('saving without a change closes the editor and sends nothing', async () => {
  const server = stubServer();
  renderEditor();
  await userEvent.click(await screen.findByRole('heading', { name: '實作網頁' }));
  await userEvent.click(await screen.findByRole('button', { name: '儲存' }));

  expect(screen.queryByRole('textbox', { name: '任務名稱' })).not.toBeInTheDocument();
  expect(server.writes()).toHaveLength(0);
});

test('Save and Cancel keep their names and their hints say which key does the same', async () => {
  stubServer();
  renderEditor();
  await userEvent.click(await screen.findByRole('heading', { name: '實作網頁' }));
  expect(await screen.findByRole('button', { name: '儲存' })).toHaveAttribute(
    'title',
    '儲存（Enter）',
  );
  expect(screen.getByRole('button', { name: '取消' })).toHaveAttribute('title', '取消（Esc）');

  await userEvent.keyboard('{Escape}');
  await userEvent.click(await screen.findByText('原工作內容'));
  expect(await screen.findByRole('button', { name: '儲存' })).toHaveAttribute(
    'title',
    '儲存（Ctrl／⌘＋Enter）',
  );
});

test('a multi-line field keeps Enter for new lines and saves with Ctrl+Enter', async () => {
  const server = stubServer();
  renderEditor();
  await userEvent.click(await screen.findByText('原工作內容'));
  const field = await screen.findByRole('textbox', { name: '工作內容' });

  await userEvent.type(field, '{Enter}第二行');
  expect(field).toHaveValue('原工作內容\n第二行');
  expect(server.writes()).toHaveLength(0);

  await userEvent.keyboard('{Control>}{Enter}{/Control}');
  await waitFor(() => expect(server.writes()).toHaveLength(1));
  expect(server.writes()[0]).toMatchObject({
    change: {
      action: 'revise_task',
      changes: [{ action: 'set_field', field: 'description', value: '原工作內容\n第二行' }],
    },
  });
});

test.each([
  {
    name: 'responsibility scope',
    text: '原範圍',
    textbox: '職責範圍',
    section: '職責 網站交付',
    change: {
      action: 'revise_area',
      area_id: areaId,
      changes: [{ field: 'scope_text', value: '未提交草稿\n第二行' }],
    },
  },
  {
    name: 'task description',
    text: '原工作內容',
    textbox: '工作內容',
    section: '任務 實作網頁',
    change: {
      action: 'revise_task',
      task_id: taskId,
      changes: [{ action: 'set_field', field: 'description', value: '未提交草稿\n第二行' }],
    },
  },
])('folding $name keeps the unsent draft and its opening revision', async (example) => {
  const server = stubServer();
  const { client } = renderEditor();
  await userEvent.click(await screen.findByText(example.text));
  const field = await screen.findByRole('textbox', { name: example.textbox });
  await userEvent.clear(field);
  await userEvent.type(field, '未提交草稿{Enter}第二行');

  await userEvent.click(screen.getByRole('button', { name: `收合${example.section}` }));
  expect(field).not.toBeVisible();
  expect(server.writes()).toHaveLength(0);
  act(() => {
    client.setQueryData(jdWorkQuery(fileId).queryKey, {
      ...jd,
      revision_id: '70000000-0000-4000-8000-000000000007',
    });
  });
  await userEvent.click(screen.getByRole('button', { name: `展開${example.section}` }));

  expect(screen.getByRole('textbox', { name: example.textbox })).toHaveValue('未提交草稿\n第二行');
  await userEvent.click(screen.getByRole('button', { name: '儲存' }));
  await waitFor(() => expect(server.writes()).toHaveLength(1));
  expect(server.writes()[0]).toMatchObject({
    expected_revision_id: revision,
    change: example.change,
  });
});

test('emptying an optional field clears it with null, not an empty string', async () => {
  const server = stubServer();
  renderEditor();
  await userEvent.click(await screen.findByText('原工作內容'));
  await userEvent.clear(await screen.findByRole('textbox', { name: '工作內容' }));
  await userEvent.click(screen.getByRole('button', { name: '儲存' }));

  await waitFor(() => expect(server.writes()).toHaveLength(1));
  expect(server.writes()[0]).toMatchObject({
    change: { changes: [{ action: 'set_field', field: 'description', value: null }] },
  });
});

test('whitespace only is refused with a reason; the draft stays and nothing is sent', async () => {
  const server = stubServer();
  renderEditor();
  await userEvent.click(await screen.findByRole('heading', { name: '實作網頁' }));
  const field = await screen.findByRole('textbox', { name: '任務名稱' });
  await userEvent.clear(field);
  await userEvent.type(field, '   ');
  await userEvent.click(screen.getByRole('button', { name: '儲存' }));

  expect(screen.getByRole('alert')).toHaveTextContent('不能是空白');
  expect(field).toHaveValue('   ');
  expect(server.writes()).toHaveLength(0);
});

test('keyboard: the edit button opens the editor with focus in it, and Esc returns focus to the button', async () => {
  stubServer();
  renderEditor();
  const edit = await screen.findByRole('button', { name: '修改任務名稱' });
  edit.focus();
  await userEvent.keyboard('{Enter}');

  expect(await screen.findByRole('textbox', { name: '任務名稱' })).toHaveFocus();
  await userEvent.keyboard('{Escape}');
  expect(screen.getByRole('button', { name: '修改任務名稱' })).toHaveFocus();
});

async function typeTaskName(text: string): Promise<HTMLElement> {
  await userEvent.click(await screen.findByRole('heading', { name: '實作網頁' }));
  const field = await screen.findByRole('textbox', { name: '任務名稱' });
  await userEvent.clear(field);
  await userEvent.type(field, `${text}{Enter}`);
  return field;
}

const lostThenAccepted = (attempt: number): Promise<Response> =>
  attempt === 1
    ? Promise.reject(new TypeError('lost response'))
    : Promise.resolve(Response.json({ revision_id: revision, tasks: jd.tasks }));

test('a lost response keeps the draft in the editor, which re-confirms the same command from there', async () => {
  const server = stubServer(lostThenAccepted);
  renderEditor();
  const field = await typeTaskName('改寫網頁');

  expect(await screen.findByRole('alert')).toHaveTextContent('JD 修改結果尚未確認');
  expect(field).toHaveValue('改寫網頁');
  expect(field).toBeDisabled();
  // One re-confirm button, inside the editor: the page banner stands down while an editor is open.
  expect(screen.getAllByRole('button', { name: '重新確認修改結果' })).toHaveLength(1);
  expect(screen.queryByRole('button', { name: '儲存' })).not.toBeInTheDocument();

  await userEvent.click(screen.getByRole('button', { name: '重新確認修改結果' }));
  await waitFor(() =>
    expect(screen.queryByRole('textbox', { name: '任務名稱' })).not.toBeInTheDocument(),
  );
  expect(server.writes()).toHaveLength(2);
  expect(server.writes()[1]).toEqual(server.writes()[0]);
  expect(sessionStorage.length).toBe(0);
});

test('leaving the editor with an unconfirmed result hands the re-confirmation to the page', async () => {
  const server = stubServer(lostThenAccepted);
  renderEditor();
  await typeTaskName('改寫網頁');
  await screen.findByRole('alert');

  await userEvent.click(screen.getByRole('button', { name: '取消' }));
  expect(screen.queryByRole('textbox', { name: '任務名稱' })).not.toBeInTheDocument();
  expect(screen.getByRole('alert')).toHaveTextContent('JD 修改結果尚未確認');

  await userEvent.click(screen.getByRole('button', { name: '重新確認修改結果' }));
  await waitFor(() => expect(screen.queryByRole('alert')).not.toBeInTheDocument());
  expect(server.writes()[1]).toEqual(server.writes()[0]);
});

test('a rejected change keeps the draft and asks to read the current JD instead of rebasing', async () => {
  const server = stubServer(() => Promise.resolve(Response.json({}, { status: 409 })));
  renderEditor();
  const field = await typeTaskName('改寫網頁');

  expect(await screen.findByRole('alert')).toHaveTextContent('修改未被接受');
  expect(field).toHaveValue('改寫網頁');
  expect(field).toBeDisabled();
  expect(server.writes()).toHaveLength(1);

  await userEvent.click(screen.getByRole('button', { name: '讀取目前 JD' }));
  await waitFor(() =>
    expect(screen.queryByRole('textbox', { name: '任務名稱' })).not.toBeInTheDocument(),
  );
});

test('a background refresh does not rebase the draft: the write carries the revision the editor opened at', async () => {
  const server = stubServer();
  const { client } = renderEditor();
  await userEvent.click(await screen.findByRole('heading', { name: '實作網頁' }));
  const field = await screen.findByRole('textbox', { name: '任務名稱' });
  act(() => {
    client.setQueryData(jdWorkQuery(fileId).queryKey, {
      ...jd,
      revision_id: '70000000-0000-4000-8000-000000000007',
    });
  });

  await userEvent.type(field, '！{Enter}');
  await waitFor(() => expect(server.writes()).toHaveLength(1));
  expect(server.writes()[0]).toMatchObject({ expected_revision_id: revision });
});

test('an untouched draft closes without writing after the displayed field changes in the background', async () => {
  const server = stubServer();
  const { client } = renderEditor();
  await userEvent.click(await screen.findByRole('heading', { name: '實作網頁' }));
  const field = await screen.findByRole('textbox', { name: '任務名稱' });
  act(() => {
    client.setQueryData(jdWorkQuery(fileId).queryKey, {
      ...jd,
      revision_id: '70000000-0000-4000-8000-000000000007',
      tasks: jd.tasks.map((task) => ({ ...task, title: '背景新版任務' })),
    });
  });
  expect(field).toHaveValue('實作網頁');
  await userEvent.click(screen.getByRole('button', { name: '儲存' }));

  expect(server.writes()).toHaveLength(0);
  expect(screen.queryByRole('textbox', { name: '任務名稱' })).not.toBeInTheDocument();
  expect(screen.getByRole('heading', { name: '背景新版任務' })).toBeVisible();
});

test.each(['本機修改的任務', '背景新版任務'])(
  'a changed draft %s retains its opening revision and handles conflict after a background field change',
  async (draft) => {
    const server = stubServer(() => Promise.resolve(Response.json({}, { status: 409 })));
    const { client } = renderEditor();
    await userEvent.click(await screen.findByRole('heading', { name: '實作網頁' }));
    const field = await screen.findByRole('textbox', { name: '任務名稱' });
    act(() => {
      client.setQueryData(jdWorkQuery(fileId).queryKey, {
        ...jd,
        revision_id: '70000000-0000-4000-8000-000000000007',
        tasks: jd.tasks.map((task) => ({ ...task, title: '背景新版任務' })),
      });
    });
    await userEvent.clear(field);
    await userEvent.type(field, draft);
    await userEvent.click(screen.getByRole('button', { name: '儲存' }));

    expect(await screen.findByRole('alert')).toHaveTextContent('修改未被接受');
    expect(field).toHaveValue(draft);
    expect(server.writes()).toEqual([
      expect.objectContaining({
        expected_revision_id: revision,
        change: {
          action: 'revise_task',
          task_id: taskId,
          changes: [{ action: 'set_field', field: 'title', value: draft }],
        },
      }),
    ]);
  },
);

test('a failed background refresh keeps the work draft, shows the error and blocks new writes until recovery', async () => {
  let current = jd;
  let readFails = false;
  const fetch = vi.fn<(path: string, options?: RequestInit) => Promise<Response>>();
  fetch.mockImplementation((_path, options) => {
    if (options?.method === 'POST') return Promise.resolve(Response.json({}, { status: 409 }));
    return Promise.resolve(readFails ? Response.json({}, { status: 503 }) : Response.json(current));
  });
  vi.stubGlobal('fetch', fetch);
  const { client } = renderEditor();
  await userEvent.click(await screen.findByText('原工作內容'));
  const field = await screen.findByRole('textbox', { name: '工作內容' });
  await userEvent.clear(field);
  await userEvent.type(field, '未提交草稿{Enter}第二行');

  readFails = true;
  await act(async () => {
    await client.invalidateQueries({ queryKey: jdWorkQuery(fileId).queryKey });
  });

  expect(await screen.findByRole('alert')).toBeVisible();
  expect(field).toBeVisible();
  expect(screen.getByRole('textbox', { name: '工作內容' })).toHaveValue('未提交草稿\n第二行');
  expect(field).toBeDisabled();
  expect(screen.getByRole('button', { name: '儲存' })).toBeDisabled();
  expect(screen.getByRole('button', { name: '修改任務名稱' })).toHaveAttribute(
    'aria-disabled',
    'true',
  );
  expect(screen.getByRole('button', { name: '新增職責' })).toHaveAttribute('aria-disabled', 'true');
  const form = field.closest('form');
  if (!form) throw new Error('Missing inline edit form');
  fireEvent.submit(form);
  expect(fetch.mock.calls.filter(([, options]) => options?.method === 'POST')).toHaveLength(0);

  current = { ...jd, revision_id: '70000000-0000-4000-8000-000000000007' };
  readFails = false;
  await userEvent.click(screen.getByRole('button', { name: '重新讀取職責與任務' }));
  await waitFor(() => expect(screen.queryByRole('alert')).not.toBeInTheDocument());
  expect(screen.getByRole('textbox', { name: '工作內容' })).toHaveValue('未提交草稿\n第二行');
  expect(field).toBeEnabled();
  await userEvent.click(screen.getByRole('button', { name: '儲存' }));

  expect(await screen.findByRole('alert')).toHaveTextContent('修改未被接受');
  const posts = fetch.mock.calls.filter(([, options]) => options?.method === 'POST');
  expect(posts).toHaveLength(1);
  const body: unknown =
    typeof posts[0]?.[1]?.body === 'string' ? JSON.parse(posts[0][1].body) : null;
  expect(body).toMatchObject({
    expected_revision_id: revision,
    change: {
      action: 'revise_task',
      task_id: taskId,
      changes: [{ action: 'set_field', field: 'description', value: '未提交草稿\n第二行' }],
    },
  });
});

test('while the request is in flight the editor cannot be changed, saved again or left', async () => {
  let finish: (response: Response) => void = () => {
    throw new Error('Request not started');
  };
  const response = new Promise<Response>((resolve) => {
    finish = resolve;
  });
  stubServer(() => response);
  renderEditor();
  const field = await typeTaskName('改寫網頁');

  expect(field).toBeDisabled();
  expect(screen.getByRole('status')).toHaveTextContent('正在確認修改');
  expect(screen.getByRole('button', { name: '取消' })).toBeDisabled();

  await act(async () => {
    finish(Response.json({ revision_id: revision, tasks: jd.tasks }));
    await response;
  });
  await waitFor(() =>
    expect(screen.queryByRole('textbox', { name: '任務名稱' })).not.toBeInTheDocument(),
  );
});

test('while an editor is open every other edit control waits, and returns once it closes', async () => {
  stubServer();
  renderEditor();
  await userEvent.click(await screen.findByRole('heading', { name: '實作網頁' }));
  await screen.findByRole('textbox', { name: '任務名稱' });

  expect(screen.getByRole('button', { name: '刪除任務' })).toBeDisabled();
  expect(screen.getByRole('button', { name: '新增職責' })).toHaveAttribute('aria-disabled', 'true');
  await userEvent.click(screen.getByText('原工作內容'));
  expect(screen.getAllByRole('textbox')).toHaveLength(1);

  await userEvent.click(screen.getByRole('button', { name: '取消' }));
  expect(screen.getByRole('button', { name: '刪除任務' })).toBeEnabled();
});

test('a read-only JD cannot be edited in place', async () => {
  stubServer();
  renderEditor(true);
  await userEvent.click(await screen.findByRole('heading', { name: '實作網頁' }));

  expect(screen.queryByRole('textbox', { name: '任務名稱' })).not.toBeInTheDocument();
  expect(screen.getByRole('button', { name: '修改任務名稱' })).toHaveAttribute(
    'aria-disabled',
    'true',
  );
});

test('when the JD turns read-only mid-edit the draft is kept but cannot be saved', async () => {
  const server = stubServer();
  const { setReadOnly } = renderEditor();
  await userEvent.click(await screen.findByRole('heading', { name: '實作網頁' }));
  const field = await screen.findByRole('textbox', { name: '任務名稱' });
  await userEvent.type(field, '！');

  setReadOnly(true);
  expect(field).toBeDisabled();
  expect(field).toHaveValue('實作網頁！');
  expect(screen.getByRole('button', { name: '儲存' })).toBeDisabled();
  expect(screen.getByRole('alert')).toHaveTextContent('JD 暫時唯讀');

  setReadOnly(false);
  expect(field).toBeEnabled();
  expect(server.writes()).toHaveLength(0);
});

test('selecting text to copy it does not open the editor', async () => {
  stubServer();
  renderEditor();
  const text = await screen.findByText('原工作內容');
  window.getSelection()?.selectAllChildren(text);
  fireEvent.click(text);

  expect(screen.queryByRole('textbox')).not.toBeInTheDocument();
});

test('if the edited field vanishes while its result is unconfirmed, the page still offers the re-confirmation', async () => {
  const server = stubServer(lostThenAccepted);
  const { client } = renderEditor();
  await typeTaskName('改寫網頁');
  await screen.findByRole('alert');

  act(() => {
    client.setQueryData(jdWorkQuery(fileId).queryKey, {
      ...jd,
      revision_id: '70000000-0000-4000-8000-000000000007',
      tasks: [],
    });
  });
  await waitFor(() =>
    expect(screen.queryByRole('textbox', { name: '任務名稱' })).not.toBeInTheDocument(),
  );
  expect(screen.getByRole('button', { name: '重新確認修改結果' })).toBeEnabled();

  await userEvent.click(screen.getByRole('button', { name: '重新確認修改結果' }));
  await waitFor(() => expect(screen.queryByRole('alert')).not.toBeInTheDocument());
  expect(server.writes()[1]).toEqual(server.writes()[0]);
});

test('after a save by keyboard, focus is back on the edit button even while the page refreshes', async () => {
  stubServer();
  renderEditor();
  const edit = await screen.findByRole('button', { name: '修改任務名稱' });
  edit.focus();
  await userEvent.keyboard('{Enter}');
  await userEvent.keyboard('！{Enter}');

  await waitFor(() =>
    expect(screen.queryByRole('textbox', { name: '任務名稱' })).not.toBeInTheDocument(),
  );
  expect(screen.getByRole('button', { name: '修改任務名稱' })).toHaveFocus();
});

const outcomeId = '50000000-0000-4000-8000-000000000005';
const requirementId = '60000000-0000-4000-8000-000000000006';
const knowledgeId = '80000000-0000-4000-8000-000000000008';
const collaboratorId = '90000000-0000-4000-8000-000000000009';
const conditionId = 'a0000000-0000-4000-8000-00000000000a';

const fullJd: JdWorkView = {
  ...jd,
  tasks: [
    {
      task_id: taskId,
      area_id: areaId,
      title: '實作網頁',
      description: '原工作內容',
      outcomes: [{ detail_id: outcomeId, text: '可操作頁面' }],
      requirements: [{ detail_id: requirementId, text: '核對主要流程' }],
    },
  ],
  capabilities: [
    {
      capability_id: knowledgeId,
      kind: 'knowledge',
      name: 'HTML 基礎',
      description: '標記語言概念',
    },
  ],
  collaborators: [{ collaborator_id: collaboratorId, name: '設計部', scope_text: '提供視覺稿' }],
  conditions: [{ condition_id: conditionId, kind: 'work_environment', text: '辦公室工作' }],
};

const save = '{Control>}{Enter}{/Control}';
const otherFields = [
  {
    name: 'responsibility name',
    click: '網站交付',
    textbox: '職責名稱',
    keys: '二{Enter}',
    path: 'areas',
    change: {
      action: 'revise_area',
      area_id: areaId,
      changes: [{ field: 'title', value: '網站交付二' }],
    },
  },
  {
    name: 'responsibility scope',
    click: '原範圍',
    textbox: '職責範圍',
    keys: `補充${save}`,
    path: 'areas',
    change: {
      action: 'revise_area',
      area_id: areaId,
      changes: [{ field: 'scope_text', value: '原範圍補充' }],
    },
  },
  {
    name: 'an outcome',
    click: '可操作頁面',
    textbox: '工作成果 1',
    keys: `（已驗證）${save}`,
    path: 'tasks',
    change: {
      action: 'revise_task',
      task_id: taskId,
      changes: [{ action: 'revise_detail', detail_id: outcomeId, text: '可操作頁面（已驗證）' }],
    },
  },
  {
    name: 'a requirement',
    click: '核對主要流程',
    textbox: '工作要求 1',
    keys: `（兩次）${save}`,
    path: 'tasks',
    change: {
      action: 'revise_task',
      task_id: taskId,
      changes: [
        { action: 'revise_detail', detail_id: requirementId, text: '核對主要流程（兩次）' },
      ],
    },
  },
  {
    name: 'a knowledge name',
    click: 'HTML 基礎',
    textbox: '知識名稱',
    keys: '與 CSS{Enter}',
    path: 'capabilities',
    change: {
      action: 'revise_capability',
      capability_id: knowledgeId,
      changes: [{ field: 'name', value: 'HTML 基礎與 CSS' }],
    },
  },
  {
    name: 'a knowledge description',
    click: '標記語言概念',
    textbox: '知識說明',
    keys: `與語意${save}`,
    path: 'capabilities',
    change: {
      action: 'revise_capability',
      capability_id: knowledgeId,
      changes: [{ field: 'description', value: '標記語言概念與語意' }],
    },
  },
  {
    name: 'a collaborator name',
    click: '設計部',
    textbox: '協作對象名稱',
    keys: '組{Enter}',
    path: 'collaborators',
    change: {
      action: 'revise_collaborator',
      collaborator_id: collaboratorId,
      changes: [{ field: 'name', value: '設計部組' }],
    },
  },
  {
    name: 'a collaborator scope',
    click: '提供視覺稿',
    textbox: '協作範圍',
    keys: `與規格${save}`,
    path: 'collaborators',
    change: {
      action: 'revise_collaborator',
      collaborator_id: collaboratorId,
      changes: [{ field: 'scope_text', value: '提供視覺稿與規格' }],
    },
  },
  {
    name: 'a condition',
    click: '辦公室工作',
    textbox: '條件內容',
    keys: `，可遠端${save}`,
    path: 'conditions',
    change: {
      action: 'revise_condition',
      condition_id: conditionId,
      changes: [{ field: 'text', value: '辦公室工作，可遠端' }],
    },
  },
];

test.each(otherFields)('edit $name in place with one bounded change', async (field) => {
  const server = stubServer(undefined, fullJd);
  renderEditor();
  await userEvent.click(await screen.findByText(field.click));
  await userEvent.type(await screen.findByRole('textbox', { name: field.textbox }), field.keys);

  await waitFor(() => expect(server.writes()).toHaveLength(1));
  expect(server.paths()[0]).toBe(`/api/job-files/${fileId}/jd/${field.path}`);
  expect(server.writes()[0]).toMatchObject({
    expected_revision_id: revision,
    change: field.change,
  });
});

test('a required text cannot be emptied: the reason shows, the draft stays and nothing is sent', async () => {
  const server = stubServer(undefined, fullJd);
  renderEditor();
  await userEvent.click(await screen.findByText('辦公室工作'));
  const field = await screen.findByRole('textbox', { name: '條件內容' });
  await userEvent.clear(field);
  await userEvent.click(screen.getByRole('button', { name: '儲存' }));

  expect(screen.getByRole('alert')).toHaveTextContent('不能是空白');
  expect(field).toHaveValue('');
  expect(server.writes()).toHaveLength(0);
});
