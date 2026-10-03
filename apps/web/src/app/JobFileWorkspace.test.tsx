/** Workspace behavior: JD read-only lock, Turn state badge and narrow-screen pane switching. */
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router';
import { afterEach, beforeEach, expect, test, vi } from 'vitest';
import type { JobFile } from '../shared/api/generated/job-file-list';
import { retainTurnHint } from '../features/interview/interview-turn-api';
import { App } from './App';

const file: JobFile = {
  job_file_id: '10000000-0000-4000-8000-000000000001',
  display_name: '前端職務',
  employee_name: '合成員工甲',
  created_at: '2026-09-29T10:00:00Z',
  name_revision: 1,
};
const executionId = '50000000-0000-4000-8000-000000000005';
const profile = {
  revision_id: '40000000-0000-4000-8000-000000000004',
  profile: { job_title: '原正式工程師', organization_unit: null, reports_to: null, purpose: null },
};
const work = {
  revision_id: profile.revision_id,
  areas: [],
  tasks: [],
  capabilities: [],
  task_links: [],
  collaborators: [],
  conditions: [],
};
const clients: QueryClient[] = [];

function renderJobFile() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  clients.push(client);
  return {
    client,
    ...render(
      <QueryClientProvider client={client}>
        <MemoryRouter initialEntries={[`/job-files/${file.job_file_id}`]}>
          <App />
        </MemoryRouter>
      </QueryClientProvider>,
    ),
  };
}

function turnBody(status: 'active' | 'paused' | 'cancelled') {
  const live = status !== 'cancelled';
  return {
    job_file_id: file.job_file_id,
    execution_id: executionId,
    status,
    pause_requested: false,
    input_text: '尚非正式的輸入',
    allowed_controls: live ? ['cancel'] : [],
    commentary: [],
    candidate: live ? { profile: { ...profile.profile, job_title: '候選工程師' }, work } : null,
  };
}

beforeEach(() => {
  sessionStorage.clear();
  localStorage.clear();
});
afterEach(() => {
  clients.splice(0).forEach((client) => client.clear());
  vi.unstubAllGlobals();
});

test.each([true, false])(
  'JD locks and previews the active Turn, then reopens after cancel (local hint: %s)',
  async (hasHint) => {
    if (hasHint)
      retainTurnHint(file.job_file_id, {
        command_id: '60000000-0000-4000-8000-000000000006',
        execution_id: executionId,
      });
    let cancelled = false;
    vi.stubGlobal(
      'fetch',
      vi.fn((path: string, options?: RequestInit) => {
        if (path.endsWith('/cancel') && options?.method === 'POST') cancelled = true;
        if (path.endsWith('/jd/work')) return Promise.resolve(Response.json(work));
        if (path.endsWith('/jd/profile')) return Promise.resolve(Response.json(profile));
        if (path.endsWith('/consultant-turns/current'))
          return Promise.resolve(Response.json({ turn: cancelled ? null : turnBody('active') }));
        if (path.includes('/consultant-turns/'))
          return Promise.resolve(Response.json(turnBody(cancelled ? 'cancelled' : 'active')));
        if (path.endsWith('/interviews')) return Promise.resolve(Response.json({ messages: [] }));
        return Promise.resolve(Response.json(file));
      }),
    );
    renderJobFile();
    expect(await screen.findByText(/顧問處理中，JD 暫時唯讀/)).toBeVisible();
    expect(screen.getByText('顧問處理中')).toBeVisible();
    await userEvent.click(screen.getByRole('button', { name: '正式稿' }));
    expect(await screen.findByText('原正式工程師')).toBeVisible();
    expect(screen.getByRole('button', { name: '修改職務名稱' })).toHaveAttribute(
      'aria-disabled',
      'true',
    );
    expect(screen.getByRole('button', { name: '新增職責' })).toHaveAttribute(
      'aria-disabled',
      'true',
    );

    await userEvent.click(screen.getByRole('button', { name: '取消處理' }));
    expect(await screen.findByText(/這次處理已取消/, {}, { timeout: 3_000 })).toBeVisible();
    expect(screen.queryByText(/顧問處理中，JD 暫時唯讀/)).not.toBeInTheDocument();
    expect(screen.getByRole('button', { name: '修改職務名稱' })).toHaveAttribute(
      'aria-disabled',
      'false',
    );
    expect(screen.getByRole('button', { name: '新增職責' })).toHaveAttribute(
      'aria-disabled',
      'false',
    );
    expect(screen.getByText('已取消')).toBeVisible();
  },
);

