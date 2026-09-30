/** Recover a server-owned Turn without fabricating or re-sending its input command. */
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { act, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, beforeEach, expect, test, vi } from 'vitest';
import { InterviewComposer } from './InterviewComposer';
import { readTurnHint, retainTurnHint } from './interview-turn-api';
import { useCurrentTurn } from './use-current-turn';

const fileId = '10000000-0000-4000-8000-000000000001';
const executionId = '20000000-0000-4000-8000-000000000002';
const commandId = '30000000-0000-4000-8000-000000000003';
const baseUrl = `/api/job-files/${fileId}/consultant-turns`;
const active = {
  job_file_id: fileId,
  execution_id: executionId,
  status: 'active',
  pause_requested: false,
  input_text: '已受理的合成訪談',
  allowed_controls: ['pause', 'cancel'],
  commentary: [],
  candidate: null,
};
const clients: QueryClient[] = [];

function PageObserver() {
  const current = useCurrentTurn(fileId);
  return (
    <output aria-label="頁面處理狀態">
      {current.turn?.status ?? (current.isVerified ? 'idle' : 'unknown')}
    </output>
  );
}

function openComposer() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  clients.push(client);
  return {
    client,
    ...render(
      <QueryClientProvider client={client}>
        <PageObserver />
        <InterviewComposer jobFileId={fileId} />
      </QueryClientProvider>,
    ),
  };
}

beforeEach(() => localStorage.clear());
afterEach(() => {
  clients.splice(0).forEach((client) => client.clear());
  vi.unstubAllGlobals();
});

test.each(['active', 'paused'] as const)(
  'finds %s work without a local hint, then follows its original execution',
  async (status) => {
    const turn = {
      ...active,
      status,
      allowed_controls: status === 'paused' ? ['resume', 'cancel'] : ['pause', 'cancel'],
    };
    const fetch = vi.fn((path: string) =>
      Promise.resolve(Response.json(path === `${baseUrl}/current` ? { turn } : turn)),
    );
    vi.stubGlobal('fetch', fetch);
    openComposer();
    expect(await screen.findByText(active.input_text)).toBeVisible();
    expect(
      screen.getByRole('button', { name: status === 'paused' ? '繼續處理' : '暫停處理' }),
    ).toBeVisible();
    await waitFor(() => expect(screen.getByLabelText('頁面處理狀態')).toHaveTextContent(status));
    expect(screen.queryByLabelText('訪談內容')).not.toBeInTheDocument();
    expect(fetch.mock.calls.map(([path]) => path)).toEqual([
      `${baseUrl}/current`,
      `${baseUrl}/${executionId}`,
    ]);
    expect(readTurnHint(fileId)).toBeNull();
  },
);

test('holds submission while discovery is unresolved, without discarding the draft', async () => {
  let finish: (response: Response) => void = () => {
    throw new Error('request not started');
  };
  vi.stubGlobal(
    'fetch',
    vi.fn(
      () =>
        new Promise<Response>((resolve) => {
          finish = resolve;
        }),
    ),
  );
  openComposer();
  await userEvent.type(screen.getByLabelText('訪談內容'), '還没送出的草稿');
  expect(screen.getByRole('button', { name: '送出訪談' })).toBeDisabled();
  expect(screen.getByLabelText('頁面處理狀態')).toHaveTextContent('unknown');
  act(() => finish(Response.json({ turn: null })));
  await waitFor(() => expect(screen.getByRole('button', { name: '送出訪談' })).toBeEnabled());
  expect(screen.getByLabelText('訪談內容')).toHaveValue('還没送出的草稿');
  expect(screen.getByLabelText('頁面處理狀態')).toHaveTextContent('idle');
});

test('failed discovery is not idle; explicit read-only retry can recover', async () => {
  const fetch = vi
    .fn<typeof globalThis.fetch>()
    .mockResolvedValueOnce(new Response(null, { status: 503 }))
    .mockImplementation(() => Promise.resolve(Response.json({ turn: null })));
  vi.stubGlobal('fetch', fetch);
  openComposer();
  await userEvent.click(await screen.findByRole('button', { name: '重新查詢進行中處理' }));
  await waitFor(() => expect(screen.getByRole('button', { name: '送出訪談' })).toBeEnabled());
  expect(fetch.mock.calls.every(([, options]) => !options?.method)).toBe(true);
});

