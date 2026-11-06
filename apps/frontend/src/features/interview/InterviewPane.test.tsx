import { useCallback } from 'react';
import { QueryClient, QueryClientProvider, useQueryClient } from '@tanstack/react-query';
import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, expect, it, vi } from 'vitest';
import type {
  QuestionExchange,
  StepView,
  TurnEvent,
  TurnView,
} from '../../shared/api/generated';
import { streamTurnEvents } from '../../shared/api/sse';
import { InterviewPane } from './InterviewPane';
import { interviewKeys, useAgentTurns } from './queries';
import { retainSubmission } from './submission';
import { validateSubmitTurnRequest } from '../../shared/api/generated/validators';

vi.mock('../../shared/api/sse', () => ({ streamTurnEvents: vi.fn() }));
const workspaceId = '00000000-0000-4000-8000-000000000001';
const turnId = '00000000-0000-4000-8000-000000000002';
const messageId = '00000000-0000-4000-8000-000000000003';
const questionId = '00000000-0000-4000-8000-000000000004';
const turn: TurnView = {
  workspace_id: workspaceId,
  turn_id: turnId,
  input: '原始訪談',
  output: null,
  status: 'interrupted',
  interrupts: [],
  usage: null,
  compactions: [],
  created_at: '2026-11-06T00:00:00Z',
  updated_at: '2026-11-06T00:00:00Z',
};
const answered: QuestionExchange = {
  model_step: 1,
  call_id: 'question-call',
  status: 'answered',
  questions: [
    {
      message_id: questionId,
      question_ref: 'message_1',
      question: '您如何核對？',
      options: [],
      multi_select: false,
      header: null,
    },
  ],
  answers: [{ question_message_id: questionId, selected: [], custom: '查原件' }],
};

function Harness({ id = workspaceId }: { id?: string }) {
  const client = useQueryClient();
  const turns = useAgentTurns(id);
  const refresh = useCallback(() => {
    void client.invalidateQueries({ queryKey: interviewKeys.all(id) });
  }, [client, id]);
  return (
    <InterviewPane
      workspaceId={id}
      intervieweeName="林員工"
      turnsQuery={turns}
      onWorkspaceChanged={refresh}
      renderTurnChanges={() => null}
    />
  );
}
function mount(id = workspaceId) {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  return {
    client,
    ...render(
      <QueryClientProvider client={client}>
        <Harness id={id} />
      </QueryClientProvider>,
    ),
  };
}
function backend(
  options: {
    turns?: TurnView[];
    questions?: QuestionExchange[];
    steps?: StepView[];
    post?: (path: string, init: RequestInit) => Promise<Response>;
  } = {},
) {
  const fetcher = vi.fn(async (path: string, init?: RequestInit) => {
    if (init?.method === 'POST' && options.post) return options.post(path, init);
    if (path.endsWith('/agent/turns')) return Response.json(options.turns ?? [turn]);
    if (path.endsWith('/questions')) return Response.json(options.questions ?? []);
    if (path.endsWith('/steps')) return Response.json(options.steps ?? []);
    if (path.endsWith('/plan'))
      return Response.json({ workspace_id: workspaceId, version: null, body: null });
    if (path.endsWith('/interview/messages'))
      return Response.json([
        {
          message_id: messageId,
          turn_id: turnId,
          speaker: 'employee',
          kind: 'text',
          text: '原始訪談',
          reply_to_message_id: null,
        },
      ]);
    if (path.endsWith(`/turns/${turnId}`))
      return Response.json(options.turns?.[0] ?? turn);
    throw new Error(`Unexpected ${path}`);
  });
  vi.stubGlobal('fetch', fetcher);
  return fetcher;
}
beforeEach(() => {
  sessionStorage.clear();
  vi.mocked(streamTurnEvents).mockImplementation(
    (_path, { signal }) =>
      new Promise((_resolve, reject) => {
        signal.addEventListener(
          'abort',
          () => reject(new DOMException('aborted', 'AbortError')),
          { once: true },
        );
      }),
  );
});

it('saved_answers_are_not_asked_again: 已答後中斷只提供恢復，不重問舊題組', async () => {
  backend({ questions: [answered] });
  mount();
  expect(await screen.findByRole('button', { name: '恢復本輪' })).toBeEnabled();
  expect(screen.queryByRole('form', { name: '回答顧問問題' })).not.toBeInTheDocument();
});

