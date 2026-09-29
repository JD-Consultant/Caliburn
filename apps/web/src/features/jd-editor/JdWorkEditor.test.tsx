import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { act, render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, beforeEach, expect, test, vi } from 'vitest';
import { JdWorkEditor } from './JdWorkEditor';
import { jdWorkQuery } from './jd-work-api';
import type { JdWorkView } from '../../shared/api/generated/jd-work-view';
import { isEditJdTasksRequest } from '../../shared/api/validation';

const fileId = '10000000-0000-4000-8000-000000000001';
const revision = '20000000-0000-4000-8000-000000000002';
const areaId = '30000000-0000-4000-8000-000000000003';
const clients: QueryClient[] = [];
function renderEditor() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  clients.push(client);
  return {
    client,
    ...render(
      <QueryClientProvider client={client}>
        <JdWorkEditor key={fileId} jobFileId={fileId} />
      </QueryClientProvider>,
    ),
  };
}
beforeEach(() => sessionStorage.clear());
afterEach(() => {
  clients.splice(0).forEach((client) => client.clear());
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
});

test('建立職責只送表單內容與捕捉基底，成功後讀取同版職責任務', async () => {
  const current = { revision_id: revision, areas: [], tasks: [] };
  const updated = {
    ...current,
    areas: [{ area_id: areaId, title: '網站交付', scope_text: '約定前端範圍' }],
  };
  let saved = false;
  const fetch = vi.fn<(path: string, options?: RequestInit) => Promise<Response>>();
  fetch.mockImplementation((_path, options) => {
    if (options?.method === 'POST') {
      saved = true;
      return Promise.resolve(Response.json({ revision_id: revision, areas: updated.areas }));
    }
    return Promise.resolve(Response.json(saved ? updated : current));
  });
  vi.stubGlobal('fetch', fetch);
  renderEditor();
  await userEvent.click(await screen.findByRole('button', { name: '新增職責' }));
  await userEvent.type(screen.getByRole('textbox', { name: '職責名稱' }), '網站交付');
  await userEvent.type(screen.getByRole('textbox', { name: '職責範圍' }), '約定前端範圍');
  await userEvent.click(screen.getByRole('button', { name: '儲存職責' }));
  await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument());
  expect(screen.getByRole('heading', { name: '網站交付' })).toBeVisible();
  const write = fetch.mock.calls.find(([, options]) => options?.method === 'POST');
  expect(write?.[0]).toBe(`/api/job-files/${fileId}/jd/areas`);
  const payload: unknown = typeof write?.[1]?.body === 'string' ? JSON.parse(write[1].body) : null;
  expect(payload).toMatchObject({
    expected_revision_id: revision,
    change: { action: 'create_area', title: '網站交付', scope_text: '約定前端範圍' },
  });
});

const original: JdWorkView = {
  revision_id: revision,
  areas: [{ area_id: areaId, title: '網站交付', scope_text: '原範圍' }],
  tasks: [
    {
      task_id: '40000000-0000-4000-8000-000000000004',
      area_id: areaId,
      title: '實作網頁',
      description: '原工作內容',
      outcomes: [{ detail_id: '50000000-0000-4000-8000-000000000005', text: '可操作頁面' }],
      requirements: [{ detail_id: '60000000-0000-4000-8000-000000000006', text: '核對主要流程' }],
    },
  ],
};

test('移動任務並改內容用同一命令，未改明細保留身分不重送', async () => {
  const fetch = vi.fn<(path: string, options?: RequestInit) => Promise<Response>>();
  fetch.mockImplementation((_path, options) =>
    Promise.resolve(
      Response.json(
        options?.method === 'POST' ? { revision_id: revision, tasks: original.tasks } : original,
      ),
    ),
  );
  vi.stubGlobal('fetch', fetch);
  renderEditor();
  await userEvent.click(await screen.findByRole('button', { name: '編輯任務' }));
  await userEvent.clear(screen.getByRole('textbox', { name: '工作內容' }));
  await userEvent.type(screen.getByRole('textbox', { name: '工作內容' }), '已調整範圍');
  await userEvent.click(screen.getByRole('combobox', { name: '所屬職責' }));
  await userEvent.click(screen.getByRole('option', { name: '未歸屬任務' }));
  await userEvent.click(screen.getByRole('button', { name: '新增工作要求' }));
  await userEvent.type(screen.getByRole('textbox', { name: '工作要求 2' }), '說明限制');
  await userEvent.click(screen.getByRole('button', { name: '儲存任務' }));
  await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument());
  const body = fetch.mock.calls.find(([, options]) => options?.method === 'POST')?.[1]?.body;
  const value: unknown = typeof body === 'string' ? JSON.parse(body) : null;
  if (!isEditJdTasksRequest(value)) throw new Error('Invalid task command');
  expect(value.change).toEqual({
    action: 'move_task',
    task_id: original.tasks[0]?.task_id,
    area_id: null,
    before_task_id: null,
    changes: [
      { action: 'set_field', field: 'description', value: '已調整範圍' },
      { action: 'add_detail', kind: 'requirement', text: '說明限制' },
    ],
  });
});

