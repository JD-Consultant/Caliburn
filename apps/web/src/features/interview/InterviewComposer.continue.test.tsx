import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { act, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, beforeEach, expect, test, vi } from 'vitest';
import { InterviewComposer } from './InterviewComposer';
import { InterviewHistory } from './InterviewHistory';
import { consultantTurnQuery, readTurnHint, retainTurnHint } from './interview-turn-api';
import { interviewHistoryQuery } from './interview-api';
import type { ConsultantTurn } from '../../shared/api/generated/consultant-turn';

const fileId = '10000000-0000-4000-8000-000000000001';
const executionId = '20000000-0000-4000-8000-000000000002';
const nextExecutionId = '20000000-0000-4000-8000-000000000003';
const commandId = '30000000-0000-4000-8000-000000000003';
const sourceId = '40000000-0000-4000-8000-000000000004';
const completed: ConsultantTurn = {
  job_file_id: fileId,
  execution_id: executionId,
  status: 'completed',
  pause_requested: false,
  input_text: '上一輪的原話',
  allowed_controls: [],
  commentary: [],
  candidate: null,
};
const clients: QueryClient[] = [];

function openComposer(withHistory = false) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  clients.push(client);
  render(
    <QueryClientProvider client={client}>
      {withHistory && <InterviewHistory jobFileId={fileId} />}
      <InterviewComposer jobFileId={fileId} />
    </QueryClientProvider>,
  );
  return client;
}

beforeEach(() => localStorage.clear());
afterEach(() => {
  clients.splice(0).forEach((client) => client.clear());
  vi.unstubAllGlobals();
});

test.each(['retained', 'discovered'] as const)(
  '%s completed turn accepts the next answer directly with a fresh command',
  async (entry) => {
    const posts: { command_id: string; text: string }[] = [];
    if (entry === 'retained') {
      retainTurnHint(fileId, { command_id: commandId, execution_id: executionId });
    }
    const active = { ...completed, status: 'active', allowed_controls: ['pause', 'cancel'] };
    vi.stubGlobal('fetch', (path: string, options?: RequestInit) => {
      if (options?.method === 'POST') {
        if (typeof options.body !== 'string') throw new Error('Expected a JSON request body');
        const command = JSON.parse(options.body) as { command_id: string; text: string };
        posts.push(command);
        return Promise.resolve(
          Response.json({
            job_file_id: fileId,
            command_id: command.command_id,
            execution_id: nextExecutionId,
            source_id: sourceId,
          }),
        );
      }
      if (path.endsWith('/reasoning-summaries')) return Promise.resolve(Response.json([]));
      if (path.endsWith('/current')) {
        return Promise.resolve(
          Response.json({
            turn: entry === 'discovered' && posts.length === 0 ? active : null,
          }),
        );
      }
      return Promise.resolve(
        Response.json(
          path.endsWith(nextExecutionId)
            ? { ...completed, execution_id: nextExecutionId, input_text: posts[0]?.text ?? '' }
            : completed,
        ),
      );
    });
    openComposer();
    await screen.findByText('這次訪談已完成並保存。');
    const input = screen.getByRole('textbox', { name: '訪談內容' });
    expect(input).toBeEnabled();
    expect(input).toHaveValue('');
    expect(screen.queryByRole('button', { name: '開始下一次訪談' })).not.toBeInTheDocument();
    expect(posts).toHaveLength(0);
    await userEvent.type(input, '補充本月盤點的內容');
    await userEvent.click(screen.getByRole('button', { name: '送出訪談' }));
    await waitFor(() => expect(posts).toHaveLength(1));
    expect(posts[0]?.text).toBe('補充本月盤點的內容');
    expect(posts[0]?.command_id).not.toBe(commandId);
    await waitFor(() => expect(screen.getByRole('textbox', { name: '訪談內容' })).toHaveValue(''));
    expect(readTurnHint(fileId)?.execution_id).toBe(nextExecutionId);
  },
);

test('a next-answer draft survives a completed-status refetch without being resent', async () => {
  retainTurnHint(fileId, { command_id: commandId, execution_id: executionId });
  const requests: string[] = [];
  vi.stubGlobal('fetch', (path: string, options?: RequestInit) => {
    requests.push(options?.method ?? 'GET');
    return Promise.resolve(Response.json(path.endsWith('/reasoning-summaries') ? [] : completed));
  });
  const client = openComposer();
  await screen.findByText('這次訪談已完成並保存。');
  await userEvent.type(screen.getByRole('textbox', { name: '訪談內容' }), '尚未送出的下一題');
  await act(async () => {
    await client.invalidateQueries({ queryKey: consultantTurnQuery(fileId, executionId).queryKey });
  });
  expect(screen.getByRole('textbox', { name: '訪談內容' })).toHaveValue('尚未送出的下一題');
  expect(requests).not.toContain('POST');
});

test('completed turns leave no footer process links even before their formal reply loads', async () => {
  retainTurnHint(fileId, { command_id: commandId, execution_id: executionId });
  const reads: string[] = [];
  vi.stubGlobal('fetch', (path: string) => {
    reads.push(path);
    return Promise.resolve(Response.json(path.endsWith('/reasoning-summaries') ? [] : completed));
  });
  const client = openComposer();
  await screen.findByText('這次訪談已完成並保存。');
  expect(screen.queryByText('推理摘要')).not.toBeInTheDocument();
  expect(screen.queryByText('回看本次處理過程')).not.toBeInTheDocument();
  expect(reads.some((path) => path.endsWith('/reasoning-summaries'))).toBe(false);
  const reply = {
    source_id: sourceId,
    interview_sequence: 3,
    speaker: 'consultant' as const,
    interview_text: '已保存的正式回覆',
    execution_id: nextExecutionId,
  };
  act(() => {
    client.setQueryData(interviewHistoryQuery(fileId).queryKey, { messages: [reply] });
  });
  expect(screen.queryByText('推理摘要')).not.toBeInTheDocument();
  act(() => {
    client.setQueryData(interviewHistoryQuery(fileId).queryKey, {
      messages: [{ ...reply, execution_id: executionId }],
    });
  });
  await waitFor(() => expect(screen.queryByText('推理摘要')).not.toBeInTheDocument());
  expect(screen.getByRole('textbox', { name: '訪談內容' })).toBeEnabled();
});