it('瀏覽器禁止sessionStorage時仍呈現訪談，明示未知並停用寫入', async () => {
  const fetcher = backend({ turns: [] });
  vi.spyOn(window, 'sessionStorage', 'get').mockImplementation(() => {
    throw new DOMException('Storage is blocked', 'SecurityError');
  });
  const view = mount();
  expect(await screen.findByText('原始訪談')).toBeVisible();
  expect(screen.getAllByText(/無法讀取待確認/).length).toBeGreaterThan(0);
  expect(screen.getByRole('textbox', { name: '訪談內容' })).toBeDisabled();
  expect(screen.getByRole('button', { name: '送出訪談' })).toBeDisabled();
  await waitFor(() =>
    expect(view.client.getQueryState(interviewKeys.turns(workspaceId))?.status).toBe(
      'error',
    ),
  );
  expect(fetcher.mock.calls.filter((call) => call[1]?.method === 'POST')).toHaveLength(0);
});

it('取消暫存讀取被拒絕時，快取輪次仍可查閱但不能恢復或取消', async () => {
  const fetcher = backend();
  const getItem = Storage.prototype.getItem.bind(sessionStorage);
  vi.spyOn(Storage.prototype, 'getItem').mockImplementation((key: string) => {
    if (key.startsWith('caliburn:pending-cancel:'))
      throw new DOMException('Blocked', 'SecurityError');
    return getItem(key);
  });
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  client.setQueryData(interviewKeys.turns(workspaceId), [turn]);
  render(
    <QueryClientProvider client={client}>
      <Harness />
    </QueryClientProvider>,
  );
  expect(await screen.findByText('原始訪談')).toBeVisible();
  expect(await screen.findByRole('button', { name: '恢復本輪' })).toBeDisabled();
  expect(screen.getByRole('button', { name: '取消本輪' })).toBeDisabled();
  await waitFor(() =>
    expect(client.getQueryState(interviewKeys.turns(workspaceId))?.status).toBe('error'),
  );
  expect(fetcher.mock.calls.filter((call) => call[1]?.method === 'POST')).toHaveLength(0);
});

it('僅取消暫存不可讀時也禁止重送既有未確認輸入', async () => {
  retainSubmission(workspaceId, { turn_id: turnId, input: '待確認原文' });
  const fetcher = backend({ turns: [] });
  const getItem = Storage.prototype.getItem.bind(sessionStorage);
  vi.spyOn(Storage.prototype, 'getItem').mockImplementation((key: string) => {
    if (key.startsWith('caliburn:pending-cancel:'))
      throw new DOMException('Blocked', 'SecurityError');
    return getItem(key);
  });
  mount();
  expect(await screen.findByText('原始訪談')).toBeVisible();
  expect(screen.getByRole('button', { name: '重新確認原請求' })).toBeDisabled();
  fireEvent.keyDown(screen.getByRole('textbox', { name: '訪談內容' }), { key: 'Enter' });
  expect(fetcher.mock.calls.filter((call) => call[1]?.method === 'POST')).toHaveLength(0);
});

it('正常儲存下未確認輸入仍可沿原turn重試', async () => {
  const request = { turn_id: turnId, input: '待確認原文' };
  retainSubmission(workspaceId, request);
  const options: {
    turns: TurnView[];
    post: (path: string, init: RequestInit) => Promise<Response>;
  } = {
    turns: [],
    post: (_path, init) => {
      expect(init.body).toBe(JSON.stringify(request));
      const completed = { ...turn, input: request.input, status: 'completed' as const };
      options.turns = [completed];
      return Promise.resolve(Response.json(completed));
    },
  };
  backend(options);
  mount();
  const button = await screen.findByRole('button', { name: '重新確認原請求' });
  expect(button).toBeEnabled();
  await userEvent.setup().click(button);
  expect(await screen.findByText(/已完成處理紀錄/)).toBeVisible();
  expect(sessionStorage.getItem(`caliburn:pending-turn:${workspaceId}`)).toBeNull();
});

