/** Saved plan selection and terminal refresh, exercised through the real pane and query cache. */
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { act, render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, beforeEach, expect, test, vi } from 'vitest';
import type { ConsultantTurn } from '../shared/api/generated/consultant-turn';
import { InterviewPane } from './InterviewPane';
import { consultantTurnQuery, retainTurnHint } from '../features/interview/interview-turn-api';

const fileId = '10000000-0000-4000-8000-000000000001';
const executionId = '20000000-0000-4000-8000-000000000002';
const clients: QueryClient[] = [];
const planKey = ['job-file', fileId, 'interview-plan'];
const active: ConsultantTurn = {
  job_file_id: fileId,
  execution_id: executionId,
  status: 'active',
  pause_requested: false,
  input_text: '合成訪談',
  allowed_controls: [],
  commentary: [],
  candidate: null,
  plan_preview: { plan: '候選待追問' },
};

function renderPane(client = new QueryClient({ defaultOptions: { queries: { retry: false } } })) {
  clients.push(client);
  return {
    client,
    ...render(
      <QueryClientProvider client={client}>
        <InterviewPane jobFileId={fileId} />
      </QueryClientProvider>,
    ),
  };
}

function stubServer(plan: string | null, turn: ConsultantTurn | null = null) {
  const state = { plan, turn };
  vi.stubGlobal(
    'fetch',
    vi.fn((path: string) => {
      if (path.endsWith('/interview-plan'))
        return Promise.resolve(Response.json({ job_file_id: fileId, plan: state.plan }));
      if (path.endsWith('/consultant-turns/current'))
        return Promise.resolve(Response.json({ turn: state.turn }));
      if (path.includes('/consultant-turns/')) return Promise.resolve(Response.json(state.turn));
      if (path.endsWith('/interviews')) return Promise.resolve(Response.json({ messages: [] }));
      return Promise.resolve(new Response(null, { status: 404 }));
    }),
  );
  return state;
}

beforeEach(() => localStorage.clear());
afterEach(() => {
  clients.splice(0).forEach((client) => client.clear());
  vi.unstubAllGlobals();
});

test('shows the adopted saved plan as read-only Markdown when idle', async () => {
  stubServer('## 未釐清子任務\n- 盤點差異由誰確認？');
  renderPane();
  const plan = await screen.findByRole('region', { name: '工作計畫' });
  expect(await within(plan).findByText('盤點差異由誰確認？')).toBeVisible();
  expect(within(plan).queryByRole('textbox')).not.toBeInTheDocument();
});

test('a terminal refresh without adopted cache reports unavailable instead of inventing a previous version', async () => {
  const terminal: ConsultantTurn = { ...active, status: 'completed' };
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  client.setQueryData(consultantTurnQuery(fileId, executionId).queryKey, terminal);
  await retainTurnHint(fileId, {
    command_id: '30000000-0000-4000-8000-000000000003',
    execution_id: executionId,
  });
  stubServer(null, terminal);
  const existingFetch = globalThis.fetch;
  vi.stubGlobal('fetch', (path: RequestInfo | URL, options?: RequestInit) =>
    typeof path === 'string' && path.endsWith('/interview-plan')
      ? new Promise<Response>(() => undefined)
      : existingFetch(path, options),
  );
  renderPane(client);
  const region = await screen.findByRole('region', { name: '工作計畫' });
  expect(await within(region).findByText(/工作計畫目前不可用/)).toBeVisible();
  expect(within(region).queryByText('上一採用版，等待更新')).not.toBeInTheDocument();
});

test.each([
  [null, '尚未建立工作計畫。'],
  ['', '工作計畫目前沒有記錄項目。'],
])('distinguishes saved plan %s without declaring the interview complete', async (plan, label) => {
  stubServer(plan);
  renderPane();
  const region = await screen.findByRole('region', { name: '工作計畫' });
  expect(await within(region).findByText(label)).toBeVisible();
  expect(within(region).queryByText(/訪談.*完成/)).not.toBeInTheDocument();
});

test.each(['active', 'paused'] as const)(
  'uses only the verified %s candidate, including deliberate blank',
  async (status) => {
    const turn = { ...active, status, plan_preview: { plan: '' } };
    stubServer('原採用筆記', turn);
    await retainTurnHint(fileId, {
      command_id: '30000000-0000-4000-8000-000000000003',
      execution_id: executionId,
    });
    renderPane();
    const region = await screen.findByRole('region', { name: '工作計畫' });
    expect(await within(region).findByText('本輪候選')).toBeVisible();
    expect(within(region).getByText('工作計畫目前沒有記錄項目。')).toBeVisible();
    expect(within(region).queryByText('原採用筆記')).not.toBeInTheDocument();
  },
);

test.each(['completed', 'cancelled', 'failed'] as const)(
  'withdraws the candidate on %s and retries an unconfirmed adopted refresh',
  async (status) => {
    const state = stubServer('上一採用筆記', active);
    await retainTurnHint(fileId, {
      command_id: '30000000-0000-4000-8000-000000000003',
      execution_id: executionId,
    });
    const { client } = renderPane();
    const region = await screen.findByRole('region', { name: '工作計畫' });
    expect(await within(region).findByText('候選待追問')).toBeVisible();
    await waitFor(() =>
      expect(client.getQueryData(planKey)).toEqual({ job_file_id: fileId, plan: '上一採用筆記' }),
    );
    let unavailable = true;
    const previousFetch = globalThis.fetch;
    vi.stubGlobal('fetch', (path: RequestInfo | URL, options?: RequestInit) => {
      const url = typeof path === 'string' ? path : path instanceof URL ? path.href : path.url;
      return url.endsWith('/interview-plan') && unavailable
        ? Promise.resolve(new Response(null, { status: 503 }))
        : previousFetch(path, options);
    });
    const terminal = { ...active, status };
    state.turn = terminal;
    act(() => {
      client.setQueryData(consultantTurnQuery(fileId, executionId).queryKey, terminal);
    });
    await waitFor(() => expect(within(region).queryByText('候選待追問')).not.toBeInTheDocument());
    expect(await within(region).findByText('上一採用版，等待更新')).toBeVisible();
    expect(within(region).getByText('上一採用筆記')).toBeVisible();
    const retry = await within(region).findByRole('button', { name: '重新讀取工作計畫' });
    unavailable = false;
    state.plan = '終局後採用筆記';
    await userEvent.click(retry);
    expect(await within(region).findByText('終局後採用筆記')).toBeVisible();
    expect(within(region).queryByText('上一採用版，等待更新')).not.toBeInTheDocument();
  },
);
