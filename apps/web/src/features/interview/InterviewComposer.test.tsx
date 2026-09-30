import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, beforeEach, expect, test, vi } from 'vitest';
import { InterviewComposer } from './InterviewComposer';
import { readTurnHint, retainTurnHint } from './interview-turn-api';

const fileId = '10000000-0000-4000-8000-000000000001';
const executionId = '20000000-0000-4000-8000-000000000002';
const commandId = '30000000-0000-4000-8000-000000000003';
const sourceId = '40000000-0000-4000-8000-000000000004';
const input = '原始訪談內容不應存進瀏覽器';
const active = {
  job_file_id: fileId,
  execution_id: executionId,
  status: 'active',
  pause_requested: false,
  input_text: input,
  allowed_controls: [],
  commentary: [],
  candidate: null,
};
const clients: QueryClient[] = [];

function renderComposer() {
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

beforeEach(() => localStorage.clear());
afterEach(() => {
  clients.splice(0).forEach((client) => client.clear());
  vi.unstubAllGlobals();
});

test('uncertain acceptance preserves text and retries the same persisted command', async () => {
  let firstBody = '';
  let posts = 0;
  const fetch = vi
    .fn<(path: string, options?: RequestInit) => Promise<Response>>()
    .mockImplementation((path, options) => {
      if (options?.method !== 'POST') return Promise.resolve(Response.json(active));
      posts += 1;
      const body = typeof options.body === 'string' ? options.body : '';
      if (posts === 1) {
        firstBody = body;
        expect(readTurnHint(fileId)?.command_id).toBeTruthy();
        return Promise.reject(new TypeError('lost acknowledgement'));
      }
      expect(body).toBe(firstBody);
      expect(path).toBe(`/api/job-files/${fileId}/inputs`);
      return Promise.resolve(
        Response.json({
          job_file_id: fileId,
          command_id: readTurnHint(fileId)?.command_id,
          execution_id: executionId,
          source_id: sourceId,
        }),
      );
    });
  vi.stubGlobal('fetch', fetch);
  renderComposer();
  await userEvent.type(screen.getByLabelText('訪談內容'), input);
  await userEvent.click(screen.getByRole('button', { name: '送出訪談' }));
  expect(await screen.findByText(/送出結果尚未確認/)).toBeVisible();
  expect(screen.getByLabelText('訪談內容')).toHaveValue(input);
  expect(screen.getByLabelText('訪談內容')).toBeDisabled();
  expect(localStorage.getItem(localStorage.key(0) ?? '')).not.toContain(input);
  await userEvent.click(screen.getByRole('button', { name: '重新確認原請求' }));
  expect(await screen.findByText('顧問正在處理，尚未正式完成。')).toBeVisible();
  expect(posts).toBe(2);
  expect(readTurnHint(fileId)?.execution_id).toBe(executionId);
});

test('reload verifies the saved execution then refreshes formal history and JD on completion', async () => {
  retainTurnHint(fileId, { command_id: commandId, execution_id: executionId });
  let reads = 0;
  const fetch = vi
    .fn<(path: string, options?: RequestInit) => Promise<Response>>()
    .mockImplementation(() =>
      Promise.resolve(
        Response.json({
          ...active,
          status: ++reads === 1 ? 'active' : 'completed',
        }),
      ),
    );
  vi.stubGlobal('fetch', fetch);
  const { client } = renderComposer();
  const invalidate = vi.spyOn(client, 'invalidateQueries');
  expect(await screen.findByText(input)).toBeVisible();
  expect(await screen.findByText('這次訪談已完成並保存。', {}, { timeout: 3_000 })).toBeVisible();
  await waitFor(() => {
    expect(invalidate).toHaveBeenCalledWith({
      queryKey: ['job-file', fileId, 'formal-interviews'],
    });
    expect(invalidate).toHaveBeenCalledWith({ queryKey: ['jd-profile', fileId] });
    expect(invalidate).toHaveBeenCalledWith({ queryKey: ['jd-work', fileId] });
  });
  expect(fetch.mock.calls.every(([, options]) => options?.method !== 'POST')).toBe(true);
});

test.each(['failed', 'cancelled'] as const)(
  '%s input stays explicitly nonformal',
  async (status) => {
    retainTurnHint(fileId, { command_id: commandId, execution_id: executionId });
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(Response.json({ ...active, status })));
    renderComposer();
    expect(await screen.findByText(/未列入正式訪談/)).toBeVisible();
    if (status === 'cancelled') await userEvent.click(screen.getByText('查看原輸入'));
    expect(screen.getByText(input)).toBeVisible();
    expect(screen.queryByText(/訪談序號/)).not.toBeInTheDocument();
    expect(
      screen.queryByRole('button', { name: /取消處理|暫停處理|繼續處理/ }),
    ).not.toBeInTheDocument();
    await userEvent.click(screen.getByRole('button', { name: '取回原文編輯' }));
    expect(screen.getByLabelText('訪談內容')).toHaveValue(input);
    expect(readTurnHint(fileId)).toBeNull();
  },
);

