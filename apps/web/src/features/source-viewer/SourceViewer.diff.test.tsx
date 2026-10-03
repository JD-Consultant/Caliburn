/** Citation changes are scoped to one JD target, not inferred from repeated labels. */
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, expect, test, vi } from 'vitest';
import { SourceViewer } from './SourceViewer';

const fileId = '10000000-0000-4000-8000-000000000001';
const revisionId = '20000000-0000-4000-8000-000000000002';
const citationId = '30000000-0000-4000-8000-000000000003';
const basePath = `/api/job-files/${fileId}/jd/sources`;
const reference = {
  citation_id: citationId,
  target_label: '盤點產線需求',
  target: { kind: 'task', item_id: fileId, task_id: null, field: null },
  source_kind: 'work_understanding',
  source_label: '範圍管理',
  needs_recheck: true,
  jd_changed: true,
  source_changed: true,
};
const clients: QueryClient[] = [];

function showReferences(references = [reference], sourceMarkdown: string | null = '來源差異正文') {
  const fetch = vi.fn((path: string, options?: RequestInit) => {
    expect(options?.method ?? 'GET').toBe('GET');
    if (path === basePath)
      return Promise.resolve(Response.json({ revision_id: revisionId, references }));
    if (path === `${basePath}/${citationId}/changes?revision_id=${revisionId}`)
      return Promise.resolve(
        Response.json({
          revision_id: revisionId,
          citation_id: citationId,
          jd_markdown: 'JD 差異正文：每月改為每季',
          source_markdown: sourceMarkdown,
        }),
      );
    throw new Error(`Unexpected request: ${path}`);
  });
  vi.stubGlobal('fetch', fetch);
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  clients.push(client);
  render(
    <QueryClientProvider client={client}>
      <SourceViewer jobFileId={fileId} open />
    </QueryClientProvider>,
  );
  return fetch;
}

afterEach(() => {
  clients.splice(0).forEach((client) => client.clear());
  vi.unstubAllGlobals();
});

test('one target has one heading and pending causes belong to individual source rows', async () => {
  showReferences([
    reference,
    {
      ...reference,
      citation_id: revisionId,
      source_label: '其他依據',
      needs_recheck: false,
      jd_changed: false,
      source_changed: false,
    },
  ]);
  expect(await screen.findByRole('heading', { name: '盤點產線需求' })).toBeVisible();
  expect(screen.getAllByRole('heading', { name: '盤點產線需求' })).toHaveLength(1);
  const row = screen.getByRole('listitem', { name: '範圍管理' });
  expect(within(row).getByText('JD 與來源皆有變更')).toBeVisible();
  expect(within(row).getByRole('button', { name: '查看差異' })).toBeVisible();
  expect(
    within(screen.getByRole('listitem', { name: '其他依據' })).queryByRole('button', {
      name: '查看差異',
    }),
  ).not.toBeInTheDocument();
});

test('equal labels on different JD identities are not merged', async () => {
  showReferences([
    reference,
    {
      ...reference,
      citation_id: revisionId,
      target: { ...reference.target, item_id: revisionId },
      source_label: '另一項依據',
    },
  ]);
  expect(await screen.findAllByRole('heading', { name: '盤點產線需求' })).toHaveLength(2);
});

test('one difference action lazily opens both comparisons without loading source body or confirming', async () => {
  const fetch = showReferences();
  await screen.findByRole('button', { name: '範圍管理' });
  expect(fetch).toHaveBeenCalledTimes(1);
  await userEvent.click(screen.getByRole('button', { name: '查看差異' }));
  expect(await screen.findByRole('heading', { name: 'JD 內容變更' })).toBeVisible();
  expect(screen.getByText('JD 差異正文：每月改為每季')).toBeVisible();
  expect(screen.getByRole('heading', { name: '來源變更' })).toBeVisible();
  expect(screen.getByText('來源差異正文')).toBeVisible();
  expect(screen.getByText('JD 與來源皆有變更')).toBeVisible();
  expect(fetch).toHaveBeenCalledTimes(2);
  expect(screen.queryByRole('button', { name: '確認核對' })).not.toBeInTheDocument();
});

test('an immutable interview exposes JD changes only, never suggests an interview version diff', async () => {
  showReferences(
    [{ ...reference, source_kind: 'interview', source_label: '訪談序號 3', source_changed: false }],
    null,
  );
  expect(await screen.findByText('JD 已修改')).toBeVisible();
  await userEvent.click(screen.getByRole('button', { name: '查看差異' }));
  expect(await screen.findByRole('heading', { name: 'JD 內容變更' })).toBeVisible();
  expect(screen.getByText('JD 差異正文：每月改為每季')).toBeVisible();
  expect(screen.queryByRole('heading', { name: '來源變更' })).not.toBeInTheDocument();
});
