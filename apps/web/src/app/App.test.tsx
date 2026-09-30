import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { act, render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router';
import { afterEach, beforeEach, expect, test, vi } from 'vitest';
import type { JobFile } from '../shared/api/generated/job-file-list';
import { isRenameJobFileRequest } from '../shared/api/validation';
import { App } from './App';
import { retainTurnHint } from '../features/interview/interview-turn-api';

const firstFile: JobFile = {
  job_file_id: '10000000-0000-4000-8000-000000000001',
  display_name: '前端職務',
  employee_name: '合成員工甲',
  created_at: '2026-09-29T10:00:00Z',
  name_revision: 1,
};
const secondFile: JobFile = {
  ...firstFile,
  job_file_id: '20000000-0000-4000-8000-000000000002',
  employee_name: '合成員工乙',
};
const clients: QueryClient[] = [];
const emptyProfile = {
  revision_id: '40000000-0000-4000-8000-000000000004',
  profile: { job_title: null, organization_unit: null, reports_to: null, purpose: null },
};
const emptyWork = {
  revision_id: emptyProfile.revision_id,
  areas: [],
  tasks: [],
  capabilities: [],
  task_links: [],
  collaborators: [],
  conditions: [],
};

function renderApp(path = '/') {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  clients.push(client);
  const view = render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={[path]}>
        <App />
      </MemoryRouter>
    </QueryClientProvider>,
  );
  return { ...view, client };
}

function history(text: string): Response {
  return Response.json({
    messages: [
      {
        source_id: '30000000-0000-4000-8000-000000000003',
        interview_sequence: 1,
        speaker: 'app',
        interview_text: text,
        execution_id: null,
      },
    ],
  });
}

beforeEach(() => {
  sessionStorage.clear();
  localStorage.clear();
});
afterEach(() => {
  clients.splice(0).forEach((client) => client.clear());
  vi.unstubAllGlobals();
});

test('空清單提供建立入口，但不把未接上的訪談宣稱為可用', async () => {
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue(Response.json({ job_files: [] })));
  renderApp();
  expect(await screen.findByRole('heading', { name: '職務檔案' })).toBeVisible();
  expect(await screen.findByText('尚無職務檔案')).toBeVisible();
  expect(screen.getByRole('button', { name: '建立職務檔案' })).toBeEnabled();
  expect(screen.queryByRole('button', { name: '傳送' })).not.toBeInTheDocument();
});

test('讀取失敗不是空清單，使用者可以重新讀取', async () => {
  const fetch = vi.fn().mockRejectedValueOnce(new TypeError('offline'));
  fetch.mockResolvedValue(Response.json({ job_files: [] }));
  vi.stubGlobal('fetch', fetch);
  renderApp();
  expect(await screen.findByRole('alert')).toHaveTextContent('連線未完成');
  expect(screen.queryByText('尚無職務檔案')).not.toBeInTheDocument();
  await userEvent.click(screen.getByRole('button', { name: '重新讀取' }));
  expect(await screen.findByText('尚無職務檔案')).toBeVisible();
  expect(fetch).toHaveBeenCalledTimes(2);
});

test('格式不符的服務結果不可進入清單', async () => {
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue(Response.json({ job_files: [{}] })));
  renderApp();
  expect(await screen.findByRole('alert')).toHaveTextContent('資料格式不符');
  expect(screen.queryByRole('table')).not.toBeInTheDocument();
});

