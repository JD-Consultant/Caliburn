import { StrictMode } from 'react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { act, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, expect, test, vi } from 'vitest';
import type { ConsultantTurn } from '../../shared/api/generated/consultant-turn';
import { InterviewComposer } from './InterviewComposer';
import { consultantTurnQuery, readTurnHint, retainTurnHint } from './interview-turn-api';

const fileId = '10000000-0000-4000-8000-000000000001';
const executionId = '20000000-0000-4000-8000-000000000002';
const commandId = '30000000-0000-4000-8000-000000000003';
const otherFile = '40000000-0000-4000-8000-000000000004';
const otherExecution = '50000000-0000-4000-8000-000000000005';
const active: ConsultantTurn = {
  job_file_id: fileId,
  execution_id: executionId,
  status: 'active',
  pause_requested: false,
  input_text: '僅伺服器原輸入',
  allowed_controls: ['pause', 'cancel'],
  commentary: [],
  candidate: null,
};
const update = {
  job_file_id: fileId,
  execution_id: executionId,
  response_id: 'response-1',
  message_id: 'message-1',
  text: '正在核對',
};

class TestEventSource extends EventTarget {
  static instances: TestEventSource[] = [];
  readyState = 0;
  private lastCommentary: EventListenerOrEventListenerObject | null = null;
  constructor(readonly url: string) {
    super();
    TestEventSource.instances.push(this);
  }
  override addEventListener(type: string, callback: EventListenerOrEventListenerObject | null) {
    if (type === 'commentary') this.lastCommentary = callback;
    super.addEventListener(type, callback);
  }
  close = vi.fn(() => {
    this.readyState = 2;
  });
  emit(value: unknown, type = 'commentary') {
    this.dispatchEvent(new MessageEvent(type, { data: JSON.stringify(value) }));
  }
  late(value: unknown) {
    const event = new MessageEvent('commentary', { data: JSON.stringify(value) });
    if (typeof this.lastCommentary === 'function') this.lastCommentary(event);
    else this.lastCommentary?.handleEvent(event);
  }
}

const clients: QueryClient[] = [];
beforeEach(() => {
  localStorage.clear();
  TestEventSource.instances = [];
  vi.stubGlobal('EventSource', TestEventSource);
  retainTurnHint(fileId, { command_id: commandId, execution_id: executionId });
});
afterEach(() => {
  clients.splice(0).forEach((client) => client.clear());
  vi.unstubAllGlobals();
});

function mount(read: () => ConsultantTurn = () => active, strict = false) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  clients.push(client);
  const fetch = vi.fn<(path: string, options?: RequestInit) => Promise<Response>>(() =>
    Promise.resolve(Response.json(read())),
  );
  vi.stubGlobal('fetch', fetch);
  const content = (id: string) => (
    <QueryClientProvider client={client}>
      {strict ? (
        <StrictMode>
          <InterviewComposer jobFileId={id} />
        </StrictMode>
      ) : (
        <InterviewComposer jobFileId={id} />
      )}
    </QueryClientProvider>
  );
  const view = render(content(fileId));
  return { ...view, client, fetch, changeFile: (id: string) => view.rerender(content(id)) };
}

async function currentStream() {
  await waitFor(() =>
    expect(TestEventSource.instances.filter((item) => item.readyState !== 2)).toHaveLength(1),
  );
  const stream = TestEventSource.instances.find((item) => item.readyState !== 2);
  if (!stream) throw new Error('Expected one active commentary subscription');
  return stream;
}

test('未查回 active 或初次查回已完成時不建立訂閱', async () => {
  mount(() => ({ ...active, status: 'completed', allowed_controls: [] }));
  expect(TestEventSource.instances).toHaveLength(0);
  expect(await screen.findByText('這次訪談已完成並保存。')).toBeVisible();
  expect(TestEventSource.instances).toHaveLength(0);
});

test('累積 commentary 僅更新未保存顯示，不追加重複全文或接受私有及錯 scope 事件', async () => {
  mount();
  const stream = await currentStream();
  expect(stream.url).toBe(
    `/api/job-files/${fileId}/consultant-turns/${executionId}/commentary-stream`,
  );
  act(() => stream.emit(update));
  expect(await screen.findByText('正在核對')).toBeVisible();
  expect(screen.getByText(/即時公開訊息（尚未保存/)).toBeVisible();
  act(() => {
    stream.emit({ ...update, text: '正在核對職責' });
    stream.emit({ ...update, text: '正在核對職責' });
    stream.emit({ ...update, job_file_id: otherFile, text: 'foreign-file' });
    stream.emit({ ...update, execution_id: otherExecution, text: 'foreign-turn' });
    stream.emit({ ...update, encrypted_reasoning: 'private', text: 'private-text' });
    stream.emit({ ...update, text: 'sdk-event' }, 'response.output_text.delta');
  });
  expect(screen.getAllByText('正在核對職責')).toHaveLength(1);
  expect(
    screen.queryByText(/foreign-file|foreign-turn|private-text|sdk-event/),
  ).not.toBeInTheDocument();
  expect(JSON.stringify(localStorage)).not.toContain('正在核對');
  act(() => stream.emit({ ...update, text: '<script>不執行</script>' }));
  expect(screen.getByText('<script>不執行</script>')).toBeVisible();
  expect(document.querySelector('script')).toBeNull();
});