test('storage failure prevents a POST and keeps the draft', async () => {
  const fetch = vi.fn();
  vi.stubGlobal('fetch', fetch);
  renderComposer();
  await userEvent.type(screen.getByLabelText('訪談內容'), input);
  vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => {
    throw new Error('unavailable');
  });
  await userEvent.click(screen.getByRole('button', { name: '送出訪談' }));
  expect(await screen.findByText(/尚未送出/)).toBeVisible();
  expect(screen.getByLabelText('訪談內容')).toHaveValue(input);
  expect(fetch).not.toHaveBeenCalled();
});

test('wrong-file status is rejected without exposing its original input or opening a new turn', async () => {
  retainTurnHint(fileId, { command_id: commandId, execution_id: executionId });
  const fetch = vi.fn().mockResolvedValue(Response.json({ ...active, job_file_id: sourceId }));
  vi.stubGlobal('fetch', fetch);
  renderComposer();
  expect(await screen.findByText(/處理狀態不屬於這次訪談/)).toBeVisible();
  expect(screen.queryByText(input)).not.toBeInTheDocument();
  expect(screen.queryByRole('button', { name: '送出訪談' })).not.toBeInTheDocument();
});

test('reload after lost POST acknowledgement recovers by the same command without resending', async () => {
  const fetch = vi
    .fn<(path: string, options?: RequestInit) => Promise<Response>>()
    .mockImplementation((_path, options) => {
      if (options?.method === 'POST') return Promise.reject(new TypeError('lost acknowledgement'));
      return Promise.resolve(Response.json(active));
    });
  vi.stubGlobal('fetch', fetch);
  const first = renderComposer();
  await userEvent.type(screen.getByLabelText('訪談內容'), input);
  await userEvent.click(screen.getByRole('button', { name: '送出訪談' }));
  expect(await screen.findByText(/送出結果尚未確認/)).toBeVisible();
  const saved = readTurnHint(fileId);
  expect(saved?.execution_id).toBeNull();
  first.unmount();
  renderComposer();
  expect(await screen.findByText(input)).toBeVisible();
  expect(
    fetch.mock.calls.some(
      ([path]) =>
        path === `/api/job-files/${fileId}/consultant-turns/by-command/${saved?.command_id}`,
    ),
  ).toBe(true);
  expect(fetch.mock.calls.filter(([, options]) => options?.method === 'POST')).toHaveLength(1);
  expect(readTurnHint(fileId)).toEqual({
    command_id: saved?.command_id,
    execution_id: executionId,
  });
  expect(localStorage.getItem(localStorage.key(0) ?? '')).not.toContain(input);
});

test('unresolved command lookup keeps the identity and allows read-only retry', async () => {
  retainTurnHint(fileId, { command_id: commandId, execution_id: null });
  const fetch = vi
    .fn<(path: string, options?: RequestInit) => Promise<Response>>()
    .mockResolvedValueOnce(
      Response.json({ detail: { code: 'consultant_turn_not_found' } }, { status: 404 }),
    )
    .mockImplementation(() => Promise.resolve(Response.json(active)));
  vi.stubGlobal('fetch', fetch);
  renderComposer();
  expect(await screen.findByText(/尚未查到原請求的受理結果/)).toBeVisible();
  expect(readTurnHint(fileId)).toEqual({ command_id: commandId, execution_id: null });
  expect(screen.queryByRole('button', { name: '送出訪談' })).not.toBeInTheDocument();
  await userEvent.click(screen.getByRole('button', { name: '重新查回原請求' }));
  expect(await screen.findByText(input)).toBeVisible();
  expect(fetch.mock.calls.every(([, options]) => options?.method !== 'POST')).toBe(true);
});