test('建立後開啟原檔案並回讀正式開場，不生成員工輸入', async () => {
  const user = userEvent.setup();
  const fetch = vi.fn<(path: string, options?: RequestInit) => Promise<Response>>();
  fetch.mockImplementation((path, options) => {
    if (path.endsWith('/consultant-turns/current'))
      return Promise.resolve(Response.json({ turn: null }));
    if (path.endsWith('/jd/work')) return Promise.resolve(Response.json(emptyWork));
    if (path.endsWith('/jd/profile')) return Promise.resolve(Response.json(emptyProfile));
    if (path.endsWith('/interviews')) return Promise.resolve(history('請談談最近一次完整的工作。'));
    if (path === '/api/job-files' && options?.method !== 'POST') {
      return Promise.resolve(Response.json({ job_files: [] }));
    }
    return Promise.resolve(Response.json(firstFile));
  });
  vi.stubGlobal('fetch', fetch);
  renderApp();
  await user.click(screen.getByRole('button', { name: '建立職務檔案' }));
  await user.type(screen.getByLabelText('職務檔案名稱', { exact: false }), firstFile.display_name);
  await user.type(screen.getByLabelText('受訪員工姓名', { exact: false }), firstFile.employee_name);
  await user.click(screen.getByRole('button', { name: '建立' }));
  expect(await screen.findByRole('heading', { name: firstFile.display_name })).toBeVisible();
  expect(await screen.findByText('請談談最近一次完整的工作。')).toBeVisible();
  expect(screen.getByRole('heading', { name: 'App 開場引導 · 訪談序號 1' })).toBeVisible();
  expect(screen.getByRole('textbox', { name: '訪談內容' })).toHaveValue('');
  expect(screen.getByRole('button', { name: '送出訪談' })).toBeEnabled();
  expect(fetch.mock.calls.filter(([, options]) => options?.method === 'POST')).toHaveLength(1);
});

test('同名檔案按身分切換，遲到的甲檔訪談不可顯示在乙檔', async () => {
  const user = userEvent.setup();
  let finishHistory: (value: Response) => void = () => {
    throw new Error('Uninitialized');
  };
  const delayedHistory = new Promise<Response>((resolve) => {
    finishHistory = resolve;
  });
  const fetch = vi.fn<(path: string) => Promise<Response>>();
  fetch.mockImplementation((path) => {
    if (path.endsWith('/consultant-turns/current'))
      return Promise.resolve(Response.json({ turn: null }));
    if (path.endsWith('/jd/work')) return Promise.resolve(Response.json(emptyWork));
    if (path.endsWith('/jd/profile')) return Promise.resolve(Response.json(emptyProfile));
    if (path === '/api/job-files')
      return Promise.resolve(Response.json({ job_files: [firstFile, secondFile] }));
    if (path.includes(firstFile.job_file_id)) {
      return path.endsWith('/interviews')
        ? delayedHistory
        : Promise.resolve(Response.json(firstFile));
    }
    if (path.includes(secondFile.job_file_id)) {
      return Promise.resolve(
        path.endsWith('/interviews') ? history('乙檔獨有的開場。') : Response.json(secondFile),
      );
    }
    throw new Error(`Unexpected path: ${path}`);
  });
  vi.stubGlobal('fetch', fetch);
  renderApp();
  await user.click(await screen.findByRole('link', { name: /開啟.*合成員工甲/ }));
  expect(await screen.findByText('正在讀取這份檔案的訪談…')).toBeVisible();
  await user.click(screen.getByRole('link', { name: /職務檔案清單/ }));
  await user.click(await screen.findByRole('link', { name: /開啟.*合成員工乙/ }));
  expect(await screen.findByText('乙檔獨有的開場。')).toBeVisible();
  await act(async () => {
    finishHistory(history('甲檔遲到的開場。'));
    await delayedHistory;
  });
  expect(screen.queryByText('甲檔遲到的開場。')).not.toBeInTheDocument();
  expect(screen.getByText('受訪員工：合成員工乙')).toBeVisible();
});

test('不存在的檔案顯示錯誤而非上一份內容或伺服器除錯文字', async () => {
  const fetch = vi
    .fn()
    .mockResolvedValue(Response.json({ detail: 'private debug' }, { status: 404 }));
  vi.stubGlobal('fetch', fetch);
  renderApp(`/job-files/${firstFile.job_file_id}`);
  expect(await screen.findByRole('alert')).toHaveTextContent('找不到這份職務檔案');
  expect(screen.queryByText('private debug')).not.toBeInTheDocument();
  expect(fetch).toHaveBeenCalledTimes(1);
});

