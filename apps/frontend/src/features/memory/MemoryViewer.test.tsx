import { useState } from 'react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { act, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, expect, it, vi } from 'vitest';
import { MemoryViewer } from './MemoryViewer';
import { memoryKeys } from './queries';

const workspaceId = '10000000-0000-4000-8000-000000000001';
const otherWorkspaceId = '10000000-0000-4000-8000-000000000002';
const situationId = '20000000-0000-4000-8000-000000000001';
const understandingId = '20000000-0000-4000-8000-000000000002';
const messageId = '30000000-0000-4000-8000-000000000001';
const empty = (id = workspaceId) => ({
  workspace_id: id,
  published_version: null,
  covered_through_message_id: null,
  items: [],
});
const map = (version = 3) => ({
  workspace_id: workspaceId,
  published_version: version,
  covered_through_message_id: messageId,
  items: [
    {
      item_id: situationId,
      kind: 'situation',
      title: `盤點情境 v${version}`,
      description: '每週核對存貨',
      changed_version: version,
    },
    {
      item_id: understandingId,
      kind: 'understanding',
      title: `盤點理解 v${version}`,
      description: '分析核對方法',
      changed_version: version,
    },
  ],
});
const item = (id = situationId, version = 3) => ({
  ...map(version).items.find((entry) => entry.item_id === id),
  workspace_id: workspaceId,
  published_version: version,
  body: `固定第 ${version} 版${id === situationId ? '情境' : '理解'}正文。`,
  source_ids: id === situationId ? [messageId] : [situationId],
});
const original = {
  message_id: messageId,
  turn_id: '40000000-0000-4000-8000-000000000001',
  position: 0,
  speaker: 'employee',
  kind: 'text',
  content: { text: '每週三逐項核對實際存貨。' },
  reply_to_message_id: null,
  created_at: '2026-11-06T00:00:00Z',
};
const clients: QueryClient[] = [];

function setup() {
  const cache = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  clients.push(cache);
  function Harness({ id }: { id: string }) {
    const [open, setOpen] = useState(false);
    return (
      <QueryClientProvider client={cache}>
        <button onClick={() => setOpen(true)}>Memory</button>
        <MemoryViewer workspaceId={id} open={open} onClose={() => setOpen(false)} />
      </QueryClientProvider>
    );
  }
  const view = render(<Harness id={workspaceId} />);
  return {
    ...view,
    cache,
    switchWorkspace: () => view.rerender(<Harness id={otherWorkspaceId} />),
  };
}

afterEach(() => clients.splice(0).forEach((cache) => cache.clear()));

it('只在開啟時查讀；無發布不假稱整理中；Escape歸還入口焦點', async () => {
  const fetch = vi.fn().mockResolvedValue(Response.json(empty()));
  vi.stubGlobal('fetch', fetch);
  setup();
  expect(fetch).not.toHaveBeenCalled();
  const opener = screen.getByRole('button', { name: 'Memory' });
  await userEvent.click(opener);
  expect(await screen.findByText('尚無已發布的 Memory。')).toBeVisible();
  expect(screen.queryByText(/正在整理/)).not.toBeInTheDocument();
  await userEvent.keyboard('{Escape}');
  await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument());
  expect(opener).toHaveFocus();
});

it('閱讀時新發布版移除原項目，返回導覽焦點落在重新讀取', async () => {
  vi.stubGlobal(
    'fetch',
    vi.fn((url: string) =>
      Promise.resolve(Response.json(url.endsWith('/memory') ? map() : item())),
    ),
  );
  const view = setup();
  await userEvent.click(screen.getByRole('button', { name: 'Memory' }));
  await userEvent.click(await screen.findByRole('button', { name: '盤點情境 v3' }));
  expect(await screen.findByText('固定第 3 版情境正文。')).toBeVisible();
  act(() => {
    view.cache.setQueryData(memoryKeys.map(workspaceId), { ...map(4), items: [] });
  });
  await userEvent.click(screen.getByRole('button', { name: '← 回到 Memory 導覽' }));
  expect(screen.getByRole('button', { name: '重新讀取 Memory' })).toHaveFocus();
});

