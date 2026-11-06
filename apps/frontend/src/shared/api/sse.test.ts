import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { InvalidResponseError } from './http';
import { streamTurnEvents } from './sse';
import type { TurnView } from './generated/types.gen';

const turn: TurnView = {
  workspace_id: '00112233-4455-6677-8899-aabbccddeeff',
  turn_id: '00112233-4455-6677-8899-aabbccddee00',
  status: 'running',
  input: '合成輸入',
  output: null,
  interrupts: [],
  usage: null,
  created_at: '2026-11-06T00:00:00Z',
  updated_at: '2026-11-06T00:00:00Z',
};

class TestEventSource extends EventTarget {
  static instances: TestEventSource[] = [];
  close = vi.fn();
  constructor(readonly url: string) {
    super();
    TestEventSource.instances.push(this);
  }
  emit(name: string, data: unknown): void {
    this.dispatchEvent(new MessageEvent(name, { data }));
  }
}

function subscribe() {
  const controller = new AbortController();
  const onEvent = vi.fn();
  const promise = streamTurnEvents('/workspaces/synthetic/turns/synthetic/events', {
    signal: controller.signal,
    onEvent,
  });
  const source = TestEventSource.instances.at(-1);
  if (!source) throw new Error('Expected an EventSource subscription');
  return { controller, onEvent, promise, source };
}

beforeEach(() => {
  TestEventSource.instances = [];
  vi.stubGlobal('EventSource', TestEventSource);
});
afterEach(() => vi.useRealTimers());

describe('正式具名 SSE 事件', () => {
  it('沿原生 EventSource 訂閱同源 URL，發布通過正式契約的事件', async () => {
    const { onEvent, promise, source } = subscribe();
    source.emit('text_delta', JSON.stringify({ model_step: 1, delta: '中文內容' }));
    source.emit('resync_required', JSON.stringify({ reason: 'slow_subscriber' }));
    expect(source.url).toBe('/api/workspaces/synthetic/turns/synthetic/events');
    expect(onEvent.mock.calls).toEqual([
      [{ event: 'text_delta', data: { model_step: 1, delta: '中文內容' } }],
      [{ event: 'resync_required', data: { reason: 'slow_subscriber' } }],
    ]);
    await expect(promise).resolves.toBeUndefined();
    expect(source.close).toHaveBeenCalledTimes(1);
  });

  it.each([
    ['message', '{}'],
    ['text_delta', 'not-json'],
    ['text_delta', '{"model_step":0,"delta":"invalid"}'],
    ['text_delta', '{"model_step":1,"delta":"invalid","extra":true}'],
    ['text_delta', { model_step: 1, delta: 'not a wire string' }],
  ])('壞事件關閉訂閱且不發布：%s %s', async (name, data) => {
    const { onEvent, promise, source } = subscribe();
    source.emit(name, data);
    await expect(promise).rejects.toBeInstanceOf(InvalidResponseError);
    expect(onEvent).not.toHaveBeenCalled();
    expect(source.close).toHaveBeenCalledTimes(1);
    source.emit('text_delta', '{"model_step":1,"delta":"late"}');
    expect(onEvent).not.toHaveBeenCalled();
  });

  it('斷線時立即關閉原生重連，交功能補讀，不開第二條訂閱', async () => {
    const { onEvent, promise, source } = subscribe();
    source.dispatchEvent(new Event('error'));
    await expect(promise).rejects.toBeInstanceOf(TypeError);
    expect(source.close).toHaveBeenCalledTimes(1);
    source.emit('text_delta', '{"model_step":1,"delta":"late"}');
    expect(onEvent).not.toHaveBeenCalled();
    expect(TestEventSource.instances).toHaveLength(1);
  });

  it.each(['completed', 'waiting_for_input', 'interrupted'] as const)(
    '正式 %s 狀態正常結束訂閱',
    async (status) => {
      const { onEvent, promise, source } = subscribe();
      source.emit('status', JSON.stringify(turn));
      expect(source.close).not.toHaveBeenCalled();
      source.emit('status', JSON.stringify({ ...turn, status }));
      await expect(promise).resolves.toBeUndefined();
      expect(onEvent).toHaveBeenCalledTimes(2);
      expect(source.close).toHaveBeenCalledTimes(1);
      source.dispatchEvent(new Event('error'));
      expect(source.close).toHaveBeenCalledTimes(1);
    },
  );

  it.each(['pending', 'completed'] as const)(
    '取消通知 %s 正常結束訂閱',
    async (status) => {
      const { onEvent, promise, source } = subscribe();
      source.emit('cancellation', JSON.stringify({ turn_id: turn.turn_id, status }));
      await expect(promise).resolves.toBeUndefined();
      expect(onEvent).toHaveBeenCalledTimes(1);
      expect(source.close).toHaveBeenCalledTimes(1);
    },
  );

  it('超過一般 HTTP timeout 後仍可收事件', async () => {
    vi.useFakeTimers();
    const { controller, onEvent, promise, source } = subscribe();
    await vi.advanceTimersByTimeAsync(30_000);
    expect(source.close).not.toHaveBeenCalled();
    source.emit('text_delta', '{"model_step":1,"delta":"still open"}');
    expect(onEvent).toHaveBeenCalledTimes(1);
    controller.abort();
    await expect(promise).rejects.toMatchObject({ name: 'AbortError' });
  });

  it('取消關閉訂閱，遲到事件不能污染新 scope', async () => {
    const { controller, onEvent, promise, source } = subscribe();
    controller.abort();
    await expect(promise).rejects.toMatchObject({ name: 'AbortError' });
    expect(source.close).toHaveBeenCalledTimes(1);
    source.emit('text_delta', '{"model_step":1,"delta":"late"}');
    expect(onEvent).not.toHaveBeenCalled();
  });

  it('已取消的呼叫不建立訂閱', async () => {
    const controller = new AbortController();
    controller.abort();
    await expect(
      streamTurnEvents('/events', {
        signal: controller.signal,
        onEvent: vi.fn(),
      }),
    ).rejects.toMatchObject({ name: 'AbortError' });
    expect(TestEventSource.instances).toHaveLength(0);
  });
});
