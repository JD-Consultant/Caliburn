/** 以 HTTP 替身驗證刪除確認、正式成功、拒絕與同目標重試；不接真實資料。 */
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { act, render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, Route, Routes } from 'react-router';
import { afterEach, expect, test, vi } from 'vitest';
import { JobFilesPage } from './JobFilesPage';

const target = {
  job_file_id: '10000000-0000-4000-8000-000000000001',
  display_name: '庫存管理',
  employee_name: '合成員工甲',
  created_at: '2026-09-29T10:00:00Z',
  name_revision: 1,
};
const other = {
  ...target,
  job_file_id: '20000000-0000-4000-8000-000000000002',
  employee_name: '合成員工乙',
};
const clients: QueryClient[] = [];

afterEach(() => {
  clients.splice(0).forEach((client) => client.clear());
  sessionStorage.clear();
  vi.unstubAllGlobals();
});

function renderList() {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  clients.push(client);
  render(
    <QueryClientProvider client={client}>
      <MemoryRouter>
        <Routes>
          <Route path="/" element={<JobFilesPage />} />
          <Route path="/job-files/:jobFileId" element={<p>已進入職務檔案</p>} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
  return client;
}

async function openDelete() {
  await userEvent.click(await screen.findByRole('button', { name: /刪除 庫存管理（合成員工甲/ }));
  return screen.getByRole('dialog', { name: /刪除職務檔案/ });
}

test('取消預設聚焦，確認清楚指出檔名與不可復原範圍；取消不刪除或導航', async () => {
  const transport = vi.fn(() => Promise.resolve(Response.json({ job_files: [target, other] })));
  vi.stubGlobal('fetch', transport);
  renderList();
  const dialog = await openDelete();
  expect(within(dialog).getByText(/庫存管理/)).toBeVisible();
  expect(within(dialog).getByText(/訪談.*JD.*Memory.*執行紀錄/)).toBeVisible();
  expect(within(dialog).getByText(/不可復原/)).toBeVisible();
  const cancel = within(dialog).getByRole('button', { name: '取消' });
  await waitFor(() => expect(cancel).toHaveFocus());
  await userEvent.click(cancel);
  await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument());
  expect(screen.getAllByRole('link', { name: /開啟 庫存管理/ })).toHaveLength(2);
  expect(screen.queryByText('已進入職務檔案')).not.toBeInTheDocument();
  expect(transport).toHaveBeenCalledTimes(1);
});

test('收到204前保留列，成功重讀清單並只移除該檔快取及改名暫存', async () => {
  let deleted = false;
  let finishDelete: (response: Response) => void = () => {
    throw new Error('刪除尚未送出');
  };
  const deletionResponse = new Promise<Response>((resolve) => {
    finishDelete = resolve;
  });
  const transport = vi.fn((url: string, options?: RequestInit) => {
    if (options?.method === 'DELETE') {
      expect(url).toBe(`/api/job-files/${target.job_file_id}`);
      expect(options.credentials).toBe('same-origin');
      return deletionResponse;
    }
    return Promise.resolve(Response.json({ job_files: deleted ? [other] : [target, other] }));
  });
  vi.stubGlobal('fetch', transport);
  const client = renderList();
  const scopes = [
    'job-file',
    'jd-profile',
    'jd-work',
    'jd-source-content',
    'jd-source-changes',
    'consultant-turn',
    'consultant-turn-by-command',
    'current-consultant-turn',
    'reasoning-summaries',
    'turn-jd-changes',
  ];
  scopes.forEach((scope) => {
    client.setQueryData([scope, target.job_file_id, 'detail'], 'target data');
    client.setQueryData([scope, other.job_file_id, 'detail'], 'other data');
  });
  sessionStorage.setItem(
    `caliburn.pending-job-file-rename.${target.job_file_id}`,
    'target command',
  );
  sessionStorage.setItem(`caliburn.pending-job-file-rename.${other.job_file_id}`, 'other command');
  const dialog = await openDelete();
  await userEvent.click(within(dialog).getByRole('button', { name: '永久刪除' }));
  expect(within(dialog).getByRole('button', { name: '取消' })).toBeDisabled();
  expect(
    screen.getByRole('link', { name: /開啟 庫存管理（合成員工甲/, hidden: true }),
  ).toBeInTheDocument();
  expect(client.getQueryData(['jd-work', target.job_file_id, 'detail'])).toBe('target data');
  deleted = true;
  await act(async () => {
    finishDelete(new Response(null, { status: 204 }));
    await deletionResponse;
  });
  await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument());
  await waitFor(() =>
    expect(screen.queryByRole('link', { name: /合成員工甲/ })).not.toBeInTheDocument(),
  );
  expect(screen.getByRole('link', { name: /合成員工乙/ })).toBeVisible();
  scopes.forEach((scope) => {
    expect(client.getQueryData([scope, target.job_file_id, 'detail'])).toBeUndefined();
    expect(client.getQueryData([scope, other.job_file_id, 'detail'])).toBe('other data');
  });
  expect(
    sessionStorage.getItem(`caliburn.pending-job-file-rename.${target.job_file_id}`),
  ).toBeNull();
  expect(sessionStorage.getItem(`caliburn.pending-job-file-rename.${other.job_file_id}`)).toBe(
    'other command',
  );
  expect(transport.mock.calls.filter(([, options]) => options?.method === 'DELETE')).toHaveLength(
    1,
  );
});

