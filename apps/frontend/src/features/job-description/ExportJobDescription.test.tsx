import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, expect, it, vi } from 'vitest';
import { jobDescription } from '../../../tests/fixtures';
import { ExportJobDescription } from './ExportJobDescription';
import { JobDescriptionEditorProvider } from './editing/JobDescriptionEditorProvider';
import { storeDrafts } from './editing/drafts';

beforeEach(() => sessionStorage.clear());

function renderExport() {
  const cache = new QueryClient({ defaultOptions: { mutations: { retry: false } } });
  render(
    <QueryClientProvider client={cache}>
      <JobDescriptionEditorProvider jobDescription={jobDescription} onSaved={() => {}}>
        <ExportJobDescription />
      </JobDescriptionEditorProvider>
    </QueryClientProvider>,
  );
  return cache;
}

it('PDF 未配置回覆顯示失敗，不產生下載', async () => {
  vi.stubGlobal(
    'fetch',
    vi
      .fn()
      .mockResolvedValue(
        Response.json({ detail: { code: 'pdf_export_unavailable' } }, { status: 503 }),
      ),
  );
  const createUrl = vi.fn();
  vi.stubGlobal(
    'URL',
    class extends URL {
      static createObjectURL = createUrl;
    },
  );
  const cache = renderExport();
  await userEvent.setup().click(screen.getByRole('button', { name: '下載 PDF' }));
  expect(await screen.findByRole('alert')).toHaveTextContent('尚未設定字型或瀏覽器');
  expect(createUrl).not.toHaveBeenCalled();
  cache.clear();
});

it('人工草稿未確認時不下載可能不同的已保存內容', async () => {
  storeDrafts(jobDescription.workspace_id, jobDescription.job_description_id, {
    purpose: { value: '人工輸入', baseValue: null, label: '職務目的' },
  });
  const fetch = vi.fn();
  vi.stubGlobal('fetch', fetch);
  const cache = renderExport();
  await userEvent.setup().click(screen.getByRole('button', { name: '下載 PDF' }));
  expect(await screen.findByText('請先處理尚未保存的輸入，再下載 PDF。')).toBeVisible();
  expect(fetch).not.toHaveBeenCalled();
  cache.clear();
});

it('正式 PDF 二進位成功後才建立下載連結，並釋放 URL', async () => {
  const fetch = vi
    .fn()
    .mockResolvedValue(
      new Response('%PDF-1.7', { headers: { 'Content-Type': 'application/pdf' } }),
    );
  vi.stubGlobal('fetch', fetch);
  const createUrl = vi.fn().mockReturnValue('blob:jd-pdf');
  const revokeUrl = vi.fn();
  vi.stubGlobal(
    'URL',
    class extends URL {
      static createObjectURL = createUrl;
      static revokeObjectURL = revokeUrl;
    },
  );
  const click = vi
    .spyOn(HTMLAnchorElement.prototype, 'click')
    .mockImplementation(() => {});
  const cache = renderExport();
  await userEvent.setup().click(screen.getByRole('button', { name: '下載 PDF' }));
  await waitFor(() => expect(click).toHaveBeenCalledOnce());
  expect(fetch.mock.calls[0]?.[0]).toContain('/export.pdf');
  expect(createUrl).toHaveBeenCalledOnce();
  await waitFor(() => expect(revokeUrl).toHaveBeenCalledWith('blob:jd-pdf'));
  cache.clear();
});