it('正文與理解來源固定在所選發布版，更新導覽才選新版', async () => {
  let latest = 3;
  const fetch = vi.fn((url: string) => {
    const isItem = url.includes('/items/');
    const version = url.includes('/versions/4/') ? 4 : 3;
    return Promise.resolve(
      Response.json(
        isItem
          ? item(url.endsWith(understandingId) ? understandingId : situationId, version)
          : map(latest),
      ),
    );
  });
  vi.stubGlobal('fetch', fetch);
  setup();
  await userEvent.click(screen.getByRole('button', { name: 'Memory' }));
  const selected = await screen.findByRole('button', { name: '盤點理解 v3' });
  latest = 4;
  await userEvent.click(selected);
  expect(await screen.findByText('固定第 3 版理解正文。')).toBeVisible();
  await userEvent.click(screen.getByRole('button', { name: '工作情境來源 1' }));
  expect(await screen.findByText('固定第 3 版情境正文。')).toBeVisible();
  expect(screen.getByRole('button', { name: '← 回到工作理解' })).toHaveFocus();
  expect(fetch.mock.calls.at(-1)?.[0]).toBe(
    `/api/workspaces/${workspaceId}/memory/versions/3/items/${situationId}`,
  );
  await userEvent.click(screen.getByRole('button', { name: '← 回到工作理解' }));
  await userEvent.click(screen.getByRole('button', { name: '← 回到 Memory 導覽' }));
  expect(screen.getByRole('button', { name: '盤點理解 v3' })).toHaveFocus();
  await userEvent.click(screen.getByRole('button', { name: '重新讀取 Memory' }));
  await userEvent.click(await screen.findByRole('button', { name: '盤點情境 v4' }));
  expect(await screen.findByText('固定第 4 版情境正文。')).toBeVisible();
  expect(screen.queryByText('固定第 3 版情境正文。')).not.toBeInTheDocument();
});

it('情境來源查正式訪談原件，404保留不可讀提示與重試', async () => {
  let sourceAvailable = false;
  vi.stubGlobal(
    'fetch',
    vi.fn((url: string) => {
      if (url.includes('/interview/messages/'))
        return Promise.resolve(
          sourceAvailable ? Response.json(original) : Response.json({}, { status: 404 }),
        );
      return Promise.resolve(Response.json(url.endsWith('/memory') ? map() : item()));
    }),
  );
  setup();
  await userEvent.click(screen.getByRole('button', { name: 'Memory' }));
  await userEvent.click(await screen.findByRole('button', { name: '盤點情境 v3' }));
  await userEvent.click(await screen.findByRole('button', { name: '訪談來源 1' }));
  expect(await screen.findByRole('alert')).toHaveTextContent('已無法查讀');
  sourceAvailable = true;
  await userEvent.click(screen.getByRole('button', { name: '重新讀取來源' }));
  expect(await screen.findByText('每週三逐項核對實際存貨。')).toBeVisible();
});

it('導覽讀取失敗與無發布分開；快取內容保留並標示更新失敗', async () => {
  vi.stubGlobal(
    'fetch',
    vi
      .fn()
      .mockResolvedValueOnce(Response.json({}, { status: 503 }))
      .mockResolvedValueOnce(Response.json(map()))
      .mockResolvedValueOnce(Response.json({}, { status: 503 })),
  );
  setup();
  await userEvent.click(screen.getByRole('button', { name: 'Memory' }));
  expect(await screen.findByRole('alert')).toHaveTextContent('目前無法讀取');
  expect(screen.queryByText('尚無已發布的 Memory。')).not.toBeInTheDocument();
  await userEvent.click(screen.getByRole('button', { name: '重新讀取 Memory' }));
  expect(await screen.findByRole('button', { name: '盤點情境 v3' })).toBeVisible();
  await userEvent.click(screen.getByRole('button', { name: '重新讀取 Memory' }));
  expect(await screen.findByRole('alert')).toHaveTextContent('以下保留上次讀取的版本');
});

it('切換Workspace後，較晚的舊正文不會出現在新scope', async () => {
  let resolveItem: (value: Response) => void = () => {
    throw new Error('尚未讀取正文');
  };
  vi.stubGlobal(
    'fetch',
    vi.fn((url: string) => {
      if (url.includes(otherWorkspaceId))
        return Promise.resolve(Response.json(empty(otherWorkspaceId)));
      if (url.includes('/items/'))
        return new Promise<Response>((resolve) => {
          resolveItem = resolve;
        });
      return Promise.resolve(Response.json(map()));
    }),
  );
  const view = setup();
  await userEvent.click(screen.getByRole('button', { name: 'Memory' }));
  await userEvent.click(await screen.findByRole('button', { name: '盤點情境 v3' }));
  expect(await screen.findByRole('status')).toHaveTextContent('正在讀取 Memory 正文');
  view.switchWorkspace();
  expect(await screen.findByText('尚無已發布的 Memory。')).toBeVisible();
  await act(() => {
    resolveItem(Response.json(item()));
    return Promise.resolve();
  });
  expect(screen.queryByText('固定第 3 版情境正文。')).not.toBeInTheDocument();
});