test('a retained unknown command is resolved only by command, never erased by current=null', async () => {
  retainTurnHint(fileId, { command_id: commandId, execution_id: null });
  const fetch = vi.fn((path: string) =>
    Promise.resolve(
      path === `${baseUrl}/current`
        ? Response.json({ turn: null })
        : Response.json({ detail: { code: 'consultant_turn_not_found' } }, { status: 404 }),
    ),
  );
  vi.stubGlobal('fetch', fetch);
  openComposer();
  expect(await screen.findByText(/尚未查到原請求的受理結果/)).toBeVisible();
  expect(readTurnHint(fileId)).toEqual({ command_id: commandId, execution_id: null });
  expect(fetch.mock.calls.map(([path]) => path)).toEqual([`${baseUrl}/by-command/${commandId}`]);
  expect(screen.queryByRole('button', { name: '送出訪談' })).not.toBeInTheDocument();
  expect(screen.getByLabelText('頁面處理狀態')).toHaveTextContent('unknown');
});

test('follows another tab replacing a finished Turn hint without a second query owner', async () => {
  retainTurnHint(fileId, { command_id: commandId, execution_id: executionId });
  const nextId = '40000000-0000-4000-8000-000000000004';
  const fetch = vi.fn((path: string) =>
    Promise.resolve(
      Response.json(
        path.endsWith(nextId)
          ? { ...active, execution_id: nextId, input_text: '另一分頁的新輸入' }
          : { ...active, status: 'cancelled', allowed_controls: [] },
      ),
    ),
  );
  vi.stubGlobal('fetch', fetch);
  openComposer();
  expect(await screen.findByText(/這次處理已取消/)).toBeVisible();
  act(() => {
    localStorage.setItem(
      `caliburn:interview-turn:${fileId}`,
      JSON.stringify({
        command_id: '50000000-0000-4000-8000-000000000005',
        execution_id: nextId,
      }),
    );
    window.dispatchEvent(new StorageEvent('storage'));
  });
  expect(await screen.findByText('另一分頁的新輸入')).toBeVisible();
  expect(screen.getByLabelText('頁面處理狀態')).toHaveTextContent('active');
  expect(fetch.mock.calls.map(([path]) => path)).toEqual([
    `${baseUrl}/${executionId}`,
    `${baseUrl}/${nextId}`,
  ]);
});

test('discovered work can finish, retain its terminal result, then start a fresh input', async () => {
  let turn = active;
  const fetch = vi.fn((path: string) =>
    Promise.resolve(
      Response.json(
        path === `${baseUrl}/current` ? { turn: turn.status === 'active' ? active : null } : turn,
      ),
    ),
  );
  vi.stubGlobal('fetch', fetch);
  const { client } = openComposer();
  expect(await screen.findByText(active.input_text)).toBeVisible();
  turn = { ...active, status: 'cancelled', allowed_controls: [] };
  await act(async () => {
    await client.invalidateQueries({ queryKey: ['consultant-turn', fileId, executionId] });
  });
  expect(await screen.findByText(/這次處理已取消/)).toBeVisible();
  await userEvent.click(screen.getByRole('button', { name: '取回原文編輯' }));
  await waitFor(() => expect(screen.getByRole('button', { name: '送出訪談' })).toBeEnabled());
  expect(screen.getByLabelText('訪談內容')).toHaveValue(active.input_text);
  expect(readTurnHint(fileId)).toBeNull();
  expect(
    fetch.mock.calls.map(([path]) => path).filter((path) => path === `${baseUrl}/current`),
  ).toHaveLength(2);
});

test('discovery rejects another file and does not expose its input', async () => {
  vi.stubGlobal(
    'fetch',
    vi.fn(() => Promise.resolve(Response.json({ turn: { ...active, job_file_id: commandId } }))),
  );
  openComposer();
  expect(await screen.findByText(/處理狀態不屬於這份職務檔案/)).toBeVisible();
  expect(screen.queryByText(active.input_text)).not.toBeInTheDocument();
  expect(screen.getByRole('button', { name: '送出訪談' })).toBeDisabled();
});
