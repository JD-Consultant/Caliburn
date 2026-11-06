import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen } from '@testing-library/react';
import { expect, it, vi } from 'vitest';
import { MemoryRouter } from 'react-router';
import { jobDescription, workspaceId } from '../../../tests/fixtures';
import { JobDescriptionPage } from './JobDescriptionPage';

function page(readOnly = false) {
  const cache = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={cache}>
      <MemoryRouter>
        <JobDescriptionPage
          workspaceId={workspaceId}
          intervieweeName="合成受訪者"
          readOnly={readOnly}
        />
      </MemoryRouter>
    </QueryClientProvider>,
  );
  return cache;
}

it('原子初始化的 JD 直接查讀，缺少 JD 顯示異常而不提供第二次建立', async () => {
  const fetch = vi
    .fn()
    .mockResolvedValue(
      Response.json({ detail: { code: 'jd_not_found' } }, { status: 404 }),
    );
  vi.stubGlobal('fetch', fetch);
  const cache = page();
  expect(await screen.findByRole('alert')).toHaveTextContent('尚未正確初始化');
  expect(
    screen.queryByRole('button', { name: '建立職務說明書' }),
  ).not.toBeInTheDocument();
  expect(fetch).toHaveBeenCalledTimes(1);
  expect(fetch.mock.calls[0]?.[1]).not.toHaveProperty('method', 'POST');
  cache.clear();
});

it('唯讀 JD 顯示保存內容與版本，沒有可輸入欄位', async () => {
  sessionStorage.clear();
  vi.stubGlobal(
    'fetch',
    vi
      .fn()
      .mockResolvedValue(Response.json({ ...jobDescription, job_title: '合成職務' })),
  );
  const cache = page(true);
  expect(
    await screen.findByRole('heading', { name: '職務說明書', level: 1 }),
  ).toBeVisible();
  expect(screen.getByText('合成職務')).toBeVisible();
  expect(screen.getByRole('alert')).toHaveTextContent('目前僅供查閱');
  expect(screen.queryByRole('textbox')).not.toBeInTheDocument();
  cache.clear();
});
