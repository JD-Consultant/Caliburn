import { StrictMode } from 'react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { act, render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, beforeEach, expect, test, vi } from 'vitest';
import type { ConsultantTurn } from '../../shared/api/generated/consultant-turn';
import type { ReasoningSummary } from '../../shared/api/generated/reasoning-summary';
import { InterviewComposer } from './InterviewComposer';
import { HistoricalTurnMessages } from './HistoricalTurnMessages';
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
  private listeners = new Map<string, EventListenerOrEventListenerObject | null>();
  constructor(readonly url: string) {
    super();
    TestEventSource.instances.push(this);
  }
  override addEventListener(type: string, callback: EventListenerOrEventListenerObject | null) {
    this.listeners.set(type, callback);
    super.addEventListener(type, callback);
  }
  close = vi.fn(() => {
    this.readyState = 2;
  });
  emit(value: unknown, type = 'commentary') {
    this.dispatchEvent(new MessageEvent(type, { data: JSON.stringify(value) }));
  }
  late(value: unknown, type = 'commentary') {
    const event = new MessageEvent(type, { data: JSON.stringify(value) });
    const listener = this.listeners.get(type);
    if (typeof listener === 'function') listener(event);
    else listener?.handleEvent(event);
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

function mount(
  read: () => ConsultantTurn = () => active,
  strict = false,
  readSummaries: () => ReasoningSummary[] | Promise<ReasoningSummary[]> = () => [],
) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  clients.push(client);
  const fetch = vi.fn<(path: string, options?: RequestInit) => Promise<Response>>(async (path) =>
    Response.json(path.endsWith('/reasoning-summaries') ? await readSummaries() : read()),
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
    `/api/job-files/${fileId}/consultant-turns/${executionId}/activity-stream`,
  );
  act(() => stream.emit(update));
  expect(await screen.findByText('正在核對')).toBeVisible();
  expect(screen.getByText('即時訊息（尚未保存）')).toBeVisible();
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

const summary: ReasoningSummary = {
  response_id: 'response-1',
  item_id: 'reasoning-1',
  output_index: 0,
  summary_index: 0,
  text: '先釐清範圍',
};

test('同一活動串流分開呈現摘要與公開訊息；同段替換，不洩露私有欄位或當成正式回答', async () => {
  mount();
  const stream = await currentStream();
  act(() => {
    stream.emit(update);
    stream.emit(summary, 'reasoning_summary');
    stream.emit({ ...summary, text: '先釐清範圍，再核對責任' }, 'reasoning_summary');
    stream.emit({ ...summary, text: '先釐清範圍，再核對責任' }, 'reasoning_summary');
    stream.emit(
      { ...summary, summary_index: 1, text: '<script>第二段摘要</script>' },
      'reasoning_summary',
    );
    stream.emit({ ...summary, encrypted_content: 'secret', text: '不可公開' }, 'reasoning_summary');
  });
  expect(await screen.findByText('先釐清範圍，再核對責任')).toBeVisible();
  expect(screen.getAllByText('先釐清範圍，再核對責任')).toHaveLength(1);
  expect(screen.getByText('<script>第二段摘要</script>')).toBeVisible();
  expect(screen.getByText('正在核對')).toBeVisible();
  expect(screen.queryByText('不可公開')).not.toBeInTheDocument();
  expect(document.querySelector('script')).toBeNull();
  expect(screen.queryByText('這次訪談已完成並保存。')).not.toBeInTheDocument();
  expect(JSON.stringify(localStorage)).not.toContain('釐清範圍');
});

test('處理中的內容歸屬於職務顧問，與之後那則回覆同一位作者', async () => {
  mount();
  const stream = await currentStream();
  act(() => {
    stream.emit(update);
    stream.emit(summary, 'reasoning_summary');
  });
  const reply = await screen.findByRole('group', { name: '職務顧問' });
  expect(within(reply).getByText('先釐清範圍')).toBeVisible();
  expect(within(reply).getByText('正在核對')).toBeVisible();
});

test.each(['paused', 'failed'] as const)('%s 的處理仍是顧問尚未完成的那則回覆', async (status) => {
  mount(() => ({ ...active, status, allowed_controls: [] }));
  const reply = await screen.findByRole('group', { name: '職務顧問' });
  expect(within(reply).getByText('推理摘要')).toBeVisible();
});

test('已完成的處理已在歷史訪談，不再另列一則顧問回覆', async () => {
  mount(() => ({ ...active, status: 'completed', allowed_controls: [] }));
  expect(await screen.findByText('這次訪談已完成並保存。')).toBeVisible();
  expect(screen.queryByRole('group', { name: '職務顧問' })).not.toBeInTheDocument();
});

test('重連讀回已保存摘要，原件優先於遲到片段，且只發讀取請求', async () => {
  let savedSummaries: ReasoningSummary[] = [];
  const { fetch } = mount(
    () => active,
    false,
    () => savedSummaries,
  );
  const stream = await currentStream();
  act(() => stream.emit(summary, 'reasoning_summary'));
  expect(await screen.findByText(summary.text)).toBeVisible();
  savedSummaries = [{ ...summary, text: '保存完成的原摘要' }];
  act(() => {
    stream.dispatchEvent(new Event('open'));
  });
  expect(await screen.findByText('保存完成的原摘要')).toBeVisible();
  act(() => stream.emit({ ...summary, text: '遲到摘要' }, 'reasoning_summary'));
  expect(screen.queryByText('遲到摘要')).not.toBeInTheDocument();
  expect(screen.getAllByText('保存完成的原摘要')).toHaveLength(1);
  expect(fetch.mock.calls.every(([, options]) => options?.method !== 'POST')).toBe(true);
});

test('重連取消較早尚未返回的摘要查詢，重新讀取已保存內容，不被舊空結果覆蓋', async () => {
  let releaseEarlier: ((value: ReasoningSummary[]) => void) | undefined;
  const earlier = new Promise<ReasoningSummary[]>((resolve) => {
    releaseEarlier = resolve;
  });
  const readSummaries = vi
    .fn<() => ReasoningSummary[] | Promise<ReasoningSummary[]>>()
    .mockReturnValueOnce(earlier)
    .mockReturnValue([{ ...summary, text: '重連前已保存的摘要' }]);
  const { fetch } = mount(() => active, false, readSummaries);
  const stream = await currentStream();
  await waitFor(() => expect(readSummaries).toHaveBeenCalledTimes(1));
  const earlierSignal = fetch.mock.calls.find(([path]) =>
    path.endsWith('/reasoning-summaries'),
  )?.[1]?.signal;
  act(() => stream.emit(summary, 'reasoning_summary'));
  expect(await screen.findByText(summary.text)).toBeVisible();
  act(() => {
    stream.dispatchEvent(new Event('open'));
  });
  await waitFor(() => expect(earlierSignal?.aborted).toBe(true));
  expect(await screen.findByText('重連前已保存的摘要')).toBeVisible();
  await act(async () => {
    releaseEarlier?.([]);
    await earlier;
  });
  expect(readSummaries).toHaveBeenCalledTimes(2);
  expect(screen.getByText('重連前已保存的摘要')).toBeVisible();
  expect(screen.queryByText('這次處理沒有已保存的推理摘要。')).not.toBeInTheDocument();
});

test('完成後關閉串流並移除底部紀錄；原摘要由歷史回答按需讀回', async () => {
  let status = active;
  let savedSummaries: ReasoningSummary[] = [];
  const { client } = mount(
    () => status,
    false,
    () => savedSummaries,
  );
  const stream = await currentStream();
  act(() => stream.emit(summary, 'reasoning_summary'));
  expect(await screen.findByText(summary.text)).toBeVisible();
  savedSummaries = [{ ...summary, text: '已保存終態摘要' }];
  status = { ...active, status: 'completed', allowed_controls: [] };
  await act(() =>
    client.invalidateQueries({ queryKey: consultantTurnQuery(fileId, executionId).queryKey }),
  );
  await waitFor(() => expect(stream.close).toHaveBeenCalled());
  expect(screen.queryByText(summary.text)).not.toBeInTheDocument();
  expect(screen.queryByText('推理摘要')).not.toBeInTheDocument();
  expect(screen.queryByText('回看本次處理過程')).not.toBeInTheDocument();

  render(
    <QueryClientProvider client={client}>
      <HistoricalTurnMessages jobFileId={fileId} executionId={executionId} />
    </QueryClientProvider>,
  );
  await userEvent.click(screen.getByRole('button', { name: '處理紀錄' }));
  const saved = await screen.findByText('已保存終態摘要');
  expect(saved).not.toBeVisible();
  await userEvent.click(screen.getByText('推理摘要'));
  expect(saved).toBeVisible();
  expect(screen.queryByText(summary.text)).not.toBeInTheDocument();
});

test.each(['cancelled', 'failed', 'paused'] as const)(
  '%s 後讀回完整摘要，丟棄未保存片段，終態收合但仍可回看',
  async (outcome) => {
    let status = active;
    let savedSummaries: ReasoningSummary[] = [];
    const { client } = mount(
      () => status,
      false,
      () => savedSummaries,
    );
    const stream = await currentStream();
    act(() => stream.emit(summary, 'reasoning_summary'));
    expect(await screen.findByText(summary.text)).toBeVisible();
    savedSummaries = [{ ...summary, text: '已保存終態摘要' }];
    status = { ...active, status: outcome, allowed_controls: [] };
    await act(() =>
      client.invalidateQueries({ queryKey: consultantTurnQuery(fileId, executionId).queryKey }),
    );
    const content = await screen.findByText('已保存終態摘要');
    expect(content.closest('details')?.open).toBe(outcome === 'paused');
    expect(screen.queryByText(summary.text)).not.toBeInTheDocument();
    expect(stream.close).toHaveBeenCalled();
  },
);

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
  act(() => first.late({ ...summary, text: '舊檔摘要' }, 'reasoning_summary'));
  expect(first.close).toHaveBeenCalled();
  expect(second.url).toContain(`/job-files/${otherFile}/consultant-turns/${otherExecution}/`);
  expect(screen.queryByText(/正在核對$|舊檔晚到|舊檔摘要/)).not.toBeInTheDocument();
});
