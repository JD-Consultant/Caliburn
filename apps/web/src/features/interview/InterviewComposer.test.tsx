import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, beforeEach, expect, test, vi } from 'vitest';
import { InterviewComposer } from './InterviewComposer';
import { clearDeletedInterview, readTurnHint, retainTurnHint } from './interview-turn-api';

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
  plan_preview: null,
  candidate: null,
};
const clients: QueryClient[] = [];

function renderComposer() {
  // These command-recovery fixtures predate discovery. They have no other in-flight Turn;
  // discovery-specific and shared-page behavior is exercised in the adjacent discovery suite.
  const commandFetch = globalThis.fetch;
  vi.stubGlobal('fetch', (path: RequestInfo | URL, options?: RequestInit) =>
    path === `/api/job-files/${fileId}/consultant-turns/current`
      ? Promise.resolve(Response.json({ turn: null }))
      : commandFetch(path, options),
  );
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  clients.push(client);
  return {
    client,
    ...render(
      <QueryClientProvider client={client}>
        <InterviewComposer refreshCompletedTurn={async () => {}} jobFileId={fileId} />
      </QueryClientProvider>,
    ),
  };
}

beforeEach(() => localStorage.clear());
afterEach(() => {
  clients.splice(0).forEach((client) => client.clear());
  vi.useRealTimers();
  vi.unstubAllGlobals();
});

async function holdFileLock(): Promise<() => Promise<void>> {
  let release: () => void = () => {};
  let acquired: () => void = () => {};
  const locked = new Promise<void>((resolve) => {
    acquired = resolve;
  });
  const held = navigator.locks.request('caliburn:interview-turn:' + fileId, {}, () => {
    acquired();
    return new Promise<void>((resolve) => {
      release = resolve;
    });
  });
  await locked;
  return async () => {
    release();
    await held;
  };
}

test('waiting for the file lock protects the first input until exactly one POST', async () => {
  const release = await holdFileLock();
  const posts: { command_id: string; text: string }[] = [];
  vi.stubGlobal('fetch', (_path: string, options?: RequestInit) => {
    if (options?.method !== 'POST') return Promise.resolve(Response.json(active));
    if (typeof options.body !== 'string') throw new Error('Expected a JSON request body');
    const command = JSON.parse(options.body) as { command_id: string; text: string };
    posts.push(command);
    return Promise.resolve(
      Response.json({
        job_file_id: fileId,
        command_id: command.command_id,
        execution_id: executionId,
        source_id: sourceId,
      }),
    );
  });
  renderComposer();
  const textbox = screen.getByRole('textbox', { name: '訪談內容' });
  await userEvent.type(textbox, input);
  await userEvent.click(screen.getByRole('button', { name: '送出訪談' }));
  try {
    expect(textbox).toBeDisabled();
    expect(screen.getByRole('button', { name: '正在確認送出…' })).toBeDisabled();
    await userEvent.type(textbox, '等待期間補充');
    expect(textbox).toHaveValue(input);
    expect(posts).toHaveLength(0);
    const form = textbox.closest('form');
    if (!form) throw new Error('Expected composer form');
    fireEvent.submit(form);
  } finally {
    await act(release);
  }
  await screen.findByText('顧問正在處理，尚未正式完成。');
  expect(posts).toEqual([{ command_id: readTurnHint(fileId)?.command_id, text: input }]);
});

test('lock acquisition timeout sends nothing and unlocks the original draft for editing', async () => {
  const release = await holdFileLock();
  const fetch = vi.fn();
  vi.stubGlobal('fetch', fetch);
  renderComposer();
  const textbox = screen.getByRole('textbox', { name: '訪談內容' });
  await userEvent.type(textbox, input);
  await waitFor(() => expect(screen.getByRole('button', { name: '送出訪談' })).toBeEnabled());
  const form = textbox.closest('form');
  if (!form) throw new Error('Expected composer form');
  vi.useFakeTimers();
  try {
    await act(async () => {
      fireEvent.submit(form);
      await vi.advanceTimersByTimeAsync(0);
    });
    expect(textbox).toBeDisabled();
    await act(async () => {
      await vi.advanceTimersByTimeAsync(5_000);
    });
    expect(screen.getByText(/尚未送出/)).toBeVisible();
    expect(screen.queryByText(/送出結果尚未確認/)).not.toBeInTheDocument();
    expect(textbox).toBeEnabled();
    expect(textbox).toHaveValue(input);
    expect(screen.getByRole('button', { name: '送出訪談' })).toBeEnabled();
    expect(fetch).not.toHaveBeenCalled();
    expect(readTurnHint(fileId)).toBeNull();
  } finally {
    vi.useRealTimers();
    await act(release);
  }
  await userEvent.type(textbox, '可繼續編輯');
  expect(textbox).toHaveValue(input + '可繼續編輯');
});

