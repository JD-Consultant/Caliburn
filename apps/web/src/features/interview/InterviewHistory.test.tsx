import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, expect, test, vi } from 'vitest';
import { InterviewHistory } from './InterviewHistory';

const fileId = '10000000-0000-4000-8000-000000000001';
const firstTurn = '20000000-0000-4000-8000-000000000002';
const laterTurn = '30000000-0000-4000-8000-000000000003';
const clients: QueryClient[] = [];

afterEach(() => {
  clients.splice(0).forEach((client) => client.clear());
  localStorage.clear();
  vi.unstubAllGlobals();
});

test('each historical consultant reply expands its own original turn without a browser recovery hint', async () => {
  localStorage.clear();
  const reads: string[] = [];
  vi.stubGlobal(
    'fetch',
    vi.fn((path: string, options?: RequestInit) => {
      expect(options?.method).not.toBe('POST');
      if (path === `/api/job-files/${fileId}/interviews`)
        return Promise.resolve(
          Response.json({
            messages: [
              {
                source_id: '40000000-0000-4000-8000-000000000004',
                interview_sequence: 1,
                speaker: 'app',
                interview_text: '正式開場',
                execution_id: null,
              },
              {
                source_id: '50000000-0000-4000-8000-000000000005',
                interview_sequence: 2,
                speaker: 'employee',
                interview_text: '員工原話',
                execution_id: null,
              },
              {
                source_id: '60000000-0000-4000-8000-000000000006',
                interview_sequence: 3,
                speaker: 'consultant',
                interview_text: '較早正式回答',
                execution_id: firstTurn,
              },
              {
                source_id: '70000000-0000-4000-8000-000000000007',
                interview_sequence: 4,
                speaker: 'employee',
                interview_text: '後續原話',
                execution_id: null,
              },
              {
                source_id: '80000000-0000-4000-8000-000000000008',
                interview_sequence: 5,
                speaker: 'consultant',
                interview_text: '較晚正式回答',
                execution_id: laterTurn,
              },
            ],
          }),
        );
      reads.push(path);
      if (path.endsWith('/reasoning-summaries')) return Promise.resolve(Response.json([]));
      const executionId = path.endsWith(firstTurn) ? firstTurn : laterTurn;
      return Promise.resolve(
        Response.json({
          job_file_id: fileId,
          execution_id: executionId,
          status: 'completed',
          pause_requested: false,
          input_text: '不在此處重複呈現',
          allowed_controls: [],
          plan_preview: null,
          candidate: null,
          commentary: [
            {
              response_id: `response-${executionId}`,
              message_id: 'message',
              text: executionId === firstTurn ? '較早公開說明' : '較晚公開說明',
            },
          ],
        }),
      );
    }),
  );
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  clients.push(client);
  render(
    <QueryClientProvider client={client}>
      <InterviewHistory jobFileId={fileId} />
    </QueryClientProvider>,
  );
  expect(await screen.findByText('較早正式回答')).toBeVisible();
  expect(reads).toEqual([]);
  const [opening, employee, earlier, , later] = screen.getAllByRole('listitem');
  if (!opening || !employee || !earlier || !later) throw new Error('Expected formal history rows');
  expect(within(opening).queryByRole('button')).not.toBeInTheDocument();
  expect(within(employee).queryByRole('button')).not.toBeInTheDocument();
  expect(screen.getAllByRole('button', { name: '處理紀錄' })).toHaveLength(2);
  await userEvent.click(within(earlier).getByRole('button', { name: '處理紀錄' }));
  await userEvent.click(await within(earlier).findByText('處理過程'));
  expect(await within(earlier).findByText('較早公開說明')).toBeVisible();
  expect(within(later).queryByText('較早公開說明')).not.toBeInTheDocument();
  await userEvent.click(within(later).getByRole('button', { name: '處理紀錄' }));
  await userEvent.click(await within(later).findByText('處理過程'));
  expect(await within(later).findByText('較晚公開說明')).toBeVisible();
  expect(reads).toEqual([
    `/api/job-files/${fileId}/consultant-turns/${firstTurn}`,
    `/api/job-files/${fileId}/consultant-turns/${firstTurn}/reasoning-summaries`,
    `/api/job-files/${fileId}/consultant-turns/${laterTurn}`,
    `/api/job-files/${fileId}/consultant-turns/${laterTurn}/reasoning-summaries`,
  ]);
  expect(localStorage.length).toBe(0);
});