test('a paused Turn keeps the JD read-only and says why', async () => {
  retainTurnHint(file.job_file_id, {
    command_id: '60000000-0000-4000-8000-000000000006',
    execution_id: executionId,
  });
  vi.stubGlobal(
    'fetch',
    vi.fn((path: string) => {
      if (path.endsWith('/jd/work')) return Promise.resolve(Response.json(work));
      if (path.endsWith('/jd/profile')) return Promise.resolve(Response.json(profile));
      if (path.includes('/consultant-turns/'))
        return Promise.resolve(Response.json(turnBody('paused')));
      if (path.endsWith('/interviews')) return Promise.resolve(Response.json({ messages: [] }));
      return Promise.resolve(Response.json(file));
    }),
  );
  renderJobFile();
  expect(await screen.findByText(/這輪處理已暫停，JD 仍為唯讀/)).toBeVisible();
  expect(screen.getByText('已暫停')).toBeVisible();
});

test('narrow-screen tabs switch panes without unmounting either one', async () => {
  vi.stubGlobal(
    'fetch',
    vi.fn((path: string) => {
      if (path.endsWith('/consultant-turns/current'))
        return Promise.resolve(Response.json({ turn: null }));
      if (path.endsWith('/jd/work')) return Promise.resolve(Response.json(work));
      if (path.endsWith('/jd/profile')) return Promise.resolve(Response.json(profile));
      if (path.endsWith('/interviews')) return Promise.resolve(Response.json({ messages: [] }));
      return Promise.resolve(Response.json(file));
    }),
  );
  const view = renderJobFile();
  const interviewTab = await screen.findByRole('tab', { name: '訪談' });
  const jdTab = screen.getByRole('tab', { name: 'JD' });
  const workspace = view.container.querySelector('.workspace');
  expect(interviewTab).toHaveAttribute('aria-selected', 'true');
  expect(workspace).toHaveAttribute('data-active-pane', 'interview');

  await userEvent.type(await screen.findByRole('textbox', { name: '訪談內容' }), '尚未送出');
  await userEvent.click(jdTab);
  expect(jdTab).toHaveAttribute('aria-selected', 'true');
  expect(workspace).toHaveAttribute('data-active-pane', 'jd');
  // Switching is presentation only: the unsent draft is still mounted and intact.
  expect(screen.getByRole('textbox', { name: '訪談內容' })).toHaveValue('尚未送出');
  await userEvent.click(interviewTab);
  expect(workspace).toHaveAttribute('data-active-pane', 'interview');
});

test('unknown discovery keeps the formal JD readable but not editable until a successful check', async () => {
  let discoveryFailed = true;
  vi.stubGlobal(
    'fetch',
    vi.fn((path: string) => {
      if (path.endsWith('/consultant-turns/current'))
        return Promise.resolve(
          discoveryFailed ? new Response(null, { status: 503 }) : Response.json({ turn: null }),
        );
      if (path.endsWith('/jd/work')) return Promise.resolve(Response.json(work));
      if (path.endsWith('/jd/profile')) return Promise.resolve(Response.json(profile));
      if (path.endsWith('/interviews')) return Promise.resolve(Response.json({ messages: [] }));
      return Promise.resolve(Response.json(file));
    }),
  );
  renderJobFile();
  expect(await screen.findByText('原正式工程師')).toBeVisible();
  expect(screen.getByRole('button', { name: '修改職務名稱' })).toHaveAttribute(
    'aria-disabled',
    'true',
  );
  const retry = await screen.findByRole('button', { name: '重新查詢進行中處理' });
  expect(screen.getByText(/尚未確認顧問處理狀態/)).toBeVisible();
  discoveryFailed = false;
  await userEvent.click(retry);
  await waitFor(() =>
    expect(screen.getByRole('button', { name: '修改職務名稱' })).toHaveAttribute(
      'aria-disabled',
      'false',
    ),
  );
});

