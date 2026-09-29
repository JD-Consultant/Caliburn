import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { act, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, beforeEach, expect, test, vi } from 'vitest';
import type { JdProfileView } from '../../shared/api/generated/jd-profile-view';
import { isReviseJdProfileRequest } from '../../shared/api/validation';
import { JdProfileEditor } from './JdProfileEditor';
import { jdProfileQuery } from './jd-profile-api';

const fileId = '10000000-0000-4000-8000-000000000001';
const original: JdProfileView = {
  revision_id: '20000000-0000-4000-8000-000000000002',
  profile: {
    job_title: '前端工程師',
    organization_unit: '產品團隊',
    reports_to: null,
    purpose: '原目的',
  },
};
const updated: JdProfileView = {
  revision_id: '30000000-0000-4000-8000-000000000003',
  profile: { ...original.profile, job_title: '維護工程師', purpose: null },
};
const clients: QueryClient[] = [];

function renderEditor() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  clients.push(client);
  return {
    client,
    ...render(
      <QueryClientProvider client={client}>
        <JdProfileEditor key={fileId} jobFileId={fileId} />
      </QueryClientProvider>,
    ),
  };
}

async function editTitle(title: string): Promise<void> {
  await userEvent.click(await screen.findByRole('button', { name: '編輯基本資料' }));
  await userEvent.clear(screen.getByRole('textbox', { name: '職務名稱' }));
  await userEvent.type(screen.getByRole('textbox', { name: '職務名稱' }), title);
}

beforeEach(() => sessionStorage.clear());
afterEach(() => {
  clients.splice(0).forEach((client) => client.clear());
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
});

test('只送有變動欄位與明確清空，回傳原操作後仍 GET 最新正文', async () => {
  let current = original;
  const fetch = vi.fn<(path: string, options?: RequestInit) => Promise<Response>>();
  fetch.mockImplementation((_path, options) => {
    if (options?.method === 'POST') {
      current = updated;
      return Promise.resolve(Response.json(original));
    }
    return Promise.resolve(Response.json(current));
  });
  vi.stubGlobal('fetch', fetch);
  renderEditor();
  await editTitle('維護工程師');
  await userEvent.clear(screen.getByRole('textbox', { name: '職務目的' }));
  await userEvent.click(screen.getByRole('button', { name: '儲存基本資料' }));
  expect(await screen.findByText('維護工程師')).toBeVisible();
  const write = fetch.mock.calls.find(([, options]) => options?.method === 'POST');
  if (typeof write?.[1]?.body !== 'string') throw new Error('Missing command');
  const command: unknown = JSON.parse(write[1].body);
  if (!isReviseJdProfileRequest(command)) throw new Error('Invalid command');
  expect(command.expected_revision_id).toBe(original.revision_id);
  expect(command.changes).toEqual([
    { action: 'set_field', field: 'job_title', value: '維護工程師' },
    { action: 'clear_field', field: 'purpose' },
  ]);
  expect(screen.getByText('產品團隊')).toBeVisible();
});

test('結果不明後 remount 沿用原命令與基底，不覆蓋後來稿', async () => {
  let current = original;
  let attempt = 0;
  const fetch = vi.fn<(path: string, options?: RequestInit) => Promise<Response>>();
  fetch.mockImplementation((_path, options) => {
    if (options?.method === 'POST') {
      attempt += 1;
      current = { ...updated, profile: { ...updated.profile, job_title: '後來的職務名稱' } };
      return attempt === 1
        ? Promise.reject(new TypeError('lost response'))
        : Promise.resolve(Response.json(updated));
    }
    return Promise.resolve(Response.json(current));
  });
  vi.stubGlobal('fetch', fetch);
  const first = renderEditor();
  await editTitle('維護工程師');
  await userEvent.click(screen.getByRole('button', { name: '儲存基本資料' }));
  expect(await screen.findByRole('alert')).toHaveTextContent('JD 修改結果尚未確認');
  first.unmount();
  renderEditor();
  await userEvent.click(await screen.findByRole('button', { name: '編輯基本資料' }));
  expect(screen.getByRole('textbox', { name: '職務名稱' })).toHaveValue('維護工程師');
  expect(screen.getByRole('textbox', { name: '職務名稱' })).toBeDisabled();
  await userEvent.click(screen.getByRole('button', { name: '重新確認修改結果' }));
  await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument());
  expect(screen.getByText('後來的職務名稱')).toBeVisible();
  const writes = fetch.mock.calls.filter(([, options]) => options?.method === 'POST');
  expect(writes).toHaveLength(2);
  expect(writes[1]?.[1]?.body).toBe(writes[0]?.[1]?.body);
  expect(sessionStorage.length).toBe(0);
});

