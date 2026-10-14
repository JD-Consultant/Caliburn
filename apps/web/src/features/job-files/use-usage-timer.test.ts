import { stubHttp } from '../../test-http';
import { act, renderHook } from '@testing-library/react';
import { afterEach, beforeEach, expect, test, vi } from 'vitest';
import { useUsageTimer } from './use-usage-timer';

interface HeartbeatBody {
  elapsed_seconds: number;
}

const jobFileId = '10000000-0000-4000-8000-000000000001';

function baseFile(activeUsageSeconds: number) {
  return {
    job_file_id: jobFileId,
    display_name: '合成檔案',
    employee_name: '合成員工',
    name_revision: 1,
    created_at: '2026-10-10T00:00:00Z',
    active_usage_seconds: activeUsageSeconds,
  };
}

function heartbeatBody(options: RequestInit | undefined): HeartbeatBody {
  return JSON.parse((options?.body ?? '') as string) as HeartbeatBody;
}

let sendBeacon: ReturnType<typeof vi.fn>;

beforeEach(() => {
  vi.useFakeTimers();
  sendBeacon = vi.fn(() => true);
  Object.defineProperty(navigator, 'sendBeacon', { configurable: true, value: sendBeacon });
});
afterEach(() => {
  vi.useRealTimers();
  vi.unstubAllGlobals();
});

test('ticks the display once per second from the server-provided base', () => {
  stubHttp(() => Response.json(baseFile(40)));
  const { result } = renderHook(() => useUsageTimer(jobFileId, 40));
  expect(result.current).toBe(40);
  act(() => {
    vi.advanceTimersByTime(3_000);
  });
  expect(result.current).toBe(43);
});

test('sends an accumulated heartbeat every 15 seconds and resyncs to the authoritative total', async () => {
  const read = vi.fn<(path: string, options?: RequestInit) => Response>((_path, options) =>
    Response.json(baseFile(100 + heartbeatBody(options).elapsed_seconds)),
  );
  stubHttp(read);
  const { result } = renderHook(() => useUsageTimer(jobFileId, 0));
  await act(async () => {
    await vi.advanceTimersByTimeAsync(15_000);
  });
  expect(read).toHaveBeenCalledTimes(1);
  expect(heartbeatBody(read.mock.calls[0]?.[1])).toEqual({ elapsed_seconds: 15 });
  expect(result.current).toBe(115);
});

test('flushes the remaining pending seconds on unmount', async () => {
  const read = vi.fn<(path: string, options?: RequestInit) => Response>(() =>
    Response.json(baseFile(5)),
  );
  stubHttp(read);
  const { unmount } = renderHook(() => useUsageTimer(jobFileId, 0));
  act(() => {
    vi.advanceTimersByTime(5_000);
  });
  unmount();
  await vi.waitFor(() => expect(read).toHaveBeenCalledTimes(1));
  expect(heartbeatBody(read.mock.calls[0]?.[1])).toEqual({ elapsed_seconds: 5 });
});

test('uses sendBeacon instead of fetch when the page is actually being closed', () => {
  const read = vi.fn<(path: string, options?: RequestInit) => Response>(() =>
    Response.json(baseFile(0)),
  );
  stubHttp(read);
  renderHook(() => useUsageTimer(jobFileId, 0));
  act(() => {
    vi.advanceTimersByTime(7_000);
  });
  act(() => {
    window.dispatchEvent(new Event('pagehide'));
  });
  expect(read).not.toHaveBeenCalled();
  expect(sendBeacon).toHaveBeenCalledTimes(1);
  expect(sendBeacon.mock.calls[0]?.[0]).toBe(`/api/job-files/${jobFileId}/usage-heartbeat`);
});

test('does not send a heartbeat for less than one accumulated second', () => {
  const read = vi.fn<(path: string, options?: RequestInit) => Response>(() =>
    Response.json(baseFile(0)),
  );
  stubHttp(read);
  const { unmount } = renderHook(() => useUsageTimer(jobFileId, 0));
  unmount();
  expect(read).not.toHaveBeenCalled();
  expect(sendBeacon).not.toHaveBeenCalled();
});
