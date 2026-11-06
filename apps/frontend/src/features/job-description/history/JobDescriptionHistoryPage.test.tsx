import { QueryClient, QueryClientProvider, useQuery } from '@tanstack/react-query';
import { act, render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { Link, MemoryRouter, Route, Routes } from 'react-router';
import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import type {
  HistoryEntryResponse,
  HistoryResponse,
  JobDescriptionResponse,
} from '../../../shared/api/generated/types.gen';
import { jobDescription, workspaceId } from '../../../../tests/fixtures';
import { storeDrafts } from '../editing/drafts';
import { jobDescriptionOptions } from '../queries';
import { JobDescriptionHistoryPage } from './JobDescriptionHistoryPage';

const current = { ...jobDescription, version: 3, job_title: '目前職務' };
const lookupPath = `/api/workspaces/${workspaceId}/job-description`;
const jdPath = `/api/workspaces/${workspaceId}/job-descriptions/${current.job_description_id}`;
const clients: QueryClient[] = [];

function entry(version: number): HistoryEntryResponse {
  return {
    job_description_id: current.job_description_id,
    version,
    kind: version === 1 ? 'created' : 'edited',
    recorded_at: '2026-10-27T10:00:00Z',
    correlation_id: null,
    reverts_correlation_id: null,
    restored_from_version: null,
  };
}

function snapshot(version: number): HistoryResponse {
  const content = { ...current, version: undefined };
  return {
    content: {
      ...content,
      job_title: version === 3 ? '目前職務' : `舊職務 ${String(version)}`,
    },
    entry: entry(version),
  };
}

function serveHistory(
  restore?: (init: RequestInit | undefined) => Response | Promise<Response>,
) {
  return vi.fn((input: string, init?: RequestInit) => {
    const url = new URL(input, 'http://localhost');
    if (url.pathname === lookupPath) return Promise.resolve(Response.json(current));
    if (url.pathname === `${jdPath}/history`)
      return Promise.resolve(
        Response.json(
          url.searchParams.has('page_token')
            ? { items: [entry(1)], next_page_token: null }
            : { items: [entry(3), entry(2)], next_page_token: 'older-page' },
        ),
      );
    if (url.pathname === `${jdPath}/history:compare`)
      return Promise.resolve(
        Response.json({
          job_description_id: current.job_description_id,
          before_version: Number(url.searchParams.get('before_version')),
          after_version: Number(url.searchParams.get('after_version')),
          items: [],
          collections: [],
        }),
      );
    if (url.pathname.startsWith(`${jdPath}/history/`))
      return Promise.resolve(
        Response.json(snapshot(Number(url.pathname.split('/').at(-1)))),
      );
    if (url.pathname === `${jdPath}:restore` && restore)
      return Promise.resolve(restore(init));
    throw new Error(`Unexpected request: ${url.pathname}`);
  });
}

function CurrentPage() {
  const currentQuery = useQuery(jobDescriptionOptions(workspaceId));
  return (
    <>
      <h1>返回目前職務說明書</h1>
      <p>目前版本：{currentQuery.data?.version}</p>
      <Link to={`/workspaces/${workspaceId}/jd/history`}>再看歷史</Link>
    </>
  );
}

function showHistory() {
  const cache = new QueryClient({
    defaultOptions: {
      queries: { retry: false, staleTime: Infinity },
      mutations: { retry: false },
    },
  });
  clients.push(cache);
  render(
    <QueryClientProvider client={cache}>
      <MemoryRouter initialEntries={[`/workspaces/${workspaceId}/jd/history`]}>
        <Routes>
          <Route
            path="/workspaces/:workspaceId/jd/history"
            element={
              <JobDescriptionHistoryPage
                workspaceId={workspaceId}
                intervieweeName="合成受訪者"
              />
            }
          />
          <Route path="/workspaces/:workspaceId/jd" element={<CurrentPage />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
  return cache;
}

beforeEach(() => {
  sessionStorage.clear();
  vi.stubGlobal(
    'matchMedia',
    vi.fn(() => ({ matches: false })),
  );
  Object.defineProperty(HTMLDialogElement.prototype, 'showModal', {
    configurable: true,
    value: function (this: HTMLDialogElement) {
      this.open = true;
    },
  });
  Object.defineProperty(HTMLDialogElement.prototype, 'close', {
    configurable: true,
    value: function (this: HTMLDialogElement) {
      this.open = false;
    },
  });
});
afterEach(() => {
  clients.splice(0).forEach((cache) => {
    cache.clear();
  });
});

it('以游標載入較早版本，預覽保持唯讀且可以比較任意兩個歷史版本', async () => {
  const fetch = serveHistory();
  vi.stubGlobal('fetch', fetch);
  showHistory();
  const user = userEvent.setup();
  await user.click(await screen.findByRole('button', { name: '預覽版本 2' }));
  expect(
    await screen.findByRole('heading', { name: '舊職務 2', level: 1 }),
  ).toBeVisible();
  expect(screen.queryByRole('textbox')).not.toBeInTheDocument();
  await user.click(screen.getByRole('button', { name: '載入較早版本' }));
  await screen.findByRole('button', { name: '預覽版本 1' });
  expect(fetch.mock.calls.some(([url]) => url.includes('page_token=older-page'))).toBe(
    true,
  );
  await user.click(screen.getByRole('button', { name: '比較版本' }));
  await user.selectOptions(screen.getByRole('combobox', { name: '比較起始版本' }), '1');
  await user.selectOptions(screen.getByRole('combobox', { name: '比較目標版本' }), '2');
  expect(await screen.findByText('這兩個版本沒有內容差異。')).toBeVisible();
  await waitFor(() =>
    expect(
      fetch.mock.calls.some(([url]) => url.includes('before_version=1&after_version=2')),
    ).toBe(true),
  );
});

it('恢復帶目前版本且使用成功回覆的新版本，較早的查詢不能覆蓋它', async () => {
  const restored: JobDescriptionResponse = {
    ...current,
    version: 4,
    job_title: '舊職務 2',
  };
  const posts: unknown[] = [];
  const server = serveHistory((init) => {
    if (typeof init?.body !== 'string') throw new Error('Expected a JSON request body');
    posts.push(JSON.parse(init.body));
    return Response.json(restored);
  });
  let finishLookup: (response: Response) => void = () => {
    throw new Error('尚未重查');
  };
  let lookupCount = 0;
  vi.stubGlobal(
    'fetch',
    vi.fn((input: string, init?: RequestInit) => {
      if (input === lookupPath && ++lookupCount === 2)
        return new Promise<Response>((resolve) => {
          finishLookup = resolve;
        });
      return server(input, init);
    }),
  );
  const cache = showHistory();
  const user = userEvent.setup();
  await user.click(await screen.findByRole('button', { name: '預覽版本 2' }));
  await screen.findByRole('heading', { name: '舊職務 2', level: 1 });
  act(() => {
    void cache.refetchQueries({
      queryKey: jobDescriptionOptions(workspaceId).queryKey,
      exact: true,
    });
  });
  await user.click(screen.getByRole('button', { name: '恢復此版本' }));
  const dialog = screen.getByRole('dialog');
  expect(dialog).toHaveTextContent('目前版本 3');
  expect(dialog).toHaveTextContent('版本 2');
  await user.click(within(dialog).getByRole('button', { name: '確認恢復' }));
  await screen.findByRole('heading', { name: '返回目前職務說明書' });
  act(() => {
    finishLookup(Response.json(current));
  });
  expect(posts).toEqual([{ expected_version: 3, target_version: 2 }]);
  expect(cache.getQueryData(jobDescriptionOptions(workspaceId).queryKey)).toEqual(
    restored,
  );
});

it('有未確認草稿時只能返回編輯頁處理，不能恢復歷史', async () => {
  storeDrafts(workspaceId, current.job_description_id, {
    purpose: { value: '尚未送出的文字', baseValue: null, label: '職務目的' },
  });
  vi.stubGlobal('fetch', serveHistory());
  showHistory();
  await screen.findByRole('button', { name: '預覽版本 2' });
  expect(screen.getByRole('alert')).toHaveTextContent('未確認輸入');
  expect(screen.queryByRole('button', { name: '恢復此版本' })).not.toBeInTheDocument();
  expect(screen.getByRole('link', { name: '返回編輯頁處理輸入' })).toHaveAttribute(
    'href',
    `/workspaces/${workspaceId}/jd`,
  );
});

it('恢復結果未知時保留歷史頁與錯誤，不能再次送出', async () => {
  const fetch = serveHistory(() =>
    Response.json(
      { detail: { code: 'jd_write_outcome_unknown', commit_status: 'unknown' } },
      { status: 500 },
    ),
  );
  vi.stubGlobal('fetch', fetch);
  showHistory();
  const user = userEvent.setup();
  await user.click(await screen.findByRole('button', { name: '預覽版本 2' }));
  await screen.findByRole('heading', { name: '舊職務 2', level: 1 });
  await user.click(screen.getByRole('button', { name: '恢復此版本' }));
  await user.click(screen.getByRole('button', { name: '確認恢復' }));
  expect(await screen.findByRole('alert')).toHaveTextContent('無法確認');
  expect(screen.getByRole('button', { name: '確認恢復' })).toBeDisabled();
  expect(
    screen.queryByRole('heading', { name: '返回目前職務說明書' }),
  ).not.toBeInTheDocument();
  expect(fetch.mock.calls.filter(([url]) => url.endsWith(':restore'))).toHaveLength(1);
  await user.click(screen.getByRole('button', { name: '取消' }));
  expect(screen.queryByRole('button', { name: '恢復此版本' })).not.toBeInTheDocument();
  expect(screen.getByRole('link', { name: '返回目前 JD 核對' })).toBeVisible();
});

it('確認視窗開啟後出現未確認輸入，也必須阻止恢復', async () => {
  const fetch = serveHistory();
  vi.stubGlobal('fetch', fetch);
  showHistory();
  const user = userEvent.setup();
  await user.click(await screen.findByRole('button', { name: '預覽版本 2' }));
  await screen.findByRole('heading', { name: '舊職務 2', level: 1 });
  await user.click(screen.getByRole('button', { name: '恢復此版本' }));
  storeDrafts(workspaceId, current.job_description_id, {
    purpose: { value: '剛新增的草稿', baseValue: null, label: '職務目的' },
  });
  await user.click(screen.getByRole('button', { name: '確認恢復' }));
  expect(screen.getByRole('alert')).toHaveTextContent('未確認輸入');
  expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
  expect(fetch.mock.calls.filter(([url]) => url.endsWith(':restore'))).toHaveLength(0);
});

it('恢復成功後再開歷史會讀取包含新版本的清單', async () => {
  let restored = false;
  const server = serveHistory(() => {
    restored = true;
    return Response.json({ ...current, version: 4, job_title: '舊職務 2' });
  });
  vi.stubGlobal('fetch', (input: string, init?: RequestInit) => {
    if (restored && input.includes('/history?'))
      return Promise.resolve(
        Response.json({ items: [entry(4), entry(3), entry(2)], next_page_token: null }),
      );
    return server(input, init);
  });
  showHistory();
  const user = userEvent.setup();
  await user.click(await screen.findByRole('button', { name: '預覽版本 2' }));
  await screen.findByRole('heading', { name: '舊職務 2', level: 1 });
  await user.click(screen.getByRole('button', { name: '恢復此版本' }));
  await user.click(screen.getByRole('button', { name: '確認恢復' }));
  await user.click(await screen.findByRole('link', { name: '再看歷史' }));
  expect(await screen.findByRole('button', { name: '預覽版本 4' })).toBeVisible();
});

it('恢復結果未知後返回目前 JD 必須重新讀取，不能使用舊快取核對', async () => {
  let serverChanged = false;
  const server = serveHistory(() => {
    serverChanged = true;
    return Response.json(
      { detail: { code: 'jd_write_outcome_unknown', commit_status: 'unknown' } },
      { status: 500 },
    );
  });
  vi.stubGlobal('fetch', (input: string, init?: RequestInit) => {
    if (serverChanged && input === lookupPath)
      return Promise.resolve(Response.json({ ...current, version: 4 }));
    return server(input, init);
  });
  showHistory();
  const user = userEvent.setup();
  await user.click(await screen.findByRole('button', { name: '預覽版本 2' }));
  await screen.findByRole('heading', { name: '舊職務 2', level: 1 });
  await user.click(screen.getByRole('button', { name: '恢復此版本' }));
  await user.click(screen.getByRole('button', { name: '確認恢復' }));
  await user.click(await screen.findByRole('link', { name: '返回目前 JD 核對' }));
  expect(await screen.findByText('目前版本：4')).toBeVisible();
});