test('歷史訪談以原文字串顯示，不解析成 HTML', async () => {
  const original = '<img src=x onerror="alert(1)">\n請說明工作。';
  vi.stubGlobal(
    'fetch',
    vi.fn((path: string) => {
      if (path.endsWith('/consultant-turns/current'))
        return Promise.resolve(Response.json({ turn: null }));
      if (path.endsWith('/jd/work')) return Promise.resolve(Response.json(emptyWork));
      if (path.endsWith('/jd/profile')) return Promise.resolve(Response.json(emptyProfile));
      return Promise.resolve(
        path.endsWith('/interviews') ? history(original) : Response.json(firstFile),
      );
    }),
  );
  renderApp(`/job-files/${firstFile.job_file_id}`);
  const paragraph = await screen.findByText(/<img src=x/);
  expect(paragraph.textContent).toBe(original);
  expect(paragraph.querySelector('img')).toBeNull();
});

test('列表改名只送標籤與讀取基準，保存後重讀清單', async () => {
  const user = userEvent.setup();
  let current = firstFile;
  const fetch = vi.fn<(path: string, options?: RequestInit) => Promise<Response>>();
  fetch.mockImplementation((path) => {
    if (path.endsWith('/rename')) {
      current = { ...firstFile, display_name: '目前工作紀錄', name_revision: 2 };
      return Promise.resolve(Response.json(current));
    }
    return Promise.resolve(Response.json({ job_files: [current, secondFile] }));
  });
  vi.stubGlobal('fetch', fetch);
  renderApp();
  await user.click(await screen.findByRole('button', { name: /重新命名.*合成員工甲/ }));
  const field = screen.getByRole('textbox', { name: '職務檔案名稱' });
  await user.clear(field);
  await user.type(field, '目前工作紀錄');
  await user.click(screen.getByRole('button', { name: '儲存名稱' }));
  expect(await screen.findByRole('link', { name: /開啟 目前工作紀錄.*合成員工甲/ })).toBeVisible();
  expect(screen.getByRole('link', { name: /開啟 前端職務.*合成員工乙/ })).toBeVisible();
  const sent = fetch.mock.calls.find(([path]) => path.endsWith('/rename'));
  const body = sent?.[1]?.body;
  if (typeof body !== 'string') throw new Error('Expected JSON command');
  const command: unknown = JSON.parse(body);
  if (!isRenameJobFileRequest(command)) throw new Error('Invalid rename command');
  expect(command.display_name).toBe('目前工作紀錄');
  expect(command.expected_name_revision).toBe(1);
  expect(Object.keys(command).sort()).toEqual([
    'command_id',
    'display_name',
    'expected_name_revision',
  ]);
});

test('改名結果不明，關閉重開仍送原命令而不採用新基準', async () => {
  const user = userEvent.setup();
  let current = firstFile;
  let attempt = 0;
  const fetch = vi.fn<(path: string, options?: RequestInit) => Promise<Response>>();
  fetch.mockImplementation((path) => {
    if (path.endsWith('/rename')) {
      attempt += 1;
      current = { ...firstFile, display_name: '已改名', name_revision: 2 };
      return attempt === 1
        ? Promise.reject(new TypeError('lost response'))
        : Promise.resolve(Response.json(current));
    }
    return Promise.resolve(Response.json({ job_files: [current] }));
  });
  vi.stubGlobal('fetch', fetch);
  const view = renderApp();
  await user.click(await screen.findByRole('button', { name: /重新命名/ }));
  const field = screen.getByRole('textbox', { name: '職務檔案名稱' });
  await user.clear(field);
  await user.type(field, '已改名');
  await user.click(screen.getByRole('button', { name: '儲存名稱' }));
  expect(await screen.findByRole('alert')).toHaveTextContent('改名結果尚未確認');
  view.unmount();
  renderApp();
  await user.click(await screen.findByRole('button', { name: /重新命名/ }));
  expect(screen.getByRole('textbox', { name: '職務檔案名稱' })).toBeDisabled();
  await user.click(screen.getByRole('button', { name: '重新確認改名結果' }));
  expect(await screen.findByRole('link', { name: /開啟 已改名/ })).toBeVisible();
  const writes = fetch.mock.calls.filter(([path]) => path.endsWith('/rename'));
  expect(writes).toHaveLength(2);
  expect(writes[1]?.[1]?.body).toBe(writes[0]?.[1]?.body);
});

