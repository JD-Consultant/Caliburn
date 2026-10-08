import { onlineManager, QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, beforeEach, expect, test, vi } from 'vitest';
import { InterviewComposer } from './InterviewComposer';
import { readTurnHint, retainTurnHint } from './interview-turn-api';

const fileId = '10000000-0000-4000-8000-000000000001';
const executionId = '20000000-0000-4000-8000-000000000002';
const commandId = '30000000-0000-4000-8000-000000000003';
const path = `/api/job-files/${fileId}/consultant-turns/${executionId}`;
const active = {
  job_file_id: fileId,
  execution_id: executionId,
  status: 'active',
  pause_requested: false,
  input_text: '本輪尚未正式保存的原話',
  allowed_controls: ['pause', 'cancel'],
  commentary: [],
  plan_preview: null,
  candidate: null,
};
const clients: QueryClient[] = [];

function renderComposer() {
  const commandFetch = globalThis.fetch;
  vi.stubGlobal('fetch', (url: RequestInfo | URL, options?: RequestInit) =>
    url === `/api/job-files/${fileId}/consultant-turns/current`
      ? Promise.resolve(Response.json({ turn: null }))
      : commandFetch(url, options),
  );
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  clients.push(client);
  return {
    client,
    ...render(
      <QueryClientProvider client={client}>
        <InterviewComposer jobFileId={fileId} />
      </QueryClientProvider>,
    ),
  };
}

beforeEach(() => {
  localStorage.clear();
  retainTurnHint(fileId, { command_id: commandId, execution_id: executionId });
});
afterEach(() => {
  clients.splice(0).forEach((client) => client.clear());
  onlineManager.setOnline(true);
  vi.unstubAllGlobals();
});

test('pause intent waits for a safe point; resume keeps the same turn and original input', async () => {
  let current = active;
  const posts: string[] = [];
  vi.stubGlobal(
    'fetch',
    vi.fn((url: string, options?: RequestInit) => {
      if (options?.method === 'POST') {
        posts.push(url);
        current = url.endsWith('/pause')
          ? { ...active, pause_requested: true, allowed_controls: ['cancel'] }
          : active;
      }
      return Promise.resolve(Response.json(current));
    }),
  );
  const first = renderComposer();
  await userEvent.click(await screen.findByRole('button', { name: '暫停處理' }));
  expect(await screen.findByText(/等待安全點/)).toBeVisible();
  expect(
    screen.queryByText('這次處理已暫停，原輸入仍保留，尚未正式完成。'),
  ).not.toBeInTheDocument();
  expect(screen.queryByRole('button', { name: '繼續處理' })).not.toBeInTheDocument();
  expect(screen.queryByRole('button', { name: '暫停處理' })).not.toBeInTheDocument();
  first.unmount();
  const { client } = renderComposer();
  expect(await screen.findByText(/等待安全點/)).toBeVisible();
  current = {
    ...active,
    status: 'paused',
    pause_requested: true,
    allowed_controls: ['resume', 'cancel'],
  };
  await client.invalidateQueries({ queryKey: ['consultant-turn', fileId, executionId] });
  const resume = await screen.findByRole('button', { name: '繼續處理' });
  resume.focus();
  await userEvent.keyboard('{Enter}');
  expect(await screen.findByRole('button', { name: '暫停處理' })).toBeVisible();
  expect(posts).toEqual([`${path}/pause`, `${path}/resume`]);
  expect(readTurnHint(fileId)).toEqual({ command_id: commandId, execution_id: executionId });
  expect(screen.getByText(active.input_text)).toBeVisible();
});

test('lost cancel acknowledgement reads the same turn; retrying original words is a new input', async () => {
  let cancelled = false;
  const controls: string[] = [];
  const inputs: { command_id: string; text: string }[] = [];
  vi.stubGlobal(
    'fetch',
    vi.fn((url: string, options?: RequestInit) => {
      if (options?.method === 'POST') {
        if (url.endsWith('/cancel')) {
          controls.push(url);
          cancelled = true;
          return Promise.reject(new TypeError('lost acknowledgement'));
        }
        const command = {
          command_id: readTurnHint(fileId)?.command_id ?? '',
          text: active.input_text,
        };
        expect(options.body).toBe(JSON.stringify(command));
        inputs.push(command);
        return Promise.resolve(
          Response.json({
            job_file_id: fileId,
            command_id: command.command_id,
            execution_id: '40000000-0000-4000-8000-000000000004',
            source_id: '50000000-0000-4000-8000-000000000005',
          }),
        );
      }
      return Promise.resolve(
        Response.json(
          cancelled ? { ...active, status: 'cancelled', allowed_controls: [] } : active,
        ),
      );
    }),
  );
  renderComposer();
  await userEvent.click(await screen.findByRole('button', { name: '取消處理' }));
  expect(await screen.findByText(/這次處理已取消/)).toBeVisible();
  expect(screen.queryByRole('button', { name: '繼續處理' })).not.toBeInTheDocument();
  expect(inputs).toHaveLength(0);
  expect(controls).toEqual([`${path}/cancel`]);
  await userEvent.click(screen.getByRole('button', { name: '取回原文編輯' }));
  expect(screen.getByLabelText('訪談內容')).toHaveValue(active.input_text);
  await userEvent.click(screen.getByRole('button', { name: '送出訪談' }));
  await waitFor(() => expect(inputs).toHaveLength(1));
  expect(inputs[0]?.command_id).not.toBe(commandId);
  expect(inputs[0]?.text).toBe(active.input_text);
});

test('an uncertain pause never claims paused or automatically repeats a command', async () => {
  const posts: string[] = [];
  vi.stubGlobal(
    'fetch',
    vi.fn((url: string, options?: RequestInit) => {
      if (options?.method === 'POST') {
        posts.push(url);
        return Promise.reject(new TypeError('offline'));
      }
      return Promise.resolve(Response.json(active));
    }),
  );
  renderComposer();
  const pause = await screen.findByRole('button', { name: '暫停處理' });
  onlineManager.setOnline(false);
  await userEvent.click(pause);
  expect(await screen.findByText(/控制結果尚未確認/)).toBeVisible();
  expect(screen.getByText('顧問正在處理，尚未正式完成。')).toBeVisible();
  expect(screen.queryByRole('button', { name: '繼續處理' })).not.toBeInTheDocument();
  expect(posts).toEqual([`${path}/pause`]);
  expect(readTurnHint(fileId)?.execution_id).toBe(executionId);
});