test('unmount aborts a queued reservation so releasing the lock cannot send a late POST', async () => {
  const release = await holdFileLock();
  const fetch = vi.fn();
  vi.stubGlobal('fetch', fetch);
  const { unmount } = renderComposer();
  await userEvent.type(screen.getByRole('textbox', { name: '訪談內容' }), input);
  await userEvent.click(screen.getByRole('button', { name: '送出訪談' }));
  unmount();
  await act(release);
  expect(fetch).not.toHaveBeenCalled();
  expect(readTurnHint(fileId)).toBeNull();
});

test('unmount after reservation storage succeeds prevents the post-lock POST', async () => {
  const release = await holdFileLock();
  const fetch = vi.fn();
  vi.stubGlobal('fetch', fetch);
  const { unmount } = renderComposer();
  await userEvent.type(screen.getByRole('textbox', { name: '訪談內容' }), input);
  await userEvent.click(screen.getByRole('button', { name: '送出訪談' }));
  const save = localStorage.setItem.bind(localStorage);
  const stored = vi.spyOn(Storage.prototype, 'setItem').mockImplementation((key, value) => {
    save(key, value);
    unmount();
  });
  await act(release);
  expect(stored).toHaveBeenCalledOnce();
  const hint = readTurnHint(fileId);
  expect(hint?.command_id).toBeTypeOf('string');
  expect(hint?.execution_id).toBeNull();
  expect(fetch).not.toHaveBeenCalled();
});

test('without Web Locks discovery remains readable but input cannot be submitted', async () => {
  const locks = navigator.locks;
  Object.defineProperty(navigator, 'locks', { configurable: true, value: undefined });
  const fetch = vi.fn();
  vi.stubGlobal('fetch', fetch);
  try {
    const { client } = renderComposer();
    await waitFor(() =>
      expect(client.getQueryData(['current-consultant-turn', fileId])).toEqual({ turn: null }),
    );
    expect(screen.getByText(/仍可查詢既有處理/)).toBeVisible();
    expect(screen.getByRole('button', { name: '送出訪談' })).toBeDisabled();
    await userEvent.type(screen.getByRole('textbox', { name: '訪談內容' }), input);
    const form = screen.getByRole('textbox', { name: '訪談內容' }).closest('form');
    if (!form) throw new Error('Expected composer form');
    fireEvent.submit(form);
    await screen.findByText(/尚未送出/);
    expect(fetch).not.toHaveBeenCalled();
  } finally {
    Object.defineProperty(navigator, 'locks', { configurable: true, value: locks });
  }
});

test('an accepted POST whose execution hint cannot be saved remains known accepted', async () => {
  vi.stubGlobal('fetch', (_path: string, options?: RequestInit) => {
    if (options?.method !== 'POST') return Promise.resolve(Response.json(active));
    vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => {
      throw new Error('storage unavailable');
    });
    return Promise.resolve(
      Response.json({
        job_file_id: fileId,
        command_id: readTurnHint(fileId)?.command_id,
        execution_id: executionId,
        source_id: sourceId,
      }),
    );
  });
  renderComposer();
  await userEvent.type(screen.getByRole('textbox', { name: '訪談內容' }), input);
  await userEvent.click(screen.getByRole('button', { name: '送出訪談' }));
  expect(await screen.findByText(/原輸入已受理/)).toBeVisible();
  expect(screen.queryByText(/尚未送出|送出結果尚未確認/)).not.toBeInTheDocument();
  expect(await screen.findByText('顧問正在處理，尚未正式完成。')).toBeVisible();
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

test('reload verifies the saved execution and follows it to completion without resending', async () => {
  await retainTurnHint(fileId, { command_id: commandId, execution_id: executionId });
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
  renderComposer();
  expect(await screen.findByText(input)).toBeVisible();
  expect(await screen.findByText('這次訪談已完成並保存。', {}, { timeout: 3_000 })).toBeVisible();
  expect(fetch.mock.calls.every(([, options]) => options?.method !== 'POST')).toBe(true);
});

test.each(['failed', 'cancelled'] as const)(
  '%s input stays explicitly nonformal',
  async (status) => {
    await retainTurnHint(fileId, { command_id: commandId, execution_id: executionId });
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(Response.json({ ...active, status })));
    renderComposer();
    expect(await screen.findByText(/未列入正式訪談/)).toBeVisible();
    if (status === 'cancelled') await userEvent.click(screen.getByText('查看原輸入'));
    expect(screen.getByText(input)).toBeVisible();
    expect(screen.queryByRole('heading', { name: /受訪員工/ })).not.toBeInTheDocument();
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
  expect(screen.getByLabelText('訪談內容')).toBeEnabled();
  expect(screen.getByRole('button', { name: '送出訪談' })).toBeEnabled();
  expect(fetch).not.toHaveBeenCalled();
});