test('completion confirmed by another page retires an uncertain command before the next answer', async () => {
  const posts: { command_id: string; text: string }[] = [];
  vi.stubGlobal('fetch', (path: string, options?: RequestInit) => {
    if (options?.method === 'POST') {
      if (typeof options.body !== 'string') throw new Error('Expected a JSON request body');
      const command = JSON.parse(options.body) as { command_id: string; text: string };
      posts.push(command);
      if (posts.length === 1) return Promise.reject(new TypeError('lost acknowledgement'));
      return Promise.resolve(
        Response.json({
          job_file_id: fileId,
          command_id: command.command_id,
          execution_id: nextExecutionId,
          source_id: sourceId,
        }),
      );
    }
    if (path.endsWith('/current')) return Promise.resolve(Response.json({ turn: null }));
    if (path.endsWith('/reasoning-summaries')) return Promise.resolve(Response.json([]));
    return Promise.resolve(
      Response.json(
        path.endsWith(nextExecutionId)
          ? { ...completed, execution_id: nextExecutionId, input_text: posts[1]?.text ?? '' }
          : completed,
      ),
    );
  });
  openComposer();
  await waitFor(() => expect(screen.getByRole('button', { name: '送出訪談' })).toBeEnabled());
  await userEvent.type(screen.getByRole('textbox', { name: '訪談內容' }), '第一次回答');
  await userEvent.click(screen.getByRole('button', { name: '送出訪談' }));
  await screen.findByText(/送出結果尚未確認/);
  const originalHint = readTurnHint(fileId);
  if (!originalHint) throw new Error('Expected an uncertain command hint');
  act(() => retainTurnHint(fileId, { ...originalHint, execution_id: executionId }));
  await screen.findByText('這次訪談已完成並保存。');
  expect(screen.getByRole('textbox', { name: '訪談內容' })).toHaveValue('');
  expect(screen.queryByText(/送出結果尚未確認/)).not.toBeInTheDocument();
  await userEvent.type(screen.getByRole('textbox', { name: '訪談內容' }), '下一次回答');
  await userEvent.click(screen.getByRole('button', { name: '送出訪談' }));
  await waitFor(() => expect(posts).toHaveLength(2));
  expect(posts[1]?.command_id).not.toBe(posts[0]?.command_id);
  expect(posts[1]?.text).toBe('下一次回答');
});

test('history retry restores the completed reply and its process after the next answer starts', async () => {
  retainTurnHint(fileId, { command_id: commandId, execution_id: executionId });
  let historyAvailable = false;
  let posts = 0;
  const previous = {
    ...completed,
    commentary: [{ response_id: 'response-1', message_id: 'message-1', text: '已核對上一輪職責' }],
  };
  vi.stubGlobal('fetch', (path: string, options?: RequestInit) => {
    if (options?.method === 'POST') {
      if (typeof options.body !== 'string') throw new Error('Expected a JSON request body');
      const command = JSON.parse(options.body) as { command_id: string };
      posts += 1;
      return Promise.resolve(
        Response.json({
          job_file_id: fileId,
          command_id: command.command_id,
          execution_id: nextExecutionId,
          source_id: sourceId,
        }),
      );
    }
    if (path.endsWith('/interviews')) {
      if (!historyAvailable) return Promise.reject(new TypeError('history unavailable'));
      return Promise.resolve(
        Response.json({
          messages: [
            {
              source_id: sourceId,
              interview_sequence: 3,
              speaker: 'consultant',
              interview_text: '上一輪正式回答',
              execution_id: executionId,
            },
          ],
        }),
      );
    }
    if (path.endsWith('/current')) return Promise.resolve(Response.json({ turn: null }));
    if (path.endsWith('/reasoning-summaries')) return Promise.resolve(Response.json([]));
    return Promise.resolve(
      Response.json(
        path.endsWith(nextExecutionId)
          ? {
              ...completed,
              execution_id: nextExecutionId,
              status: 'active',
              input_text: '下一則回答',
            }
          : previous,
      ),
    );
  });
  openComposer(true);
  await screen.findByText('這次訪談已完成並保存。');
  await screen.findByRole('button', { name: '重新讀取' });
  expect(screen.queryByText('回看本次處理過程')).not.toBeInTheDocument();
  await userEvent.type(screen.getByRole('textbox', { name: '訪談內容' }), '下一則回答');
  await userEvent.click(screen.getByRole('button', { name: '送出訪談' }));
  await screen.findByText('顧問正在處理，尚未正式完成。');
  expect(posts).toBe(1);
  historyAvailable = true;
  await userEvent.click(screen.getByRole('button', { name: '重新讀取' }));
  await screen.findByText('上一輪正式回答');
  await userEvent.click(screen.getByRole('button', { name: '處理紀錄' }));
  await userEvent.click(await screen.findByText('處理過程', { selector: 'summary' }));
  expect(await screen.findByText('已核對上一輪職責')).toBeVisible();
  expect(posts).toBe(1);
});