test('saved commentary is plain nonformal text and remains expandable after completion', async () => {
  retainTurnHint(fileId, { command_id: commandId, execution_id: executionId });
  const publicText = '<script>not executable</script> 正在核對職責';
  let reads = 0;
  vi.stubGlobal(
    'fetch',
    vi.fn(() =>
      Promise.resolve(
        Response.json({
          ...active,
          status: ++reads === 1 ? 'active' : 'completed',
          commentary: [{ response_id: 'response-1', message_id: 'message-1', text: publicText }],
        }),
      ),
    ),
  );
  renderComposer();
  expect(await screen.findByText(publicText)).toBeVisible();
  expect(screen.getByText('公開處理訊息（非正式訪談、不可引用）')).toBeVisible();
  expect(document.querySelector('script')).toBeNull();
  expect(await screen.findByText('這次訪談已完成並保存。', {}, { timeout: 3_000 })).toBeVisible();
  expect(screen.getByText(publicText)).not.toBeVisible();
  await userEvent.click(screen.getByText('回看本次公開處理訊息'));
  expect(screen.getByText(publicText)).toBeVisible();
  expect(screen.queryByText(/訪談序號/)).not.toBeInTheDocument();
});

test.each([
  { status: 503, code: 'model_not_configured' },
  { status: 503, code: 'consultant_unavailable' },
  { status: 503, code: 'database_not_configured' },
  { status: 404, code: 'job_file_not_found' },
])(
  'a first submission explicitly rejected with $status/$code clears only its hint and remains editable',
  async ({ status, code }) => {
    const fetch = vi.fn(() =>
      Promise.resolve(Response.json({ detail: { code, debug: 'private data' } }, { status })),
    );
    vi.stubGlobal('fetch', fetch);
    const first = renderComposer();
    await userEvent.type(screen.getByLabelText('訪談內容'), input);
    await userEvent.click(screen.getByRole('button', { name: '送出訪談' }));
    expect(await screen.findByText(/這次輸入未被接受/)).toBeVisible();
    expect(screen.getByLabelText('訪談內容')).toBeEnabled();
    expect(screen.getByLabelText('訪談內容')).toHaveValue(input);
    expect(readTurnHint(fileId)).toBeNull();
    expect(screen.queryByText(/private data/)).not.toBeInTheDocument();
    first.unmount();
    renderComposer();
    expect(screen.getByRole('button', { name: '送出訪談' })).toBeEnabled();
    expect(fetch).toHaveBeenCalledTimes(1);
  },
);

test.each([503, 404])(
  'an unrecognized %s response must retain the uncertain command',
  async (status) => {
    vi.stubGlobal(
      'fetch',
      vi.fn(() => Promise.resolve(Response.json({ detail: 'private data' }, { status }))),
    );
    renderComposer();
    await userEvent.type(screen.getByLabelText('訪談內容'), input);
    await userEvent.click(screen.getByRole('button', { name: '送出訪談' }));
    expect(await screen.findByText(/送出結果尚未確認/)).toBeVisible();
    expect(readTurnHint(fileId)?.command_id).toBeTruthy();
    expect(screen.getByLabelText('訪談內容')).toBeDisabled();
    expect(screen.queryByText(/private data/)).not.toBeInTheDocument();
  },
);

test('a pre-admission rejection on retry does not erase an earlier uncertain acceptance', async () => {
  vi.stubGlobal(
    'fetch',
    vi
      .fn()
      .mockRejectedValueOnce(new TypeError('lost acknowledgement'))
      .mockImplementation(() =>
        Promise.resolve(
          Response.json({ detail: { code: 'consultant_unavailable' } }, { status: 503 }),
        ),
      ),
  );
  renderComposer();
  await userEvent.type(screen.getByLabelText('訪談內容'), input);
  await userEvent.click(screen.getByRole('button', { name: '送出訪談' }));
  expect(await screen.findByText(/送出結果尚未確認/)).toBeVisible();
  const hint = readTurnHint(fileId);
  await userEvent.click(screen.getByRole('button', { name: '重新確認原請求' }));
  expect(await screen.findByText(/送出結果尚未確認/)).toBeVisible();
  expect(readTurnHint(fileId)).toEqual(hint);
  expect(screen.getByLabelText('訪談內容')).toBeDisabled();
});