test('已保存同身分訊息取代暫態，晚到串流不得覆蓋已保存文字', async () => {
  let status = active;
  const { client } = mount(() => status);
  const stream = await currentStream();
  act(() => stream.emit(update));
  status = {
    ...active,
    commentary: [{ response_id: 'response-1', message_id: 'message-1', text: '已保存完整訊息' }],
  };
  await act(() =>
    client.invalidateQueries({ queryKey: consultantTurnQuery(fileId, executionId).queryKey }),
  );
  expect(await screen.findByText('已保存完整訊息')).toBeVisible();
  act(() => stream.emit({ ...update, text: '晚到片段' }));
  expect(screen.getAllByText('已保存完整訊息')).toHaveLength(1);
  expect(screen.queryByText(/正在核對|晚到片段/)).not.toBeInTheDocument();
  status = {
    ...status,
    commentary: [{ response_id: 'response-1', message_id: 'message-1', text: '' }],
  };
  await act(() =>
    client.invalidateQueries({ queryKey: consultantTurnQuery(fileId, executionId).queryKey }),
  );
  await waitFor(() => expect(screen.queryByText('已保存完整訊息')).not.toBeInTheDocument());
  act(() => stream.emit({ ...update, text: '不得補回已保存空字串' }));
  expect(screen.queryByText('不得補回已保存空字串')).not.toBeInTheDocument();
});

test('斷線及重新連線只核對 status，不送 input/cancel、不改 command 或假完成', async () => {
  const { fetch, unmount } = mount();
  const stream = await currentStream();
  const hint = readTurnHint(fileId);
  act(() => {
    stream.readyState = 0;
    stream.dispatchEvent(new Event('error'));
    stream.emit(update, 'done');
  });
  expect(await screen.findByText(/即時顯示中斷/)).toBeVisible();
  expect(screen.getByRole('button', { name: '取消處理' })).toBeVisible();
  expect(screen.queryByText('這次訪談已完成並保存。')).not.toBeInTheDocument();
  act(() => {
    stream.readyState = 1;
    stream.dispatchEvent(new Event('open'));
  });
  expect(screen.queryByText(/即時顯示中斷/)).not.toBeInTheDocument();
  act(() => {
    stream.readyState = 2;
    stream.dispatchEvent(new Event('error'));
  });
  expect(screen.getByRole('button', { name: '取消處理' })).toBeVisible();
  expect(screen.queryByText('這次訪談已完成並保存。')).not.toBeInTheDocument();
  expect(TestEventSource.instances).toHaveLength(1);
  expect(readTurnHint(fileId)).toEqual(hint);
  unmount();
  expect(stream.close).toHaveBeenCalled();
  expect(fetch.mock.calls.every(([, options]) => options?.method !== 'POST')).toBe(true);
});

test.each(['completed', 'cancelled', 'failed', 'paused'] as const)(
  '%s status 才關閉訂閱並剔除遲來瞬時文字',
  async (outcome) => {
    let status = active;
    const { client, fetch } = mount(() => status);
    const stream = await currentStream();
    act(() => stream.emit(update));
    status = { ...active, status: outcome, allowed_controls: [] };
    await act(() =>
      client.invalidateQueries({ queryKey: consultantTurnQuery(fileId, executionId).queryKey }),
    );
    await waitFor(() => expect(stream.close).toHaveBeenCalled());
    act(() => stream.late({ ...update, text: '晚到訊息' }));
    expect(stream.close).toHaveBeenCalled();
    expect(screen.queryByText(/正在核對$|晚到訊息/)).not.toBeInTheDocument();
    expect(screen.queryByText('這次訪談已完成並保存。') !== null).toBe(outcome === 'completed');
    expect(fetch.mock.calls.every(([, options]) => options?.method !== 'POST')).toBe(true);
  },
);

test('StrictMode 與換檔只有一條有效訂閱，舊檔 callback 不污染新檔', async () => {
  let status = active;
  const { changeFile } = mount(() => status, true);
  const first = await currentStream();
  act(() => first.emit(update));
  retainTurnHint(otherFile, { command_id: commandId, execution_id: otherExecution });
  status = { ...active, job_file_id: otherFile, execution_id: otherExecution };
  changeFile(otherFile);
  await waitFor(() =>
    expect(TestEventSource.instances.some((item) => item.url.includes(otherExecution))).toBe(true),
  );
  const second = await currentStream();
  act(() => first.late({ ...update, text: '舊檔晚到' }));
  expect(first.close).toHaveBeenCalled();
  expect(second.url).toContain(`/job-files/${otherFile}/consultant-turns/${otherExecution}/`);
  expect(screen.queryByText(/正在核對$|舊檔晚到/)).not.toBeInTheDocument();
});