/** A workspace whose Turn-status check can be switched to "unknown" (503) and back. */
function stubUnknownStatusSwitch() {
  const state = { unavailable: false };
  const fetch = vi.fn<typeof globalThis.fetch>((input) => {
    const path = typeof input === 'string' ? input : input instanceof URL ? input.href : input.url;
    if (path.endsWith('/consultant-turns/current'))
      return Promise.resolve(
        state.unavailable ? new Response(null, { status: 503 }) : Response.json({ turn: null }),
      );
    if (path.endsWith('/jd/work')) return Promise.resolve(Response.json(work));
    if (path.endsWith('/jd/profile')) return Promise.resolve(Response.json(profile));
    if (path.endsWith('/interviews')) return Promise.resolve(Response.json({ messages: [] }));
    return Promise.resolve(Response.json(file));
  });
  vi.stubGlobal('fetch', fetch);
  return { fetch, state };
}

test('an open basic-data draft cannot be saved while Turn status is unknown, and survives it', async () => {
  const { fetch, state } = stubUnknownStatusSwitch();
  const { client } = renderJobFile();
  const open = await screen.findByRole('button', { name: '修改職務名稱' });
  await waitFor(() => expect(open).toHaveAttribute('aria-disabled', 'false'));
  await userEvent.click(open);
  const input = await screen.findByRole('textbox', { name: '職務名稱' });
  await userEvent.clear(input);
  await userEvent.type(input, '保留的人工草稿');
  state.unavailable = true;
  await act(() =>
    client.invalidateQueries({ queryKey: ['current-consultant-turn', file.job_file_id] }),
  );
  const submit = screen.getByRole('button', { name: '儲存' });
  await waitFor(() => expect(submit).toBeDisabled());
  expect(screen.queryByRole('button', { name: '讀取目前 JD' })).not.toBeInTheDocument();
  const form = input.closest('form');
  if (!form) throw new Error('expected the open draft form');
  fireEvent.submit(form);
  expect(fetch.mock.calls.some(([, options]) => options?.method === 'POST')).toBe(false);
  expect(input).toHaveValue('保留的人工草稿');
  state.unavailable = false;
  await act(() =>
    client.invalidateQueries({ queryKey: ['current-consultant-turn', file.job_file_id] }),
  );
  await waitFor(() => expect(submit).toBeEnabled());
  expect(input).toHaveValue('保留的人工草稿');
});

test('an open new-area field cannot be saved while Turn status is unknown, and survives it', async () => {
  const { fetch, state } = stubUnknownStatusSwitch();
  const { client } = renderJobFile();
  const add = await screen.findByRole('button', { name: '新增職責' });
  await waitFor(() => expect(add).toHaveAttribute('aria-disabled', 'false'));
  await userEvent.click(add);
  const input = await screen.findByRole('textbox', { name: '職責名稱' });
  await userEvent.type(input, '保留的人工草稿');
  state.unavailable = true;
  await act(() =>
    client.invalidateQueries({ queryKey: ['current-consultant-turn', file.job_file_id] }),
  );
  const submit = screen.getByRole('button', { name: '儲存' });
  await waitFor(() => expect(submit).toBeDisabled());
  expect(screen.queryByRole('button', { name: '讀取目前 JD' })).not.toBeInTheDocument();
  const form = input.closest('form');
  if (!form) throw new Error('expected the open draft form');
  fireEvent.submit(form);
  expect(fetch.mock.calls.some(([, options]) => options?.method === 'POST')).toBe(false);
  expect(input).toHaveValue('保留的人工草稿');
  state.unavailable = false;
  await act(() =>
    client.invalidateQueries({ queryKey: ['current-consultant-turn', file.job_file_id] }),
  );
  await waitFor(() => expect(submit).toBeEnabled());
  expect(input).toHaveValue('保留的人工草稿');
});