it('cancellation_failure_can_continue: 503後保留正文，冷重開仍沿原turn重送取消，204才清除', async () => {
  const user = userEvent.setup();
  let confirmed = false;
  let calls = 0;
  const fetcher = backend({
    post: () => {
      calls++;
      if (calls === 1) return Promise.resolve(Response.json({}, { status: 503 }));
      confirmed = true;
      return Promise.resolve(new Response(null, { status: 204 }));
    },
  });
  const first = mount();
  expect(await screen.findByText('原始訪談')).toBeInTheDocument();
  await user.click(await screen.findByRole('button', { name: '取消本輪' }));
  expect(await screen.findByText(/尚未確認取消完成/)).toBeInTheDocument();
  expect(screen.getByText('原始訪談')).toBeInTheDocument();
  first.unmount();
  fetcher.mockImplementation((path, init) => {
    if (init?.method === 'POST') {
      expect(path).toBe(`/api/workspaces/${workspaceId}/agent/turns/${turnId}/cancel`);
      confirmed = true;
      return Promise.resolve(new Response(null, { status: 204 }));
    }
    if (
      path.endsWith('/agent/turns') ||
      path.endsWith('/interview/messages') ||
      path.endsWith('/questions') ||
      path.endsWith('/steps')
    )
      return Promise.resolve(Response.json([]));
    if (path.endsWith('/plan'))
      return Promise.resolve(
        Response.json({ workspace_id: workspaceId, version: null, body: null }),
      );
    return Promise.resolve(Response.json({}, { status: 404 }));
  });
  mount();
  await user.click(await screen.findByRole('button', { name: '重新確認取消' }));
  await waitFor(() =>
    expect(
      screen.queryByRole('button', { name: '重新確認取消' }),
    ).not.toBeInTheDocument(),
  );
  expect(confirmed).toBe(true);
  expect(sessionStorage.getItem(`caliburn:pending-cancel:${workspaceId}`)).toBeNull();
});

it('resync_replaces_transient_output: SSE增量失聯後以保存步驟取代，不拼舊字', async () => {
  let emit: ((event: TurnEvent) => void) | undefined;
  let disconnect: (() => void) | undefined;
  vi.mocked(streamTurnEvents).mockImplementation((_path, options) => {
    emit = options.onEvent;
    return new Promise<void>((resolve) => {
      disconnect = resolve;
    });
  });
  const running = { ...turn, status: 'running' as const };
  backend({
    turns: [running],
    steps: [
      {
        model_step: 1,
        messages: ['保存正文'],
        reasoning_summary: [],
        usage: null,
        compactions: [],
        tool_calls: [],
        interrupts: [],
      },
    ],
  });
  mount();
  await waitFor(() => expect(emit).toBeDefined());
  act(() => {
    emit?.({ event: 'text_delta', data: { model_step: 2, delta: '尚未保存片段' } });
  });
  expect(screen.getByText('尚未保存片段')).toBeInTheDocument();
  act(() => {
    disconnect?.();
  });
  await waitFor(() => expect(screen.queryByText('尚未保存片段')).not.toBeInTheDocument());
  expect(screen.getByText('保存正文')).toBeInTheDocument();
});

it('IME確認和Shift+Enter不送出，普通Enter沿原文送出且保持輸入焦點', async () => {
  const user = userEvent.setup();
  let submitted = false;
  const fetcher = backend({
    turns: [],
    post: (_path, init) => {
      submitted = true;
      if (typeof init.body !== 'string') throw new Error('missing body');
      const request: unknown = JSON.parse(init.body);
      if (
        typeof request !== 'object' ||
        request === null ||
        !('turn_id' in request) ||
        !('input' in request)
      )
        throw new Error('missing request');
      return Promise.resolve(
        Response.json(
          {
            ...turn,
            turn_id: request.turn_id,
            input: request.input,
            status: 'completed',
          },
          { status: 202 },
        ),
      );
    },
  });
  mount();
  const input = screen.getByRole('textbox', { name: '訪談內容' });
  await user.type(input, '原話');
  await waitFor(() =>
    expect(screen.getByRole('button', { name: '送出訪談' })).toBeEnabled(),
  );
  fireEvent.keyDown(input, { key: 'Enter', isComposing: true });
  fireEvent.keyDown(input, { key: 'Enter', keyCode: 229 });
  fireEvent.keyDown(input, { key: 'Enter', shiftKey: true });
  expect(submitted).toBe(false);
  fireEvent.keyDown(input, { key: 'Enter' });
  await waitFor(() => expect(submitted).toBe(true));
  await waitFor(() => expect(input).toHaveValue(''));
  expect(input).toHaveFocus();
  expect(fetcher.mock.calls.filter((call) => call[1]?.method === 'POST')).toHaveLength(1);
});

