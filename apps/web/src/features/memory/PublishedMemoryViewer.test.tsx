import { stubHttp } from '../../test-http';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { cleanup, render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, expect, test, vi } from 'vitest';
import { PublishedMemoryViewer } from './PublishedMemoryViewer';

const file = '10000000-0000-4000-8000-000000000001';
const secondFile = '10000000-0000-4000-8000-000000000002';
const first = '20000000-0000-4000-8000-000000000001';
const second = '20000000-0000-4000-8000-000000000002';
const object = '30000000-0000-4000-8000-000000000001';
const empty = {
  snapshot_id: null,
  covered_through_sequence: 0,
  work_situations: [],
  work_understandings: [],
};
const map = (snapshot = first) => ({
  snapshot_id: snapshot,
  covered_through_sequence: snapshot === first ? 2 : 4,
  work_situations: [
    {
      object_id: object,
      title: snapshot === first ? '初版盤點' : '新版盤點',
      description: '逐項核對存貨。',
    },
  ],
  work_understandings: [],
});
const body = (snapshot = first) => ({
  snapshot_id: snapshot,
  object_id: object,
  layer: 'work_situation',
  title: snapshot === first ? '初版盤點正文' : '新版盤點正文',
  description: '保存的描述',
  body: snapshot === first ? '固定初版內容。' : '新版內容。',
});
const clients: QueryClient[] = [];

function setup() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  clients.push(client);
  const view = (id: string) => (
    <QueryClientProvider client={client}>
      <PublishedMemoryViewer jobFileId={id} />
    </QueryClientProvider>
  );
  const rendered = render(view(file));
  return { ...rendered, switchFile: () => rendered.rerender(view(secondFile)) };
}

afterEach(() => {
  cleanup();
  clients.splice(0).forEach((client) => client.clear());
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

test('opens on demand, shows no publication, and refreshes publication on reopening with focus restored', async () => {
  const fetch = vi
    .fn()
    .mockResolvedValueOnce(Response.json(empty))
    .mockResolvedValueOnce(Response.json(map()));
  stubHttp(fetch);
  setup();
  expect(fetch).not.toHaveBeenCalled();
  const open = screen.getByRole('button', { name: 'Memory' });
  await userEvent.click(open);
  expect(await screen.findByText('尚無已發布的 Memory。')).toBeVisible();
  await userEvent.keyboard('{Escape}');
  await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument());
  expect(open).toHaveFocus();
  await userEvent.click(open);
  expect(await screen.findByRole('button', { name: '初版盤點' })).toBeVisible();
  expect(screen.getByText('涵蓋至第 2 則訪談。')).toBeVisible();
  expect(fetch).toHaveBeenCalledTimes(2);
});

test('body reads stay pinned while a later publication exists; explicit navigation refresh selects the new version', async () => {
  let latest = first;
  const fetch = vi.fn((url: string, options?: RequestInit) => {
    expect(options?.method).not.toBe('POST');
    return Promise.resolve(
      Response.json(
        url.endsWith('/memory') ? map(latest) : body(url.includes(first) ? first : second),
      ),
    );
  });
  stubHttp(fetch);
  setup();
  await userEvent.click(screen.getByRole('button', { name: 'Memory' }));
  const initial = await screen.findByRole('button', { name: '初版盤點' });
  latest = second;
  await userEvent.click(initial);
  expect(await screen.findByText('固定初版內容。')).toBeVisible();
  expect(screen.getByText(`版本：${first}`)).toBeVisible();
  expect(fetch.mock.calls.at(-1)?.[0]).toBe(
    `/api/job-files/${file}/memory/${first}/objects/${object}`,
  );
  await userEvent.click(screen.getByRole('button', { name: '← 回到 Memory 導覽' }));
  await userEvent.click(screen.getByRole('button', { name: '重新讀取 Memory' }));
  await userEvent.click(await screen.findByRole('button', { name: '新版盤點' }));
  expect(await screen.findByText('新版內容。')).toBeVisible();
  expect(screen.queryByText('固定初版內容。')).not.toBeInTheDocument();
  expect(screen.getByText(`版本：${second}`)).toBeVisible();
});

test('read failure is not an empty memory and a cached failure is explicitly labeled', async () => {
  const fetch = vi
    .fn()
    .mockResolvedValueOnce(Response.json({}, { status: 503 }))
    .mockResolvedValueOnce(Response.json(map()))
    .mockResolvedValueOnce(Response.json({}, { status: 503 }));
  stubHttp(fetch);
  setup();
  await userEvent.click(screen.getByRole('button', { name: 'Memory' }));
  expect(await screen.findByRole('alert')).toBeVisible();
  expect(screen.queryByText('尚無已發布的 Memory。')).not.toBeInTheDocument();
  await userEvent.click(screen.getByRole('button', { name: '重新讀取 Memory' }));
  expect(await screen.findByRole('button', { name: '初版盤點' })).toBeVisible();
  await userEvent.click(screen.getByRole('button', { name: '重新讀取 Memory' }));
  expect(await screen.findByRole('alert')).toHaveTextContent('以下保留上次讀取的版本');
  expect(screen.getByRole('button', { name: '初版盤點' })).toBeVisible();
});

test('switching files closes the old dialog and never shows the old file memory', async () => {
  stubHttp(
    vi.fn((url: string) =>
      Promise.resolve(Response.json(url.includes(secondFile) ? empty : map())),
    ),
  );
  const app = setup();
  await userEvent.click(screen.getByRole('button', { name: 'Memory' }));
  expect(await screen.findByRole('button', { name: '初版盤點' })).toBeVisible();
  app.switchFile();
  expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
  await userEvent.click(screen.getByRole('button', { name: 'Memory' }));
  const dialog = screen.getByRole('dialog', { name: '目前已發布的 Memory' });
  expect(await within(dialog).findByText('尚無已發布的 Memory。')).toBeVisible();
  expect(within(dialog).queryByText('初版盤點')).not.toBeInTheDocument();
});

test('a wrong snapshot body is refused and only explicit retry adopts the matching original', async () => {
  stubHttp(
    vi
      .fn()
      .mockResolvedValueOnce(Response.json(map()))
      .mockResolvedValueOnce(Response.json(body(second)))
      .mockResolvedValueOnce(Response.json(body())),
  );
  setup();
  await userEvent.click(screen.getByRole('button', { name: 'Memory' }));
  await userEvent.click(await screen.findByRole('button', { name: '初版盤點' }));
  expect(await screen.findByRole('alert')).toHaveTextContent('尚未採用這份結果');
  expect(screen.queryByText('新版內容。')).not.toBeInTheDocument();
  await userEvent.click(screen.getByRole('button', { name: '重新讀取正文' }));
  expect(await screen.findByText('固定初版內容。')).toBeVisible();
});
