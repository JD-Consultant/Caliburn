/** The page can drive the source sheet, e.g. a badge on a JD item opens it for that item only. */
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, expect, test, vi } from 'vitest';
import { SourceViewer } from './SourceViewer';

const fileId = '10000000-0000-4000-8000-000000000001';
const revisionId = '20000000-0000-4000-8000-000000000002';
const first = '30000000-0000-4000-8000-000000000003';
const second = '30000000-0000-4000-8000-000000000004';
const third = '30000000-0000-4000-8000-000000000005';
const basePath = `/api/job-files/${fileId}/jd/sources`;
const sources = {
  revision_id: revisionId,
  references: [
    {
      citation_id: first,
      target_label: '任務：處理例外',
      source_kind: 'interview',
      source_label: '訪談序號 2 · 員工',
      needs_recheck: false,
      jd_changed: false,
      source_changed: false,
    },
    {
      citation_id: second,
      target_label: '任務：處理例外',
      source_kind: 'interview',
      source_label: '訪談序號 4 · 員工',
      needs_recheck: false,
      jd_changed: false,
      source_changed: false,
    },
    {
      citation_id: third,
      target_label: '任務：另一項',
      source_kind: 'interview',
      source_label: '訪談序號 6 · 員工',
      needs_recheck: false,
      jd_changed: false,
      source_changed: false,
    },
  ],
};
const clients: QueryClient[] = [];

function serve() {
  const fetch = vi.fn((path: string) => {
    if (path === basePath) return Promise.resolve(Response.json(sources));
    if (path === `${basePath}/${first}?revision_id=${revisionId}`)
      return Promise.resolve(
        Response.json({
          revision_id: revisionId,
          citation_id: first,
          content: {
            kind: 'interview',
            interview_sequence: 2,
            speaker: 'employee',
            interview_text: '員工原話',
          },
        }),
      );
    throw new Error(`Unexpected request: ${path}`);
  });
  vi.stubGlobal('fetch', fetch);
  return fetch;
}

function renderViewer(props: Partial<Parameters<typeof SourceViewer>[0]> = {}) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  clients.push(client);
  return render(
    <QueryClientProvider client={client}>
      <SourceViewer jobFileId={fileId} {...props} />
    </QueryClientProvider>,
  );
}

afterEach(() => {
  clients.splice(0).forEach((client) => client.clear());
  vi.unstubAllGlobals();
});

test('a controlled sheet lists only the chosen item’s citations and can return to all', async () => {
  serve();
  const onClearFilter = vi.fn();
  renderViewer({
    open: true,
    onOpenChange: vi.fn(),
    onlyCitationIds: [first, second],
    onClearFilter,
  });
  expect(await screen.findByRole('button', { name: '訪談序號 4 · 員工' })).toBeVisible();
  expect(screen.getByRole('button', { name: '訪談序號 2 · 員工' })).toBeVisible();
  expect(screen.queryByRole('button', { name: '訪談序號 6 · 員工' })).not.toBeInTheDocument();
  expect(screen.getByText(/只顯示所選 JD 項目的來源/)).toBeVisible();

  await userEvent.click(screen.getByRole('button', { name: '顯示全部來源' }));
  expect(onClearFilter).toHaveBeenCalledTimes(1);
});

test('a filter that leaves exactly one citation opens its fixed content at once; Back shows the filtered list', async () => {
  serve();
  const onClearFilter = vi.fn();
  renderViewer({ open: true, onOpenChange: vi.fn(), onlyCitationIds: [first], onClearFilter });
  expect(await screen.findByText('員工原話')).toBeVisible();

  await userEvent.click(screen.getByRole('button', { name: '返回來源列表' }));
  expect(await screen.findByRole('button', { name: '訪談序號 2 · 員工' })).toBeVisible();
  expect(screen.queryByRole('button', { name: '訪談序號 4 · 員工' })).not.toBeInTheDocument();
  await userEvent.click(screen.getByRole('button', { name: '顯示全部來源' }));
  expect(onClearFilter).toHaveBeenCalledTimes(1);
});

test('closing is reported to the page rather than hidden internally', async () => {
  serve();
  const onOpenChange = vi.fn();
  renderViewer({ open: true, onOpenChange });
  await userEvent.click(await screen.findByRole('button', { name: '關閉來源面板' }));
  expect(onOpenChange).toHaveBeenCalledWith(false);
});

test('without a controlling page it still opens and closes itself', async () => {
  serve();
  renderViewer();
  expect(screen.queryByRole('button', { name: '關閉來源面板' })).not.toBeInTheDocument();
  await userEvent.click(screen.getByRole('button', { name: '正式 JD 來源（唯讀）' }));
  await userEvent.click(await screen.findByRole('button', { name: '關閉來源面板' }));
  expect(screen.queryByRole('button', { name: '關閉來源面板' })).not.toBeInTheDocument();
});