test('過期改名不可自行換基準重送，先要求重讀', async () => {
  const user = userEvent.setup();
  let current = firstFile;
  const fetch = vi.fn<(path: string) => Promise<Response>>();
  fetch.mockImplementation((path) => {
    if (path.endsWith('/rename')) {
      current = { ...firstFile, display_name: '其他分頁改名', name_revision: 2 };
      return Promise.resolve(
        Response.json({ detail: { code: 'stale_job_file_name' } }, { status: 409 }),
      );
    }
    return Promise.resolve(Response.json({ job_files: [current] }));
  });
  vi.stubGlobal('fetch', fetch);
  renderApp();
  await user.click(await screen.findByRole('button', { name: /重新命名/ }));
  await user.click(screen.getByRole('button', { name: '儲存名稱' }));
  expect(await screen.findByRole('alert')).toHaveTextContent('改名未被接受');
  expect(fetch.mock.calls.filter(([path]) => path.endsWith('/rename'))).toHaveLength(1);
  await user.click(screen.getByRole('button', { name: '讀取目前名稱' }));
  expect(await screen.findByRole('link', { name: /開啟 其他分頁改名/ })).toBeVisible();
});

test('職務檔案提供 JD 基本資料讀取與人工編輯入口', async () => {
  const consoleError = vi.spyOn(console, 'error');
  vi.stubGlobal(
    'fetch',
    vi.fn((path: string) => {
      if (path.endsWith('/consultant-turns/current'))
        return Promise.resolve(Response.json({ turn: null }));
      if (path.endsWith('/jd/work')) return Promise.resolve(Response.json(emptyWork));
      if (path.endsWith('/jd/profile')) {
        return Promise.resolve(
          Response.json({
            revision_id: '40000000-0000-4000-8000-000000000004',
            profile: {
              job_title: '前端工程師',
              organization_unit: null,
              reports_to: null,
              purpose: null,
            },
          }),
        );
      }
      return Promise.resolve(
        path.endsWith('/interviews') ? history('請說明工作。') : Response.json(firstFile),
      );
    }),
  );
  renderApp(`/job-files/${firstFile.job_file_id}`);
  expect(await screen.findByRole('heading', { name: 'JD 基本資料' })).toBeVisible();
  expect(await screen.findByText('前端工程師')).toBeVisible();
  expect(screen.getByRole('button', { name: '編輯基本資料' })).toBeEnabled();
  expect(await screen.findByRole('heading', { name: 'JD 職責與任務' })).toBeVisible();
  expect(await screen.findByRole('button', { name: '新增職責' })).toBeEnabled();
  expect(consoleError).not.toHaveBeenCalled();
});

test('PDF 下載入口使用同檔案正式稿網址並明示不含候選預覽', async () => {
  vi.stubGlobal(
    'fetch',
    vi.fn((path: string) => {
      if (path.endsWith('/consultant-turns/current'))
        return Promise.resolve(Response.json({ turn: null }));
      if (path.endsWith('/jd/work')) return Promise.resolve(Response.json(emptyWork));
      if (path.endsWith('/jd/profile')) return Promise.resolve(Response.json(emptyProfile));
      return Promise.resolve(
        path.endsWith('/interviews') ? history('請說明工作。') : Response.json(firstFile),
      );
    }),
  );
  renderApp(`/job-files/${firstFile.job_file_id}`);
  const download = await screen.findByRole('link', { name: '匯出目前 JD（PDF）' });
  expect(download).toHaveAttribute('href', `/api/job-files/${firstFile.job_file_id}/jd/export.pdf`);
  expect(download).toHaveAttribute('download');
  expect(screen.getByText('匯出目前已正式保存的版本，不包含本輪候選預覽。')).toBeVisible();
});