test('原目標後來已刪除仍能 remount 重新確認同命令，不復活舊結果', async () => {
  let current = original;
  let attempt = 0;
  const fetch = vi.fn<(path: string, options?: RequestInit) => Promise<Response>>();
  fetch.mockImplementation((_path, options) => {
    if (options?.method === 'POST') {
      attempt += 1;
      current = { revision_id: '70000000-0000-4000-8000-000000000007', areas: [], tasks: [] };
      return attempt === 1
        ? Promise.reject(new TypeError('lost response'))
        : Promise.resolve(Response.json({ revision_id: revision, areas: original.areas }));
    }
    return Promise.resolve(Response.json(current));
  });
  vi.stubGlobal('fetch', fetch);
  const first = renderEditor();
  await userEvent.click(await screen.findByRole('button', { name: '編輯職責' }));
  await userEvent.type(screen.getByRole('textbox', { name: '職責名稱' }), '新名稱');
  await userEvent.click(screen.getByRole('button', { name: '儲存職責' }));
  expect(await screen.findByRole('alert')).toHaveTextContent('JD 修改結果尚未確認');
  first.unmount();
  renderEditor();
  await userEvent.click(await screen.findByRole('button', { name: '重新確認修改結果' }));
  await waitFor(() =>
    expect(screen.queryByRole('button', { name: '重新確認修改結果' })).not.toBeInTheDocument(),
  );
  expect(screen.queryByRole('heading', { name: '網站交付' })).not.toBeInTheDocument();
  const writes = fetch.mock.calls.filter(([, options]) => options?.method === 'POST');
  expect(writes).toHaveLength(2);
  expect(writes[1]?.[1]?.body).toBe(writes[0]?.[1]?.body);
  expect(sessionStorage.length).toBe(0);
});

test('背景讀取不能替換草稿基底；409 後須明確讀目前稿', async () => {
  const fetch = vi.fn<(path: string, options?: RequestInit) => Promise<Response>>();
  fetch.mockImplementation((_path, options) =>
    Promise.resolve(
      options?.method === 'POST' ? Response.json({}, { status: 409 }) : Response.json(original),
    ),
  );
  vi.stubGlobal('fetch', fetch);
  const { client } = renderEditor();
  await userEvent.click(await screen.findByRole('button', { name: '編輯職責' }));
  await userEvent.clear(screen.getByRole('textbox', { name: '職責範圍' }));
  await userEvent.type(screen.getByRole('textbox', { name: '職責範圍' }), '本機草稿');
  act(() => {
    client.setQueryData(jdWorkQuery(fileId).queryKey, {
      ...original,
      revision_id: '70000000-0000-4000-8000-000000000007',
    });
  });
  await userEvent.click(screen.getByRole('button', { name: '儲存職責' }));
  expect(await screen.findByRole('alert')).toHaveTextContent('修改未被接受');
  expect(screen.getByRole('textbox', { name: '職責範圍' })).toHaveValue('本機草稿');
  expect(screen.getByRole('button', { name: '儲存職責' })).toBeDisabled();
  const writes = fetch.mock.calls.filter(([, options]) => options?.method === 'POST');
  expect(writes).toHaveLength(1);
  expect(writes[0]?.[1]?.body).toContain(revision);
  await userEvent.click(screen.getByRole('button', { name: '讀取目前 JD' }));
  await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument());
});

test.each([{}, { revision_id: revision, areas: [], tasks: [{ title: '不完整資料' }] }])(
  '非法讀取結果不是空稿，也不可編輯',
  async (value) => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(Response.json(value)));
    renderEditor();
    expect(await screen.findByRole('alert')).toHaveTextContent('資料格式不符');
    expect(screen.queryByRole('button', { name: '新增職責' })).not.toBeInTheDocument();
  },
);