it('terminal status即使stream尚未關閉，也查回題組並刷新輪次', async () => {
  let emit: ((event: TurnEvent) => void) | undefined;
  vi.mocked(streamTurnEvents).mockImplementation((_path, options) => {
    emit = options.onEvent;
    return new Promise(() => undefined);
  });
  const options: { turns: TurnView[]; questions: QuestionExchange[] } = {
    turns: [{ ...turn, status: 'running' }],
    questions: [],
  };
  backend(options);
  mount();
  await waitFor(() => expect(emit).toBeDefined());
  options.turns = [{ ...turn, status: 'waiting_for_input' }];
  options.questions = [{ ...answered, status: 'waiting', answers: null }];
  act(() => {
    emit?.({ event: 'status', data: options.turns[0] ?? turn });
  });
  expect(await screen.findByRole('form', { name: '回答顧問問題' })).toBeInTheDocument();
});

it('執行中tool_call顯示原參數，沒有結果不宣稱未執行', async () => {
  let emit: ((event: TurnEvent) => void) | undefined;
  vi.mocked(streamTurnEvents).mockImplementation((_path, options) => {
    emit = options.onEvent;
    return new Promise(() => undefined);
  });
  backend({ turns: [{ ...turn, status: 'running' }] });
  mount();
  await waitFor(() => expect(emit).toBeDefined());
  act(() => {
    emit?.({
      event: 'tool_call',
      data: {
        model_step: 1,
        call_id: 'tool-1',
        name: 'read_plan',
        arguments: '{"scope":"current"}',
      },
    });
  });
  expect(await screen.findByText('read_plan')).toBeInTheDocument();
  expect(screen.getByText('{"scope":"current"}')).toBeInTheDocument();
});

it('未知送出已查回後取消204，Composer不保留可重送的原輪', async () => {
  retainSubmission(workspaceId, { turn_id: turnId, input: '原始訪談' });
  const options = {
    turns: [turn],
    post: () => {
      options.turns = [];
      return Promise.resolve(new Response(null, { status: 204 }));
    },
  };
  backend(options);
  mount();
  const user = userEvent.setup();
  expect(
    await screen.findByRole('button', { name: '重新確認原請求' }),
  ).toBeInTheDocument();
  await user.click(await screen.findByRole('button', { name: '取消本輪' }));
  await waitFor(() =>
    expect(
      screen.queryByRole('button', { name: '重新確認原請求' }),
    ).not.toBeInTheDocument(),
  );
  expect(screen.getByRole('textbox', { name: '訪談內容' })).toHaveValue('');
});

it('刪除scope後送出ACK晚到不復活query cache', async () => {
  let release: ((response: Response) => void) | undefined;
  let submitted: TurnView | undefined;
  backend({
    turns: [],
    post: (_path, init) => {
      if (typeof init.body !== 'string') throw new Error('missing body');
      const request: unknown = JSON.parse(init.body);
      if (!validateSubmitTurnRequest(request)) throw new Error('invalid fixture');
      submitted = { ...turn, turn_id: request.turn_id, input: request.input };
      return new Promise<Response>((resolve) => {
        release = resolve;
      });
    },
  });
  const page = mount();
  const user = userEvent.setup();
  await user.type(screen.getByRole('textbox', { name: '訪談內容' }), '送出後刪除');
  await user.click(await screen.findByRole('button', { name: '送出訪談' }));
  await waitFor(() => expect(release).toBeDefined());
  page.unmount();
  await page.client.cancelQueries();
  page.client.removeQueries();
  act(() => {
    release?.(Response.json(submitted, { status: 202 }));
  });
  await waitFor(() => expect(page.client.getQueryCache().getAll()).toEqual([]));
});