test('metadata 背景讀取失敗不卸載尚未送出的訪談與 JD 表單草稿', async () => {
  const user = userEvent.setup();
  let metadataUnavailable = false;
  const fetch = vi.fn<(path: string, options?: RequestInit) => Promise<Response>>((path) => {
    if (path.endsWith('/consultant-turns/current'))
      return Promise.resolve(Response.json({ turn: null }));
    if (path.endsWith('/jd/work')) return Promise.resolve(Response.json(emptyWork));
    if (path.endsWith('/jd/profile')) return Promise.resolve(Response.json(emptyProfile));
    if (path.endsWith('/interviews')) return Promise.resolve(history('正式開場'));
    return Promise.resolve(
      metadataUnavailable ? new Response(null, { status: 503 }) : Response.json(firstFile),
    );
  });
  vi.stubGlobal('fetch', fetch);
  const { client } = renderApp(`/job-files/${firstFile.job_file_id}`);
  await user.type(await screen.findByRole('textbox', { name: '訪談內容' }), '尚未送出的原話');
  await user.click(await screen.findByRole('button', { name: '編輯基本資料' }));
  await user.type(screen.getByRole('textbox', { name: '職務名稱' }), '尚未保存的職稱');

  metadataUnavailable = true;
  await act(async () => {
    await client.refetchQueries({ queryKey: ['job-file', firstFile.job_file_id], exact: true });
  });
  expect(await screen.findByText('暫時無法取得服務結果，請稍後再試。')).toBeInTheDocument();
  expect(screen.getByRole('textbox', { name: '職務名稱' })).toHaveValue('尚未保存的職稱');
  await user.click(screen.getByRole('button', { name: '返回 JD' }));
  expect(screen.getByRole('textbox', { name: '訪談內容' })).toHaveValue('尚未送出的原話');
  expect(screen.getByText('暫時無法取得服務結果，請稍後再試。')).toBeVisible();

  metadataUnavailable = false;
  await user.click(screen.getByRole('button', { name: '重新讀取' }));
  expect(screen.getByRole('textbox', { name: '訪談內容' })).toHaveValue('尚未送出的原話');
  expect(fetch.mock.calls.some(([, options]) => options?.method === 'POST')).toBe(false);
});

test('cancelling a candidate removes only the preview and keeps the formal JD', async () => {
  const executionId = '50000000-0000-4000-8000-000000000005';
  const formalProfile = {
    ...emptyProfile,
    profile: { ...emptyProfile.profile, job_title: '原正式工程師' },
  };
  retainTurnHint(firstFile.job_file_id, {
    command_id: '60000000-0000-4000-8000-000000000006',
    execution_id: executionId,
  });
  let cancelled = false;
  vi.stubGlobal(
    'fetch',
    vi.fn((path: string, options?: RequestInit) => {
      if (path.endsWith('/jd/work')) return Promise.resolve(Response.json(emptyWork));
      if (path.endsWith('/jd/profile')) return Promise.resolve(Response.json(formalProfile));
      if (path.endsWith('/cancel') && options?.method === 'POST') cancelled = true;
      if (path.includes('/consultant-turns/'))
        return Promise.resolve(
          Response.json({
            job_file_id: firstFile.job_file_id,
            execution_id: executionId,
            status: cancelled ? 'cancelled' : 'active',
            pause_requested: false,
            input_text: '尚非正式的輸入',
            allowed_controls: cancelled ? [] : ['cancel'],
            commentary: [],
            candidate: !cancelled
              ? { profile: { ...emptyProfile.profile, job_title: '候選工程師' }, work: emptyWork }
              : null,
          }),
        );
      return Promise.resolve(
        path.endsWith('/interviews') ? history('正式開場') : Response.json(firstFile),
      );
    }),
  );
  renderApp(`/job-files/${firstFile.job_file_id}`);
  expect(await screen.findByRole('region', { name: 'JD 候選預覽' })).toBeVisible();
  expect(screen.getByText('候選工程師')).toBeVisible();
  expect(
    screen.getByText('尚未正式保存；完成前不會取代正式 JD，PDF 仍匯出正式版本。'),
  ).toBeVisible();
  // The candidate is a separate view: the formal draft is one click away and never replaced.
  await userEvent.click(screen.getByRole('button', { name: '正式稿' }));
  expect(await screen.findByText('原正式工程師')).toBeVisible();
  expect(screen.queryByRole('region', { name: 'JD 候選預覽' })).not.toBeInTheDocument();
  expect(screen.getByRole('heading', { name: 'JD 基本資料' })).toBeVisible();
  await userEvent.click(screen.getByRole('button', { name: '取消處理' }));
  expect(await screen.findByText(/這次處理已取消/, {}, { timeout: 3_000 })).toBeVisible();
  expect(screen.queryByRole('region', { name: 'JD 候選預覽' })).not.toBeInTheDocument();
  expect(screen.queryByText('候選工程師')).not.toBeInTheDocument();
  expect(screen.getByText('原正式工程師')).toBeVisible();
  expect(screen.getByRole('heading', { name: 'JD 基本資料' })).toBeVisible();
});