test('明確拒絕不自動重試或改基底，使用者先重讀', async () => {
  let current = original;
  const fetch = vi.fn<(path: string, options?: RequestInit) => Promise<Response>>();
  fetch.mockImplementation((_path, options) => {
    if (options?.method === 'POST') {
      current = updated;
      return Promise.resolve(
        Response.json({ detail: { code: 'jd_revision_stale' } }, { status: 409 }),
      );
    }
    return Promise.resolve(Response.json(current));
  });
  vi.stubGlobal('fetch', fetch);
  renderEditor();
  await editTitle('不能覆蓋');
  await userEvent.click(screen.getByRole('button', { name: '儲存基本資料' }));
  expect(await screen.findByRole('alert')).toHaveTextContent('修改未被接受');
  expect(screen.getByRole('textbox', { name: '職務名稱' })).toHaveValue('不能覆蓋');
  expect(screen.getByRole('textbox', { name: '職務名稱' })).toBeDisabled();
  expect(fetch.mock.calls.filter(([, options]) => options?.method === 'POST')).toHaveLength(1);
  await userEvent.click(screen.getByRole('button', { name: '讀取目前 JD' }));
  expect(await screen.findByText('維護工程師')).toBeVisible();
});

test('背景 GET 更新不得替換已開啟表單的基底或草稿', async () => {
  let current = original;
  const fetch = vi.fn<(path: string, options?: RequestInit) => Promise<Response>>();
  fetch.mockImplementation((_path, options) =>
    Promise.resolve(
      options?.method === 'POST' ? Response.json({}, { status: 409 }) : Response.json(current),
    ),
  );
  vi.stubGlobal('fetch', fetch);
  const view = renderEditor();
  await editTitle('本次草稿');
  current = updated;
  await act(async () => {
    await view.client.invalidateQueries({ queryKey: jdProfileQuery(fileId).queryKey });
  });
  expect(screen.getByRole('textbox', { name: '職務名稱' })).toHaveValue('本次草稿');
  await userEvent.click(screen.getByRole('button', { name: '儲存基本資料' }));
  expect(await screen.findByRole('alert')).toHaveTextContent('修改未被接受');
  const write = fetch.mock.calls.find(([, options]) => options?.method === 'POST');
  if (typeof write?.[1]?.body !== 'string') throw new Error('Missing command');
  const sent: unknown = JSON.parse(write[1].body);
  expect(sent).toMatchObject({ expected_revision_id: original.revision_id });
});

test.each(['invalid', 'offline'])('讀取 %s 不當成空白 JD，也不能編輯', async (failure) => {
  vi.stubGlobal(
    'fetch',
    failure === 'invalid'
      ? vi.fn().mockResolvedValue(Response.json({ profile: {} }))
      : vi.fn().mockRejectedValue(new TypeError('offline')),
  );
  renderEditor();
  expect(await screen.findByRole('alert')).toBeVisible();
  expect(screen.queryByRole('button', { name: '編輯基本資料' })).not.toBeInTheDocument();
  expect(screen.queryByText('尚未提供')).not.toBeInTheDocument();
  expect(screen.getByRole('button', { name: '重新讀取 JD' })).toBeEnabled();
});

test('空白或未修改不發命令；儲存原識別失敗也不送出', async () => {
  const fetch = vi.fn().mockImplementation(() => Promise.resolve(Response.json(original)));
  vi.stubGlobal('fetch', fetch);
  renderEditor();
  await userEvent.click(await screen.findByRole('button', { name: '編輯基本資料' }));
  await userEvent.click(screen.getByRole('button', { name: '儲存基本資料' }));
  expect(await screen.findByRole('alert')).toHaveTextContent('沒有修改');
  await userEvent.clear(screen.getByRole('textbox', { name: '職務名稱' }));
  await userEvent.type(screen.getByRole('textbox', { name: '職務名稱' }), '   ');
  await userEvent.click(screen.getByRole('button', { name: '儲存基本資料' }));
  expect(await screen.findByRole('alert')).toHaveTextContent('不能只有空白');
  await userEvent.clear(screen.getByRole('textbox', { name: '職務名稱' }));
  await userEvent.type(screen.getByRole('textbox', { name: '職務名稱' }), '新內容');
  vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => {
    throw new Error('storage unavailable');
  });
  await userEvent.click(screen.getByRole('button', { name: '儲存基本資料' }));
  expect(await screen.findByRole('alert')).toHaveTextContent('尚未送出');
  expect(fetch).toHaveBeenCalledTimes(1);
});

test('命令在途禁用重送與 Escape 關閉，不將局部草稿當成正式資料', async () => {
  let finish: (value: Response) => void = () => {
    throw new Error('Uninitialized');
  };
  const response = new Promise<Response>((resolve) => {
    finish = resolve;
  });
  const fetch = vi.fn<(path: string, options?: RequestInit) => Promise<Response>>();
  fetch.mockImplementation((_path, options) =>
    options?.method === 'POST' ? response : Promise.resolve(Response.json(original)),
  );
  vi.stubGlobal('fetch', fetch);
  renderEditor();
  await editTitle('尚未確認');
  await userEvent.dblClick(screen.getByRole('button', { name: '儲存基本資料' }));
  expect(screen.getByRole('button', { name: '確認中…' })).toBeDisabled();
  await userEvent.keyboard('{Escape}');
  expect(screen.getByRole('dialog')).toBeVisible();
  expect(fetch.mock.calls.filter(([, options]) => options?.method === 'POST')).toHaveLength(1);
  await act(async () => {
    finish(Response.json(updated));
    await response;
  });
  await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument());
});
