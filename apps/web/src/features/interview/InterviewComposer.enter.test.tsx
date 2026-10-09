import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, beforeEach, expect, test, vi } from 'vitest';
import { InterviewComposer } from './InterviewComposer';
import { readTurnHint, retainTurnHint } from './interview-turn-api';
import type { ConsultantTurn } from '../../shared/api/generated/consultant-turn';

const fileId = '10000000-0000-4000-8000-000000000001';
const executionId = '20000000-0000-4000-8000-000000000002';
const nextExecutionId = '20000000-0000-4000-8000-000000000003';
const commandId = '30000000-0000-4000-8000-000000000003';
const sourceId = '40000000-0000-4000-8000-000000000004';
const clients: QueryClient[] = [];

interface Posted {
  command_id: string;
  text: string;
}

/**
 * A backend with no current turn that accepts every input. The earlier execution is already
 * completed and the one an input starts is active; `discoveryNeverAnswers` keeps the send button
 * unavailable while the text box stays editable.
 */
function stubBackend(options: { discoveryNeverAnswers?: boolean } = {}): Posted[] {
  const posts: Posted[] = [];
  vi.stubGlobal('fetch', (path: string, init?: RequestInit) => {
    if (init?.method === 'POST') {
      if (typeof init.body !== 'string') throw new Error('Expected a JSON request body');
      const command = JSON.parse(init.body) as Posted;
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
      return options.discoveryNeverAnswers
        ? new Promise<Response>(() => undefined)
        : Promise.resolve(Response.json({ turn: null }));
    }
    const turn: ConsultantTurn = {
      job_file_id: fileId,
      execution_id: path.endsWith(nextExecutionId) ? nextExecutionId : executionId,
      status: path.endsWith(nextExecutionId) ? 'active' : 'completed',
      pause_requested: false,
      input_text: '上一輪的原話',
      allowed_controls: [],
      commentary: [],
      plan_preview: null,
      candidate: null,
    };
    return Promise.resolve(Response.json(turn));
  });
  return posts;
}

function openComposer(): void {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  clients.push(client);
  render(
    <QueryClientProvider client={client}>
      <InterviewComposer refreshCompletedTurn={async () => {}} jobFileId={fileId} />
    </QueryClientProvider>,
  );
}

const sendButton = () => screen.getByRole('button', { name: '送出訪談' });

/** Types a draft and waits until the composer has finished looking for work, so Enter can send. */
async function typeDraft(text: string): Promise<HTMLElement> {
  const input = screen.getByRole('textbox', { name: '訪談內容' });
  await userEvent.type(input, text);
  await waitFor(() => expect(sendButton()).toBeEnabled());
  return input;
}

/** Lets every request and state update already started run, so "nothing happened" can be asserted. */
async function settle(): Promise<void> {
  await act(async () => {
    await new Promise((resolve) => setTimeout(resolve, 0));
  });
}

beforeEach(() => localStorage.clear());
afterEach(() => {
  clients.splice(0).forEach((client) => client.clear());
  vi.unstubAllGlobals();
});

test('Enter sends the draft like the send button does: one command, the exact text, no line break', async () => {
  const posts = stubBackend();
  openComposer();
  await typeDraft('每天先看工單');
  await userEvent.keyboard('{Enter}');
  await waitFor(() => expect(posts).toHaveLength(1));
  expect(posts[0]?.text).toBe('每天先看工單');
  await waitFor(() => expect(readTurnHint(fileId)?.execution_id).toBe(nextExecutionId));
});

test('Shift+Enter adds a line break and sends nothing', async () => {
  const posts = stubBackend();
  openComposer();
  const input = await typeDraft('第一段');
  await userEvent.keyboard('{Shift>}{Enter}{/Shift}第二段');
  await settle();
  expect(input).toHaveValue('第一段\n第二段');
  expect(readTurnHint(fileId)).toBeNull();
  expect(posts).toHaveLength(0);
});

test.each([
  { signal: 'the browser flags the key as part of a composition', init: { isComposing: true } },
  { signal: 'Safari ends the composition first and only keyCode says 229', init: { keyCode: 229 } },
])('the Enter that confirms an input-method choice is not a send: $signal', async ({ init }) => {
  const posts = stubBackend();
  openComposer();
  const input = await typeDraft('每天處理');
  fireEvent.keyDown(input, { key: 'Enter', ...init });
  await settle();
  expect(readTurnHint(fileId)).toBeNull();
  expect(posts).toHaveLength(0);
  expect(input).toBeEnabled();
  expect(input).toHaveValue('每天處理');
});

test('Enter does nothing while the send button is unavailable, and adds no line break either', async () => {
  const posts = stubBackend({ discoveryNeverAnswers: true });
  openComposer();
  const input = screen.getByRole('textbox', { name: '訪談內容' });
  await userEvent.type(input, '先打好草稿{Enter}');
  await settle();
  expect(sendButton()).toBeDisabled();
  expect(input).toHaveValue('先打好草稿');
  expect(readTurnHint(fileId)).toBeNull();
  expect(posts).toHaveLength(0);
});

test('Enter on an empty draft asks for content exactly as the send button does', async () => {
  const posts = stubBackend();
  openComposer();
  const input = await typeDraft('   ');
  await userEvent.keyboard('{Enter}');
  expect(await screen.findByText('請填寫訪談內容，不能只有空白或包含無效字元。')).toBeVisible();
  expect(input).toHaveValue('   ');
  expect(readTurnHint(fileId)).toBeNull();
  expect(posts).toHaveLength(0);
});

test('Enter also sends the next answer after a completed turn, as a fresh command', async () => {
  await retainTurnHint(fileId, { command_id: commandId, execution_id: executionId });
  const posts = stubBackend();
  openComposer();
  await screen.findByText('這次訪談已完成並保存。');
  await typeDraft('補充本月盤點');
  await userEvent.keyboard('{Enter}');
  await waitFor(() => expect(posts).toHaveLength(1));
  expect(posts[0]?.text).toBe('補充本月盤點');
  expect(posts[0]?.command_id).not.toBe(commandId);
});