test('狀態查詢失敗不沿用候選或控制；查回 failed 仍保留正式 JD 且不重送輸入', async () => {
  const executionId = '50000000-0000-4000-8000-000000000005';
  retainTurnHint(firstFile.job_file_id, {
    command_id: '60000000-0000-4000-8000-000000000006',
    execution_id: executionId,
  });
  let state: 'active' | 'unavailable' | 'failed' = 'active';
  const fetch = vi.fn<(path: string, options?: RequestInit) => Promise<Response>>((path) => {
    if (path.endsWith('/jd/work')) return Promise.resolve(Response.json(emptyWork));
    if (path.endsWith('/jd/profile'))
      return Promise.resolve(
        Response.json({
          ...emptyProfile,
          profile: { ...emptyProfile.profile, job_title: '原正式工程師' },
        }),
      );
    if (path.includes('/consultant-turns/'))
      return Promise.resolve(
        state === 'unavailable'
          ? Response.json({ detail: 'private diagnostic' }, { status: 503 })
          : Response.json({
              job_file_id: firstFile.job_file_id,
              execution_id: executionId,
              status: state,
              pause_requested: false,
              input_text: '尚非正式的輸入',
              allowed_controls: state === 'active' ? ['pause', 'cancel'] : [],
              commentary: [],
              candidate:
                state === 'active'
                  ? {
                      profile: { ...emptyProfile.profile, job_title: '候選工程師' },
                      work: emptyWork,
                    }
                  : null,
            }),
      );
    return Promise.resolve(
      path.endsWith('/interviews') ? history('正式開場') : Response.json(firstFile),
    );
  });
  vi.stubGlobal('fetch', fetch);
  const { client } = renderApp(`/job-files/${firstFile.job_file_id}`);
  expect(await screen.findByRole('region', { name: 'JD 候選預覽' })).toBeVisible();
  expect(screen.getByRole('button', { name: '暫停處理' })).toBeVisible();
  state = 'unavailable';
  await act(async () => {
    await client.refetchQueries({
      queryKey: ['consultant-turn', firstFile.job_file_id, executionId],
    });
  });
  const retry = await screen.findByRole('button', { name: '重新讀取狀態' });
  expect(screen.queryByRole('region', { name: 'JD 候選預覽' })).not.toBeInTheDocument();
  expect(screen.queryByRole('button', { name: /暫停處理|取消處理/ })).not.toBeInTheDocument();
  expect(screen.queryByText('private diagnostic')).not.toBeInTheDocument();
  expect(screen.getByText('原正式工程師')).toBeVisible();

  state = 'failed';
  await userEvent.click(retry);
  expect(await screen.findByText(/這次處理未能完成/)).toBeVisible();
  expect(screen.getByText('尚非正式的輸入')).toBeVisible();
  expect(screen.getByText('原正式工程師')).toBeVisible();
  expect(screen.queryByRole('region', { name: 'JD 候選預覽' })).not.toBeInTheDocument();
  expect(
    screen.queryByRole('button', { name: /暫停處理|取消處理|繼續處理/ }),
  ).not.toBeInTheDocument();
  expect(screen.getAllByRole('heading', { name: /訪談序號/ })).toHaveLength(1);
  expect(fetch.mock.calls.some(([, options]) => options?.method === 'POST')).toBe(false);
});

