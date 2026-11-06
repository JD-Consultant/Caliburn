import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, expect, it, vi } from 'vitest';
import { jobDescription, workspaceId } from '../../../../tests/fixtures';
import { JobDescriptionSourcesProvider } from './JobDescriptionSourcesProvider';
import { JobDescriptionSources } from './JobDescriptionSources';
import { SourceBadge } from './SourceBadge';
import { citation, citationDetail } from './source-fixtures';

const caches: QueryClient[] = [];
afterEach(() => {
  caches.splice(0).forEach((cache) => cache.clear());
});
function mount(version?: number) {
  const cache = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  caches.push(cache);
  return render(
    <QueryClientProvider client={cache}>
      <JobDescriptionSourcesProvider
        jobDescription={{ ...jobDescription, citations: [citation] }}
        version={version}
      >
        <JobDescriptionSources />
        <SourceBadge
          targetKind="job_description"
          targetId={jobDescription.job_description_id}
        />
      </JobDescriptionSourcesProvider>
    </QueryClientProvider>,
  );
}

it('徽章開啟非 modal 來源面板、按需查固定歷史原件，關閉回到徽章', async () => {
  const user = userEvent.setup();
  const fetch = vi.fn().mockResolvedValue(Response.json(citationDetail));
  vi.stubGlobal('fetch', fetch);
  mount(9);
  expect(fetch).not.toHaveBeenCalled();
  const badge = screen.getByRole('button', { name: '查看此項目的 1 筆來源' });
  await user.click(badge);
  expect(screen.getByRole('complementary')).toBeVisible();
  expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
  await user.click(screen.getByRole('button', { name: /基本資料 Memory/ }));
  expect(await screen.findByText('引用當時的原文')).toBeVisible();
  expect(screen.getByText('核對狀態未知')).toBeVisible();
  expect(fetch.mock.calls[0]?.[0]).toBe(
    `/api/workspaces/${workspaceId}/job-descriptions/${jobDescription.job_description_id}/history/9/citations/${citation.id}`,
  );
  await user.click(screen.getByRole('button', { name: '關閉來源面板' }));
  expect(badge).toHaveFocus();
});

it('來源 unavailable 與查讀失敗顯示不同狀態', async () => {
  const user = userEvent.setup();
  const fetch = vi.fn().mockResolvedValue(
    Response.json({
      ...citationDetail,
      source: { ...citationDetail.source, availability: 'unavailable', text: null },
    }),
  );
  vi.stubGlobal('fetch', fetch);
  mount();
  await user.click(screen.getByRole('button', { name: 'JD 來源（唯讀）' }));
  await user.click(screen.getByRole('button', { name: /基本資料 Memory/ }));
  expect(await screen.findByText('來源目前不可用，保留引用定位供核對。')).toBeVisible();
  fetch.mockRejectedValue(new TypeError('offline'));
  await user.click(screen.getByRole('button', { name: '重新讀取來源' }));
  await waitFor(() =>
    expect(
      screen.getByText('無法讀取來源，核對狀態仍未知。請檢查連線後重試。'),
    ).toBeVisible(),
  );
});
