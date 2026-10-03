/** The sheet is a list you drill into (Fluent drawer / Material side sheet): one view at a time, a Back control, focus kept. */
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, expect, test, vi } from 'vitest';
import { SourceViewer } from './SourceViewer';

const fileId = '10000000-0000-4000-8000-000000000001';
const revisionId = '20000000-0000-4000-8000-000000000002';
const first = '30000000-0000-4000-8000-000000000003';
const second = '30000000-0000-4000-8000-000000000004';
const basePath = `/api/job-files/${fileId}/jd/sources`;
const reference = {
  target_label: '任務：處理例外',
  source_kind: 'interview',
  needs_recheck: false,
  jd_changed: false,
  source_changed: false,
};
const sources = {
  revision_id: revisionId,
  references: [
    { ...reference, citation_id: first, source_label: '訪談序號 2 · 員工' },
    {
      ...reference,
      citation_id: second,
      source_label: '訪談序號 4 · 員工',
      source_kind: 'work_understanding',
      needs_recheck: true,
      jd_changed: true,
    },
  ],
};
const interview = (citation: string, text: string) => ({
  revision_id: revisionId,
  citation_id: citation,
  content: { kind: 'interview', interview_sequence: 2, speaker: 'employee', interview_text: text },
});
const clients: QueryClient[] = [];

function serve() {
  const fetch = vi.fn((path: string) => {
    if (path === basePath) return Promise.resolve(Response.json(sources));
    if (path === `${basePath}/${first}?revision_id=${revisionId}`)
      return Promise.resolve(Response.json(interview(first, '第一則員工原話')));
    if (path === `${basePath}/${second}?revision_id=${revisionId}`)
      return Promise.resolve(Response.json(interview(second, '第二則員工原話')));
    if (path === `${basePath}/${second}/changes?revision_id=${revisionId}`)
      return Promise.resolve(
        Response.json({
          revision_id: revisionId,
          citation_id: second,
          jd_markdown: 'JD 差異正文',
          source_markdown: null,
        }),
      );
    throw new Error(`Unexpected request: ${path}`);
  });
  vi.stubGlobal('fetch', fetch);
  return fetch;
}

function renderSheet() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  clients.push(client);
  return render(
    <QueryClientProvider client={client}>
      <SourceViewer jobFileId={fileId} open onOpenChange={vi.fn()} />
    </QueryClientProvider>,
  );
}

afterEach(() => {
  clients.splice(0).forEach((client) => client.clear());
  vi.unstubAllGlobals();
});

test('opening a source replaces the list with that source; Back returns to the list with focus on the same row', async () => {
  serve();
  renderSheet();
  await userEvent.click(await screen.findByRole('button', { name: '訪談序號 2 · 員工' }));

  expect(await screen.findByText('第一則員工原話')).toBeVisible();
  expect(screen.queryByRole('button', { name: '訪談序號 4 · 員工' })).not.toBeInTheDocument();

  await userEvent.click(screen.getByRole('button', { name: '返回來源列表' }));
  const row = await screen.findByRole('button', { name: '訪談序號 2 · 員工' });
  expect(screen.queryByText('第一則員工原話')).not.toBeInTheDocument();
  expect(screen.queryByRole('button', { name: '返回來源列表' })).not.toBeInTheDocument();
  expect(row).toHaveFocus();
});

test('the detail says which JD item the source supports', async () => {
  serve();
  renderSheet();
  await userEvent.click(await screen.findByRole('button', { name: '訪談序號 2 · 員工' }));
  const detail = await screen.findByRole('region', { name: '訪談序號 2 · 員工' });
  expect(within(detail).getByText('任務：處理例外')).toBeVisible();
});

test('a row keeps its source label as its name; the recheck reason is its description', async () => {
  serve();
  renderSheet();
  const row = await screen.findByRole('button', { name: '訪談序號 4 · 員工' });
  expect(row).toHaveAccessibleDescription('JD 已修改');
  expect(screen.getByRole('button', { name: '訪談序號 2 · 員工' })).toHaveAccessibleDescription('');
});

test('a source that needs recheck has Source and Changes tabs; the row action opens Changes without reading the body', async () => {
  const fetch = serve();
  renderSheet();
  await screen.findByRole('button', { name: '訪談序號 4 · 員工' });
  expect(fetch).toHaveBeenCalledTimes(1);

  await userEvent.click(screen.getByRole('button', { name: '查看差異' }));
  expect(await screen.findByRole('tab', { name: '差異', selected: true })).toBeVisible();
  expect(await screen.findByText('JD 差異正文')).toBeVisible();
  expect(fetch).toHaveBeenCalledTimes(2);

  await userEvent.click(screen.getByRole('tab', { name: '來源正文' }));
  expect(await screen.findByText('第二則員工原話')).toBeVisible();
  expect(fetch).toHaveBeenCalledTimes(3);
});

test('an unchanged source has no tabs', async () => {
  serve();
  renderSheet();
  await userEvent.click(await screen.findByRole('button', { name: '訪談序號 2 · 員工' }));
  await screen.findByText('第一則員工原話');
  expect(screen.queryByRole('tablist')).not.toBeInTheDocument();
});