test('歷史回答按需確認撤回只送原 Turn，成功重讀正式稿而不採用舊回傳覆蓋後來稿', async () => {
  const executionId = '50000000-0000-4000-8000-000000000005';
  const turnUrl = `/api/job-files/${firstFile.job_file_id}/consultant-turns/${executionId}`;
  let undone = false;
  let statusReads = 0;
  let workReads = 0;
  const writes: string[] = [];
  vi.stubGlobal(
    'fetch',
    vi.fn((path: string, options?: RequestInit) => {
      if (options?.method === 'POST') {
        expect(path).toBe(`${turnUrl}/undo-jd`);
        expect(options.body).toBeUndefined();
        writes.push(path);
        undone = true;
        return Promise.resolve(Response.json(emptyProfile));
      }
      if (path.endsWith('/jd/work')) {
        workReads += 1;
        return Promise.resolve(Response.json(emptyWork));
      }
      if (path.endsWith('/jd/profile'))
        return Promise.resolve(
          Response.json({
            ...emptyProfile,
            profile: {
              ...emptyProfile.profile,
              job_title: undone ? '撤回後其他頁面修改' : '原輪正式職稱',
            },
          }),
        );
      if (path.endsWith('/interviews'))
        return Promise.resolve(
          Response.json({
            messages: [
              {
                source_id: '30000000-0000-4000-8000-000000000003',
                interview_sequence: 3,
                speaker: 'consultant',
                interview_text: '應一直保留的正式回答',
                execution_id: executionId,
              },
            ],
          }),
        );
      if (path === turnUrl) {
        statusReads += 1;
        return Promise.resolve(
          Response.json({
            job_file_id: firstFile.job_file_id,
            execution_id: executionId,
            status: 'completed',
            pause_requested: false,
            allowed_controls: [],
            input_text: '不重複顯示',
            commentary: [],
            candidate: null,
          }),
        );
      }
      return Promise.resolve(Response.json(firstFile));
    }),
  );
  renderApp(`/job-files/${firstFile.job_file_id}`);
  expect(await screen.findByText('應一直保留的正式回答')).toBeVisible();
  expect(await screen.findByText('原輪正式職稱')).toBeVisible();
  expect(screen.queryByRole('button', { name: '撤回這輪 JD' })).not.toBeInTheDocument();
  expect(statusReads).toBe(0);
  await userEvent.click(screen.getByRole('button', { name: /回看本次公開處理訊息/ }));
  await userEvent.click(await screen.findByRole('button', { name: '撤回這輪 JD' }));
  expect(screen.getByRole('dialog')).toHaveTextContent('不撤回訪談或工作記憶');
  expect(screen.getByRole('dialog')).toHaveTextContent('後續人工修改');
  expect(writes).toEqual([]);
  await userEvent.click(screen.getByRole('button', { name: '確認只撤回這輪 JD' }));
  expect(await screen.findByText(/這輪 JD 撤回已確認/)).toBeVisible();
  expect(await screen.findByText('撤回後其他頁面修改')).toBeVisible();
  expect(screen.getByText('應一直保留的正式回答')).toBeVisible();
  expect(statusReads).toBeGreaterThanOrEqual(2);
  expect(workReads).toBeGreaterThanOrEqual(2);
  expect(writes).toEqual([`${turnUrl}/undo-jd`]);
});
