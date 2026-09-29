import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, beforeEach, expect, test, vi } from 'vitest';
import { JdWorkEditor } from './JdWorkEditor';
import type { JdWorkView } from '../../shared/api/generated/jd-work-view';
import { isEditJdCapabilitiesRequest } from '../../shared/api/validation';

const fileId = '10000000-0000-4000-8000-000000000001';
const revision = '20000000-0000-4000-8000-000000000002';
const knowledgeId = '30000000-0000-4000-8000-000000000003';
const taskId = '40000000-0000-4000-8000-000000000004';
const skillId = '50000000-0000-4000-8000-000000000005';
const original: JdWorkView = {
  revision_id: revision,
  areas: [],
  tasks: [
    {
      task_id: taskId,
      area_id: null,
      title: '實作網頁',
      description: null,
      outcomes: [],
      requirements: [],
    },
  ],
  capabilities: [
    {
      capability_id: knowledgeId,
      kind: 'knowledge',
      name: '資料介面',
      description: '理解狀態與錯誤訊號',
    },
    { capability_id: skillId, kind: 'skill', name: '診斷問題', description: '定位前端故障' },
  ],
  task_links: [{ task_id: taskId, capability_id: knowledgeId }],
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
function capabilitiesResult() {
  return {
    revision_id: revision,
    capabilities: original.capabilities,
    task_links: original.task_links,
  };
}
function mockServer() {
  const fetch = vi.fn<(path: string, options?: RequestInit) => Promise<Response>>();
  fetch.mockImplementation((_path, options) =>
    Promise.resolve(Response.json(options?.method === 'POST' ? capabilitiesResult() : original)),
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

test('共用知識可只填描述；名稱不是身分，送出目前同版基底', async () => {
  const fetch = mockServer();
  renderEditor();
  await userEvent.click(await screen.findByRole('button', { name: '新增知識' }));
  await userEvent.type(screen.getByRole('textbox', { name: '知識說明' }), '理解瀏覽器事件傳遞');
  await userEvent.click(screen.getByRole('button', { name: '儲存知識' }));
  await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument());
  const call = fetch.mock.calls.find(([, options]) => options?.method === 'POST');
  expect(call?.[0]).toBe(`/api/job-files/${fileId}/jd/capabilities`);
  const payload: unknown = typeof call?.[1]?.body === 'string' ? JSON.parse(call[1].body) : null;
  expect(payload).toMatchObject({
    expected_revision_id: revision,
    change: {
      action: 'create_capability',
      kind: 'knowledge',
      name: null,
      description: '理解瀏覽器事件傳遞',
    },
  });
});

test('使用中的定義列反向用途、禁止直接刪；任務解除只刪關係', async () => {
  const fetch = mockServer();
  renderEditor();
  const definition = await screen.findByRole('article', { name: '知識：資料介面' });
  expect(within(definition).getByRole('link', { name: /實作網頁/ })).toHaveAttribute(
    'href',
    `#jd-task-${taskId}`,
  );
  expect(within(definition).getByRole('button', { name: '刪除知識' })).toBeDisabled();
  const task = screen.getByRole('article', { name: '實作網頁' });
  await userEvent.click(within(task).getByRole('button', { name: '解除知識 資料介面' }));
  await waitFor(() =>
    expect(fetch.mock.calls.filter(([, o]) => o?.method === 'POST')).toHaveLength(1),
  );
  const body = fetch.mock.calls.find(([, o]) => o?.method === 'POST')?.[1]?.body;
  expect(typeof body === 'string' ? JSON.parse(body) : null).toMatchObject({
    change: {
      action: 'set_task_capability',
      task_id: taskId,
      capability_id: knowledgeId,
      linked: false,
    },
  });
});

test('任務選用既有技能，不複製定義；修定義只送變動欄', async () => {
  const fetch = mockServer();
  renderEditor();
  const task = await screen.findByRole('article', { name: '實作網頁' });
  await userEvent.click(within(task).getByRole('combobox', { name: '新增技能關聯' }));
  await userEvent.click(screen.getByRole('option', { name: /診斷問題/ }));
  await waitFor(() =>
    expect(within(task).getByRole('combobox', { name: '新增技能關聯' })).toBeEnabled(),
  );
  const definition = screen.getByRole('article', { name: '技能：診斷問題' });
  await userEvent.click(within(definition).getByRole('button', { name: '編輯技能' }));
  await userEvent.clear(screen.getByRole('textbox', { name: '技能名稱' }));
  await userEvent.type(screen.getByRole('textbox', { name: '技能名稱' }), '定位前端問題');
  await userEvent.click(screen.getByRole('button', { name: '儲存技能' }));
  await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument());
  const writes = fetch.mock.calls
    .filter(([, o]) => o?.method === 'POST')
    .map(([, o]) => {
      const value: unknown = typeof o?.body === 'string' ? JSON.parse(o.body) : null;
      if (!isEditJdCapabilitiesRequest(value)) throw new Error('Invalid capability command');
      return value.change;
    });
  expect(writes).toEqual([
    { action: 'set_task_capability', task_id: taskId, capability_id: skillId, linked: true },
    {
      action: 'revise_capability',
      capability_id: skillId,
      changes: [{ field: 'name', value: '定位前端問題' }],
    },
  ]);
});

test.each(['definition', 'relation'] as const)(
  '未確認的 %s 命令在重開後原樣確認，不以舊結果覆寫新稿',
  async (operation) => {
    let current = original;
    let writes = 0;
    const fetch = vi.fn<(path: string, options?: RequestInit) => Promise<Response>>();
    fetch.mockImplementation((_path, options) => {
      if (options?.method === 'POST') {
        writes += 1;
        current = { ...original, capabilities: [], task_links: [] };
        return writes === 1
          ? Promise.reject(new TypeError('lost response'))
          : Promise.resolve(Response.json(capabilitiesResult()));
      }
      return Promise.resolve(Response.json(current));
    });
    vi.stubGlobal('fetch', fetch);
    const first = renderEditor();
    if (operation === 'definition') {
      const definition = await screen.findByRole('article', { name: '技能：診斷問題' });
      await userEvent.click(within(definition).getByRole('button', { name: '編輯技能' }));
      await userEvent.type(screen.getByRole('textbox', { name: '技能名稱' }), '新版');
      await userEvent.click(screen.getByRole('button', { name: '儲存技能' }));
    } else {
      const task = await screen.findByRole('article', { name: '實作網頁' });
      await userEvent.click(within(task).getByRole('button', { name: '解除知識 資料介面' }));
    }
    expect(await screen.findByRole('alert')).toHaveTextContent('結果尚未確認');
    first.unmount();
    renderEditor();
    expect(await screen.findByRole('button', { name: '新增知識' })).toBeDisabled();
    await userEvent.click(screen.getByRole('button', { name: '重新確認修改結果' }));
    await waitFor(() =>
      expect(screen.queryByRole('button', { name: '重新確認修改結果' })).not.toBeInTheDocument(),
    );
    expect(screen.queryByRole('article', { name: '技能：診斷問題' })).not.toBeInTheDocument();
    expect(sessionStorage.length).toBe(0);
    const commands = fetch.mock.calls.filter(([, options]) => options?.method === 'POST');
    expect(commands).toHaveLength(2);
    expect(commands[0]?.[1]?.body).toBe(commands[1]?.[1]?.body);
  },
);

test('概覽與任務關聯使用不同順序；同名仍操作選定身分', async () => {
  const otherId = '60000000-0000-4000-8000-000000000006';
  const current: JdWorkView = {
    ...original,
    capabilities: [
      ...original.capabilities,
      { capability_id: otherId, kind: 'knowledge', name: '資料介面', description: '另一適用範圍' },
    ],
    task_links: [
      { task_id: taskId, capability_id: otherId },
      { task_id: taskId, capability_id: knowledgeId },
    ],
  };
  const fetch = vi.fn<(path: string, options?: RequestInit) => Promise<Response>>();
  fetch.mockImplementation((_path, options) =>
    Promise.resolve(Response.json(options?.method === 'POST' ? capabilitiesResult() : current)),
  );
  vi.stubGlobal('fetch', fetch);
  renderEditor();
  const definitions = await screen.findAllByRole('article', { name: '知識：資料介面' });
  const firstDefinition = definitions[0];
  if (!firstDefinition) throw new Error('Missing first definition');
  await userEvent.click(within(firstDefinition).getByRole('button', { name: '下移知識' }));
  const task = screen.getByRole('article', { name: '實作網頁' });
  const first = within(task).getAllByRole('button', { name: '下移知識關聯 資料介面' })[0];
  if (!first) throw new Error('Missing first link');
  await waitFor(() => expect(first).toBeEnabled());
  await userEvent.click(first);
  await waitFor(() =>
    expect(fetch.mock.calls.filter(([, options]) => options?.method === 'POST')).toHaveLength(2),
  );
  const changes = fetch.mock.calls
    .filter(([, options]) => options?.method === 'POST')
    .map(([, options]) => {
      const value: unknown = typeof options?.body === 'string' ? JSON.parse(options.body) : null;
      if (!isEditJdCapabilitiesRequest(value)) throw new Error('Invalid command');
      return value.change;
    });
  expect(changes).toEqual([
    { action: 'reorder_capability', capability_id: knowledgeId, before_capability_id: null },
    {
      action: 'reorder_task_capability',
      task_id: taskId,
      capability_id: otherId,
      before_capability_id: null,
    },
  ]);
});

test('未使用技能刪除需確認，空白定義與無修改不發送', async () => {
  const fetch = mockServer();
  renderEditor();
  const definition = await screen.findByRole('article', { name: '技能：診斷問題' });
  await userEvent.click(within(definition).getByRole('button', { name: '編輯技能' }));
  await userEvent.click(screen.getByRole('button', { name: '儲存技能' }));
  expect(screen.getByRole('alert')).toHaveTextContent('沒有修改');
  await userEvent.clear(screen.getByRole('textbox', { name: '技能名稱' }));
  await userEvent.clear(screen.getByRole('textbox', { name: '技能說明' }));
  await userEvent.type(screen.getByRole('textbox', { name: '技能名稱' }), '   ');
  await userEvent.click(screen.getByRole('button', { name: '儲存技能' }));
  expect(screen.getByRole('alert')).toHaveTextContent('不能只填空白');
  expect(fetch).toHaveBeenCalledTimes(1);
  await userEvent.click(screen.getByRole('button', { name: '返回 JD' }));
  await userEvent.click(within(definition).getByRole('button', { name: '刪除技能' }));
  expect(screen.getByRole('dialog')).toHaveTextContent('已保存的歷史不改寫');
  expect(fetch).toHaveBeenCalledTimes(1);
  await userEvent.click(screen.getByRole('button', { name: '確認刪除技能' }));
  await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument());
  const body = fetch.mock.calls.find(([, options]) => options?.method === 'POST')?.[1]?.body;
  expect(typeof body === 'string' ? JSON.parse(body) : null).toMatchObject({
    change: { action: 'delete_capability', capability_id: skillId },
  });
});
