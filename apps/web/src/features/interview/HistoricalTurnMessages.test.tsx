import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen, within } from '@testing-library/react';
import type { ReactNode } from 'react';
import userEvent from '@testing-library/user-event';
import { afterEach, expect, test, vi } from 'vitest';
import { HistoricalTurnMessages } from './HistoricalTurnMessages';

const fileId = '10000000-0000-4000-8000-000000000001';
const executionId = '20000000-0000-4000-8000-000000000002';
const saved = {
  job_file_id: fileId,
  execution_id: executionId,
  status: 'completed',
  pause_requested: false,
  input_text: '不應在歷史公開訊息重複顯示的原輸入',
  allowed_controls: [],
  candidate: null,
  commentary: [
    { response_id: 'response-1', message_id: 'message-1', text: '先核對既有職責。' },
    { response_id: 'response-2', message_id: 'message-2', text: '<script>普通公開文字</script>' },
  ],
};
const clients: QueryClient[] = [];

function renderHistoryTurn(renderTurnActions?: (executionId: string) => ReactNode) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  clients.push(client);
  return render(
    <QueryClientProvider client={client}>
      <HistoricalTurnMessages
        jobFileId={fileId}
        executionId={executionId}
        renderTurnActions={renderTurnActions}
      />
    </QueryClientProvider>,
  );
}

afterEach(() => {
  clients.splice(0).forEach((client) => client.clear());
  vi.unstubAllGlobals();
});

test('historical summary and commentary expand independently while JD actions remain separate', async () => {
  vi.stubGlobal(
    'fetch',
    vi.fn((path: string, options?: RequestInit) => {
      expect(options?.method).not.toBe('POST');
      return Promise.resolve(
        Response.json(
          path.endsWith('/reasoning-summaries')
            ? [
                {
                  response_id: 'r1',
                  item_id: 'rs1',
                  output_index: 0,
                  summary_index: 0,
                  text: '摘要正文',
                },
              ]
            : saved,
        ),
      );
    }),
  );
  renderHistoryTurn((id) => <button>查看 JD：{id}</button>);
  const outerToggle = screen.getByRole('button', { expanded: false });
  await userEvent.click(outerToggle);
  expect(await screen.findByText('摘要正文')).not.toBeVisible();
  expect(screen.getByText('先核對既有職責。')).not.toBeVisible();
  const jdActions = screen.getByRole('region', { name: 'JD 操作' });
  expect(within(jdActions).getByRole('button', { name: `查看 JD：${executionId}` })).toBeVisible();
  const summaryToggle = screen.getByText('推理摘要');
  const commentaryToggle = screen.getByText('處理過程');
  await userEvent.click(commentaryToggle);
  expect(screen.getByText('先核對既有職責。')).toBeVisible();
  expect(screen.getByText('摘要正文')).not.toBeVisible();
  await userEvent.click(summaryToggle);
  expect(screen.getByText('摘要正文')).toBeVisible();
  await userEvent.click(commentaryToggle);
  expect(screen.getByText('先核對既有職責。')).not.toBeVisible();
  expect(screen.getByText('摘要正文')).toBeVisible();
  expect(jdActions).toBeVisible();
  await userEvent.click(outerToggle);
  expect(screen.queryByRole('region', { name: 'JD 操作' })).not.toBeInTheDocument();
});

test('history reads its original turn only on expansion and displays public commentary in order', async () => {
  const fetch = vi.fn((path: string, options?: RequestInit) => {
    if (path.endsWith('/reasoning-summaries')) return Promise.resolve(Response.json([]));
    expect(path).toBe(`/api/job-files/${fileId}/consultant-turns/${executionId}`);
    expect(options?.method).not.toBe('POST');
    return Promise.resolve(Response.json(saved));
  });
  vi.stubGlobal('fetch', fetch);
  renderHistoryTurn();
  expect(fetch).not.toHaveBeenCalled();
  const toggle = screen.getByRole('button', { name: '處理紀錄' });
  toggle.focus();
  await userEvent.keyboard('{Enter}');
  await userEvent.click(await screen.findByText('處理過程'));
  expect(await screen.findByText('先核對既有職責。')).toBeVisible();
  expect(screen.getAllByRole('listitem').map((item) => item.textContent)).toEqual([
    '先核對既有職責。',
    '<script>普通公開文字</script>',
  ]);
  expect(screen.getByText('處理過程')).toBeVisible();
  expect(screen.queryByText(saved.input_text)).not.toBeInTheDocument();
  expect(document.querySelector('script')).toBeNull();
  await userEvent.click(toggle);
  expect(screen.queryByText('先核對既有職責。')).not.toBeInTheDocument();
});

test('a failed history read remains an error until an explicit read retry finds an empty history', async () => {
  vi.stubGlobal(
    'fetch',
    vi
      .fn()
      .mockResolvedValueOnce(Response.json({ detail: { code: 'unavailable' } }, { status: 503 }))
      .mockImplementation(() => Promise.resolve(Response.json({ ...saved, commentary: [] }))),
  );
  renderHistoryTurn();
  await userEvent.click(screen.getByRole('button', { name: '處理紀錄' }));
  expect(await screen.findByRole('button', { name: '重新讀取處理過程' })).toBeVisible();
  expect(screen.queryByText('這次處理沒有已保存的中間訊息。')).not.toBeInTheDocument();
  await userEvent.click(screen.getByRole('button', { name: '重新讀取處理過程' }));
  await userEvent.click(await screen.findByText('處理過程'));
  expect(await screen.findByText('這次處理沒有已保存的中間訊息。')).toBeVisible();
});

test('unconfigured public reader is not presented as an empty history', async () => {
  vi.stubGlobal(
    'fetch',
    vi.fn(() => Promise.resolve(Response.json({ ...saved, commentary: null }))),
  );
  renderHistoryTurn();
  await userEvent.click(screen.getByRole('button', { name: '處理紀錄' }));
  await userEvent.click(await screen.findByText('處理過程'));
  expect(await screen.findByText('目前無法讀取處理過程。')).toBeVisible();
  expect(screen.queryByText('這次處理沒有已保存的中間訊息。')).not.toBeInTheDocument();
});

test('foreign-file commentary is rejected rather than attached to this historical reply', async () => {
  vi.stubGlobal(
    'fetch',
    vi.fn(() =>
      Promise.resolve(
        Response.json({
          ...saved,
          job_file_id: '90000000-0000-4000-8000-000000000009',
        }),
      ),
    ),
  );
  renderHistoryTurn();
  await userEvent.click(screen.getByRole('button', { name: '處理紀錄' }));
  expect(await screen.findByText(/處理狀態不屬於這次訪談/)).toBeVisible();
  expect(screen.queryByText('先核對既有職責。')).not.toBeInTheDocument();
});

test('unexpected private response fields fail the public contract without rendering their values', async () => {
  vi.stubGlobal(
    'fetch',
    vi.fn(() =>
      Promise.resolve(
        Response.json({
          ...saved,
          encrypted_reasoning: 'private opaque reasoning',
          tools_meta: { secret: 'private tool data' },
        }),
      ),
    ),
  );
  renderHistoryTurn();
  await userEvent.click(screen.getByRole('button', { name: '處理紀錄' }));
  expect(await screen.findByText(/服務回傳的資料格式不符/)).toBeVisible();
  expect(screen.queryByText(/private opaque reasoning|private tool data/)).not.toBeInTheDocument();
  expect(screen.queryByText('先核對既有職責。')).not.toBeInTheDocument();
});