test('空白與暫存失敗均不發寫入；尚未送出的表單可以離開', async () => {
  const fetch = vi.fn().mockResolvedValue(Response.json(original));
  vi.stubGlobal('fetch', fetch);
  renderEditor();
  await userEvent.click(await screen.findByRole('button', { name: '新增職責' }));
  await userEvent.type(screen.getByRole('textbox', { name: '職責名稱' }), '   ');
  await userEvent.click(screen.getByRole('button', { name: '儲存職責' }));
  expect(screen.getByRole('alert')).toHaveTextContent('不能只填空白');
  await userEvent.clear(screen.getByRole('textbox', { name: '職責名稱' }));
  await userEvent.type(screen.getByRole('textbox', { name: '職責名稱' }), '有效職責');
  vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => {
    throw new Error('denied');
  });
  await userEvent.click(screen.getByRole('button', { name: '儲存職責' }));
  expect(screen.getByRole('alert')).toHaveTextContent('尚未送出');
  expect(fetch).toHaveBeenCalledTimes(1);
  await userEvent.click(screen.getByRole('button', { name: '返回 JD' }));
  expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
});

test('刪職責需明確確認，提示任務保留而非一起刪除', async () => {
  const fetch = vi.fn().mockResolvedValue(Response.json(original));
  vi.stubGlobal('fetch', fetch);
  renderEditor();
  await userEvent.click(await screen.findByRole('button', { name: '刪除職責' }));
  const dialog = screen.getByRole('dialog');
  expect(within(dialog).getByText(/任務會保留/)).toBeVisible();
  expect(within(dialog).getByRole('button', { name: '確認刪除職責' })).toBeEnabled();
  expect(fetch).toHaveBeenCalledTimes(1);
});

test('請求在途阻止再次提交與關閉；保存已知但本機清理失敗不說成未知', async () => {
  let finish: (response: Response) => void = () => {
    throw new Error('Request not started');
  };
  const response = new Promise<Response>((resolve) => {
    finish = resolve;
  });
  const fetch = vi.fn<(path: string, options?: RequestInit) => Promise<Response>>();
  fetch.mockImplementation((_path, options) =>
    options?.method === 'POST'
      ? response.then((value) => value.clone())
      : Promise.resolve(Response.json(original)),
  );
  vi.stubGlobal('fetch', fetch);
  renderEditor();
  await userEvent.click(await screen.findByRole('button', { name: '新增職責' }));
  await userEvent.type(screen.getByRole('textbox', { name: '職責名稱' }), '新職責');
  await userEvent.click(screen.getByRole('button', { name: '儲存職責' }));
  expect(screen.getByRole('button', { name: '重新確認修改結果' })).toBeDisabled();
  expect(screen.getByRole('button', { name: '返回 JD' })).toBeDisabled();
  await userEvent.keyboard('{Escape}');
  expect(screen.getByRole('dialog')).toBeVisible();
  vi.spyOn(Storage.prototype, 'removeItem').mockImplementationOnce(() => {
    throw new Error('denied');
  });
  await act(async () => {
    finish(Response.json({ revision_id: revision, areas: original.areas }));
    await response;
  });
  await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument());
  expect(screen.getByRole('alert')).toHaveTextContent('修改已保存，但本分頁暫存未能清除');
  expect(screen.queryByText(/JD 修改結果尚未確認/)).not.toBeInTheDocument();
  await userEvent.click(screen.getByRole('button', { name: '重新確認修改結果' }));
  await waitFor(() => expect(screen.queryByRole('alert')).not.toBeInTheDocument());
  const writes = fetch.mock.calls.filter(([, options]) => options?.method === 'POST');
  expect(writes).toHaveLength(2);
  expect(writes[1]?.[1]?.body).toBe(writes[0]?.[1]?.body);
});

test('損壞的待確認命令阻止新寫入，不默默丟棄', async () => {
  sessionStorage.setItem(`caliburn.pending-jd-work.${fileId}`, '{broken');
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue(Response.json(original)));
  renderEditor();
  expect(await screen.findByRole('alert')).toHaveTextContent('無法讀取待確認修改');
  expect(await screen.findByRole('button', { name: '新增職責' })).toBeDisabled();
  expect(sessionStorage.getItem(`caliburn.pending-jd-work.${fileId}`)).toBe('{broken');
});
