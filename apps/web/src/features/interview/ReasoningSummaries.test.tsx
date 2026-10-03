import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, expect, test, vi } from 'vitest';
import { HistoricalTurnMessages } from './HistoricalTurnMessages';

const fileId = '10000000-0000-4000-8000-000000000001';
const executionId = '20000000-0000-4000-8000-000000000002';
const savedTurn = {
  job_file_id: fileId,
  execution_id: executionId,
  status: 'completed',
  pause_requested: false,
  input_text: '員工輸入',
  allowed_controls: [],
  candidate: null,
  commentary: [{ response_id: 'r1', message_id: 'm1', text: '已讀取 JD。' }],
};
const summary = {
  response_id: 'r1',
  item_id: 'rs1',
  output_index: 0,
  summary_index: 0,
  text: '已核對**責任範圍**。',
};
const clients: QueryClient[] = [];

function mount() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  clients.push(client);
  return render(
    <QueryClientProvider client={client}>
      <HistoricalTurnMessages jobFileId={fileId} executionId={executionId} />
    </QueryClientProvider>,
  );
}

afterEach(() => {
  clients.splice(0).forEach((client) => client.clear());
  vi.unstubAllGlobals();
});

test('展開歷史才查原 Turn 的摘要，收合後仍能重新讀取，不呼叫模型', async () => {
  const fetch = vi.fn((path: string, options?: RequestInit) => {
    expect(options?.method).not.toBe('POST');
    if (path === `/api/job-files/${fileId}/consultant-turns/${executionId}/reasoning-summaries`)
      return Promise.resolve(Response.json([summary]));
    expect(path).toBe(`/api/job-files/${fileId}/consultant-turns/${executionId}`);
    return Promise.resolve(Response.json(savedTurn));
  });
  vi.stubGlobal('fetch', fetch);
  mount();
  expect(fetch).not.toHaveBeenCalled();
  const toggle = screen.getByRole('button', { name: '處理紀錄' });
  await userEvent.click(toggle);
  const heading = await screen.findByText('推理摘要');
  await userEvent.click(heading);
  expect(await screen.findByText('責任範圍')).toBeVisible();
  expect(screen.getByText('已讀取 JD。')).not.toBeVisible();
  await userEvent.click(toggle);
  expect(screen.queryByText('責任範圍')).not.toBeInTheDocument();
  await userEvent.click(toggle);
  await userEvent.click(await screen.findByText('推理摘要'));
  expect(await screen.findByText('責任範圍')).toBeVisible();
});

test('摘要讀取失敗不偽裝空白；可單獨重試且公開訊息仍可讀', async () => {
  let unavailable = true;
  vi.stubGlobal(
    'fetch',
    vi.fn((path: string) =>
      Promise.resolve(
        path.endsWith('/reasoning-summaries')
          ? unavailable
            ? Response.json({}, { status: 503 })
            : Response.json([])
          : Response.json(savedTurn),
      ),
    ),
  );
  mount();
  await userEvent.click(screen.getByRole('button', { name: '處理紀錄' }));
  await userEvent.click(await screen.findByText('推理摘要'));
  const retry = await screen.findByRole('button', { name: '重新讀取推理摘要' });
  await userEvent.click(screen.getByText('處理過程'));
  expect(screen.getByText('已讀取 JD。')).toBeVisible();
  expect(screen.queryByText('這次處理沒有已保存的推理摘要。')).not.toBeInTheDocument();
  unavailable = false;
  await userEvent.click(retry);
  expect(await screen.findByText('這次處理沒有已保存的推理摘要。')).toBeVisible();
});

test('不接受帶私有欄位的摘要歷史，不輸出其值', async () => {
  vi.stubGlobal(
    'fetch',
    vi.fn((path: string) =>
      Promise.resolve(
        Response.json(
          path.endsWith('/reasoning-summaries')
            ? [{ ...summary, encrypted_content: '秘密', text: '污染內容' }]
            : savedTurn,
        ),
      ),
    ),
  );
  mount();
  await userEvent.click(screen.getByRole('button', { name: '處理紀錄' }));
  await userEvent.click(await screen.findByText('推理摘要'));
  expect(await screen.findByText(/服務回傳的資料格式不符/)).toBeVisible();
  expect(screen.queryByText(/秘密|污染內容/)).not.toBeInTheDocument();
});