it('手動重連先核對正式狀態，已completed不再次訂閱', async () => {
  const options = { turns: [{ ...turn, status: 'running' as TurnView['status'] }] };
  backend(options);
  mount();
  await waitFor(() => expect(streamTurnEvents).toHaveBeenCalled());
  const before = vi.mocked(streamTurnEvents).mock.calls.length;
  options.turns = [{ ...turn, status: 'completed' }];
  await userEvent.setup().click(await screen.findByRole('button', { name: '重新連線' }));
  expect(await screen.findByText(/已完成處理紀錄/)).toBeInTheDocument();
  expect(vi.mocked(streamTurnEvents).mock.calls.length).toBe(before);
});

it('取消204先到、原POST ACK晚到，不復活已取消輪次', async () => {
  let release: ((response: Response) => void) | undefined;
  let accepted: TurnView | undefined;
  const options: {
    turns: TurnView[];
    post: (path: string, init: RequestInit) => Promise<Response>;
  } = {
    turns: [],
    post: (path, init) => {
      if (path.endsWith('/cancel')) {
        options.turns = [];
        return Promise.resolve(new Response(null, { status: 204 }));
      }
      if (typeof init.body !== 'string') throw new Error('missing body');
      const body: unknown = JSON.parse(init.body);
      if (!validateSubmitTurnRequest(body)) throw new Error('invalid submit');
      accepted = { ...turn, turn_id: body.turn_id, input: body.input };
      options.turns = [accepted];
      return new Promise<Response>((resolve) => {
        release = resolve;
      });
    },
  };
  const fetcher = backend(options);
  const defaultFetch = fetcher.getMockImplementation();
  fetcher.mockImplementation((path, init) => {
    if (accepted && path.endsWith(`/turns/${accepted.turn_id}`))
      return Promise.resolve(
        options.turns.length
          ? Response.json(accepted)
          : Response.json({}, { status: 404 }),
      );
    if (!defaultFetch) throw new Error('missing fetch');
    return defaultFetch(path, init);
  });
  const view = mount();
  const user = userEvent.setup();
  await user.type(screen.getByRole('textbox', { name: '訪談內容' }), '稍後取消');
  await user.click(screen.getByRole('button', { name: '送出訪談' }));
  await waitFor(() => expect(release).toBeDefined());
  await act(async () => {
    await view.client.invalidateQueries({ queryKey: interviewKeys.turns(workspaceId) });
  });
  await user.click(await screen.findByRole('button', { name: '取消本輪' }));
  await waitFor(() =>
    expect(screen.queryByRole('button', { name: '取消本輪' })).not.toBeInTheDocument(),
  );
  act(() => {
    release?.(Response.json(accepted, { status: 202 }));
  });
  await waitFor(() =>
    expect(screen.getByRole('textbox', { name: '訪談內容' })).toBeEnabled(),
  );
  expect(
    accepted &&
      view.client.getQueryData(interviewKeys.turn(workspaceId, accepted.turn_id)),
  ).toBeUndefined();
});

it.each(['resume', 'answers'] as const)(
  '%s ACK晚到不重建已移除workspace cache',
  async (action) => {
    let release: ((response: Response) => void) | undefined;
    backend({
      turns: [
        { ...turn, status: action === 'resume' ? 'interrupted' : 'waiting_for_input' },
      ],
      questions:
        action === 'resume' ? [] : [{ ...answered, status: 'waiting', answers: null }],
      post: () =>
        new Promise<Response>((resolve) => {
          release = resolve;
        }),
    });
    const view = mount();
    const user = userEvent.setup();
    if (action === 'resume')
      await user.click(await screen.findByRole('button', { name: '恢復本輪' }));
    else {
      await user.type(await screen.findByRole('textbox', { name: '自行補充' }), '查原件');
      await user.click(screen.getByRole('button', { name: '送出全部回答' }));
    }
    await waitFor(() => expect(release).toBeDefined());
    view.unmount();
    await view.client.cancelQueries();
    view.client.removeQueries();
    act(() => {
      release?.(Response.json({ ...turn, status: 'running' }, { status: 202 }));
    });
    await waitFor(() =>
      expect(view.client.getMutationCache().getAll()[0]?.state.status).toBe('success'),
    );
    expect(view.client.getQueryCache().getAll()).toEqual([]);
  },
);