test('wrong-file status is rejected without exposing its original input or opening a new turn', async () => {
  await retainTurnHint(fileId, { command_id: commandId, execution_id: executionId });
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
  await retainTurnHint(fileId, { command_id: commandId, execution_id: null });
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

test('saved commentary is safe nonformal text and leaves the composer on completion', async () => {
  await retainTurnHint(fileId, { command_id: commandId, execution_id: executionId });
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
  expect(screen.getByText('本次處理過程')).toBeVisible();
  expect(document.querySelector('script')).toBeNull();
  expect(await screen.findByText('這次訪談已完成並保存。', {}, { timeout: 3_000 })).toBeVisible();
  expect(screen.queryByText(publicText)).not.toBeInTheDocument();
  expect(screen.queryByText('回看本次處理過程')).not.toBeInTheDocument();
  expect(screen.queryByRole('heading', { name: /受訪員工/ })).not.toBeInTheDocument();
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
    await waitFor(() => expect(screen.getByRole('button', { name: '送出訪談' })).toBeEnabled());
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

test.each(['timeout', 'abort', 'non-json'] as const)(
  'an uncertain %s response keeps the original pending command and text',
  async (failure) => {
    const writes: string[] = [];
    vi.stubGlobal('fetch', (_path: string, options?: RequestInit) => {
      if (options?.method !== 'POST') return Promise.resolve(Response.json(active));
      writes.push(typeof options.body === 'string' ? options.body : '');
      if (failure === 'non-json')
        return Promise.resolve(new Response('<html>unknown</html>', { status: 200 }));
      return Promise.reject(
        new DOMException(
          'synthetic transport failure',
          failure === 'timeout' ? 'TimeoutError' : 'AbortError',
        ),
      );
    });
    renderComposer();
    await userEvent.type(screen.getByLabelText('訪談內容'), input);
    await userEvent.click(screen.getByRole('button', { name: '送出訪談' }));
    expect(await screen.findByText(/送出結果尚未確認/)).toBeVisible();
    const original = readTurnHint(fileId);
    expect(original?.execution_id).toBeNull();
    expect(screen.getByLabelText('訪談內容')).toHaveValue(input);
    await userEvent.click(screen.getByRole('button', { name: '重新確認原請求' }));
    await waitFor(() => expect(writes).toHaveLength(2));
    expect(writes[1]).toBe(writes[0]);
    expect(readTurnHint(fileId)).toEqual(original);
  },
);

test.each(['delete-first', 'submit-first'] as const)(
  'confirmed deletion cancels a queued reservation before React unmounts (%s)',
  async (order) => {
    let release: () => void = () => {};
    const held = navigator.locks.request(
      'caliburn:interview-turn:' + fileId,
      { mode: 'exclusive' },
      () =>
        new Promise<void>((resolve) => {
          release = resolve;
        }),
    );
    await Promise.resolve();
    await Promise.resolve();
    const posts: string[] = [];
    vi.stubGlobal('fetch', (_path: string, options?: RequestInit) => {
      if (options?.method === 'POST')
        posts.push(typeof options.body === 'string' ? options.body : '');
      return Promise.resolve(Response.json(active));
    });
    renderComposer();
    await userEvent.type(screen.getByLabelText('訪談內容'), input);
    await waitFor(() => expect(screen.getByRole('button', { name: '送出訪談' })).toBeEnabled());
    let deletion: Promise<void> = Promise.resolve();
    act(() => {
      const form = screen.getByLabelText('訪談內容').closest('form');
      if (!form) throw new Error('Expected composer form');
      if (order === 'delete-first') deletion = clearDeletedInterview(fileId);
      fireEvent.submit(form);
      if (order === 'submit-first') deletion = clearDeletedInterview(fileId);
    });
    await act(async () => {
      release();
      await held;
      await deletion;
    });
    expect(posts).toEqual([]);
    expect(readTurnHint(fileId)).toBeNull();
  },
);