test('409 job_file_busy 說明先完成或取消工作，保留檔案與快取', async () => {
  vi.stubGlobal(
    'fetch',
    vi.fn((_url: string, options?: RequestInit) =>
      Promise.resolve(
        options?.method === 'DELETE'
          ? Response.json({ detail: { code: 'job_file_busy' } }, { status: 409 })
          : Response.json({ job_files: [target] }),
      ),
    ),
  );
  const client = renderList();
  client.setQueryData(['jd-work', target.job_file_id], 'saved JD');
  const dialog = await openDelete();
  await userEvent.click(within(dialog).getByRole('button', { name: '永久刪除' }));
  expect(await within(dialog).findByRole('alert')).toHaveTextContent(
    /請先完成或取消顧問工作，或等候 Memory 整理結束，再刪除檔案。/,
  );
  expect(within(dialog).getByRole('alert')).toHaveTextContent(/顧問.*Memory/);
  expect(client.getQueryData(['jd-work', target.job_file_id])).toBe('saved JD');
  await userEvent.click(within(dialog).getByRole('button', { name: '取消' }));
  expect(await screen.findByRole('link', { name: /合成員工甲/ })).toBeVisible();
});

test('網路結果不明不移除列，同一目標手動重試可接受不存在的204', async () => {
  let attempts = 0;
  const transport = vi.fn((_url: string, options?: RequestInit) => {
    if (options?.method === 'DELETE') {
      attempts++;
      return attempts === 1
        ? Promise.reject(new TypeError('response lost'))
        : Promise.resolve(new Response(null, { status: 204 }));
    }
    return Promise.resolve(Response.json({ job_files: attempts === 2 ? [] : [target] }));
  });
  vi.stubGlobal('fetch', transport);
  renderList();
  const dialog = await openDelete();
  await userEvent.click(within(dialog).getByRole('button', { name: '永久刪除' }));
  expect(await within(dialog).findByRole('alert')).toHaveTextContent(/刪除結果尚未確認/);
  expect(attempts).toBe(1);
  expect(screen.getByRole('link', { name: /合成員工甲/, hidden: true })).toBeInTheDocument();
  await userEvent.click(within(dialog).getByRole('button', { name: /重試刪除/ }));
  expect(await screen.findByRole('heading', { name: '尚無職務檔案' })).toBeVisible();
  const deletes = transport.mock.calls.filter(([, options]) => options?.method === 'DELETE');
  expect(deletes.map(([url]) => url)).toEqual([
    `/api/job-files/${target.job_file_id}`,
    `/api/job-files/${target.job_file_id}`,
  ]);
});

test('503保留列，不顯示任意服務內部錯誤內容', async () => {
  vi.stubGlobal(
    'fetch',
    vi.fn((_url: string, options?: RequestInit) =>
      Promise.resolve(
        options?.method === 'DELETE'
          ? Response.json(
              { detail: { code: 'database_not_configured', message: 'private diagnostics' } },
              { status: 503 },
            )
          : Response.json({ job_files: [target] }),
      ),
    ),
  );
  renderList();
  const dialog = await openDelete();
  await userEvent.click(within(dialog).getByRole('button', { name: '永久刪除' }));
  expect(await within(dialog).findByRole('alert')).toHaveTextContent(/暫時無法取得服務結果/);
  expect(dialog).not.toHaveTextContent('private diagnostics');
  await userEvent.click(within(dialog).getByRole('button', { name: '取消' }));
  expect(await screen.findByRole('link', { name: /合成員工甲/ })).toBeVisible();
});

test('新增刪除操作後仍能在清單改名而不進入檔案', async () => {
  let renamed = false;
  vi.stubGlobal(
    'fetch',
    vi.fn((_url: string, options?: RequestInit) => {
      if (options?.method === 'POST') renamed = true;
      const file = { ...target, display_name: renamed ? '倉儲工作' : target.display_name };
      return Promise.resolve(
        Response.json(options?.method === 'POST' ? file : { job_files: [file] }),
      );
    }),
  );
  renderList();
  await userEvent.click(await screen.findByRole('button', { name: /重新命名 庫存管理/ }));
  const dialog = screen.getByRole('dialog', { name: '重新命名職務檔案' });
  const input = within(dialog).getByLabelText(/職務檔案名稱/);
  await userEvent.clear(input);
  await userEvent.type(input, '倉儲工作');
  await userEvent.click(within(dialog).getByRole('button', { name: '儲存名稱' }));
  expect(await screen.findByRole('link', { name: /開啟 倉儲工作/ })).toBeVisible();
  expect(screen.queryByText('已進入職務檔案')).not.toBeInTheDocument();
});
