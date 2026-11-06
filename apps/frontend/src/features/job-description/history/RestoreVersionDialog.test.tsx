import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router';
import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import { jobDescription } from '../../../../tests/fixtures';
import { jobDescriptionOptions } from '../queries';
import { RestoreVersionDialog } from './RestoreVersionDialog';

const clients: QueryClient[] = [];
const current = { ...jobDescription, version: 3, job_title: '目前職務' };
const restored = { ...current, version: 4, job_title: '恢復的職務' };
const key = jobDescriptionOptions(current.workspace_id).queryKey;

beforeEach(() => {
  sessionStorage.clear();
  Object.defineProperty(HTMLDialogElement.prototype, 'showModal', {
    configurable: true,
    value: function (this: HTMLDialogElement) {
      this.open = true;
    },
  });
  Object.defineProperty(HTMLDialogElement.prototype, 'close', {
    configurable: true,
    value: function (this: HTMLDialogElement) {
      this.open = false;
    },
  });
});

afterEach(() => {
  clients.splice(0).forEach((cache) => cache.clear());
});

async function beginRestoration() {
  let respond: (response: Response) => void = () => {
    throw new Error('恢復請求尚未送出');
  };
  const fetch = vi.fn(
    () =>
      new Promise<Response>((resolve) => {
        respond = resolve;
      }),
  );
  vi.stubGlobal('fetch', fetch);
  const cache = new QueryClient({
    defaultOptions: {
      queries: { staleTime: 15_000, retry: false },
      mutations: { retry: false, networkMode: 'always' },
    },
  });
  clients.push(cache);
  cache.setQueryData(key, current);
  const view = render(
    <QueryClientProvider client={cache}>
      <MemoryRouter>
        <RestoreVersionDialog
          current={current}
          targetVersion={1}
          onClose={() => {}}
          onDraftsFound={() => {}}
          onVerificationRequired={() => {}}
        />
      </MemoryRouter>
    </QueryClientProvider>,
  );
  fireEvent.click(screen.getByRole('button', { name: '確認恢復' }));
  await waitFor(() => expect(fetch).toHaveBeenCalledTimes(1));
  return { cache, view, respond };
}

it('恢復途中離開畫面，成功回覆仍更新該 JD 快取', async () => {
  const { cache, view, respond } = await beginRestoration();
  view.unmount();
  await act(() => {
    respond(Response.json(restored));
    return Promise.resolve();
  });
  await waitFor(() => expect(cache.getQueryData(key)).toEqual(restored));
});

it('恢復途中離開畫面，未知結果仍使舊快取失效以便回來核對', async () => {
  const { cache, view, respond } = await beginRestoration();
  view.unmount();
  await act(() => {
    respond(
      Response.json(
        { detail: { code: 'jd_write_outcome_unknown', commit_status: 'unknown' } },
        { status: 500 },
      ),
    );
    return Promise.resolve();
  });
  await waitFor(() => expect(cache.getQueryState(key)?.isInvalidated).toBe(true));
});

it('該 JD 快取已移除時，較晚的恢復回覆不能使它復活', async () => {
  const { cache, view, respond } = await beginRestoration();
  view.unmount();
  cache.removeQueries({ queryKey: key, exact: true });
  await act(() => {
    respond(Response.json(restored));
    return Promise.resolve();
  });
  await waitFor(() =>
    expect(cache.getMutationCache().getAll()[0]?.state.status).toBe('success'),
  );
  expect(cache.getQueryState(key)).toBeUndefined();
});

it('較晚的恢復回覆不能覆蓋已確認的更新版本', async () => {
  const { cache, view, respond } = await beginRestoration();
  view.unmount();
  const newest = { ...restored, version: 5, job_title: '恢復後再編輯的職務' };
  cache.setQueryData(key, newest);
  await act(() => {
    respond(Response.json(restored));
    return Promise.resolve();
  });
  await waitFor(() =>
    expect(cache.getMutationCache().getAll()[0]?.state.status).toBe('success'),
  );
  expect(cache.getQueryData(key)).toEqual(newest);
});
