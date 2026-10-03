/** Display only: the consultant's reply is formatted, every other speaker stays verbatim. */
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen, within } from '@testing-library/react';
import { afterEach, expect, test, vi } from 'vitest';
import { InterviewHistory } from './InterviewHistory';

const fileId = '10000000-0000-4000-8000-000000000001';
const clients: QueryClient[] = [];

afterEach(() => {
  clients.splice(0).forEach((client) => client.clear());
  vi.unstubAllGlobals();
});

function message(
  n: number,
  speaker: 'app' | 'employee' | 'consultant',
  text: string,
): Record<string, unknown> {
  return {
    source_id: `${String(n)}0000000-0000-4000-8000-00000000000${String(n)}`,
    interview_sequence: n,
    speaker,
    interview_text: text,
    execution_id: null,
  };
}

test('consultant Markdown is formatted; employee and App text stay exactly as stored', async () => {
  const employee = '員工打的 **不是** 標記\n- 第二行';
  const app = '開場 <b>原樣</b>';
  vi.stubGlobal(
    'fetch',
    vi.fn(() =>
      Promise.resolve(
        Response.json({
          messages: [
            message(1, 'app', app),
            message(2, 'consultant', '先確認兩件事：\n\n**1.** 優先序\n\n- 預算\n- 時程'),
            message(3, 'employee', employee),
          ],
        }),
      ),
    ),
  );
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  clients.push(client);
  render(
    <QueryClientProvider client={client}>
      <InterviewHistory jobFileId={fileId} />
    </QueryClientProvider>,
  );
  const [opening, consultant, staff] = await screen.findAllByRole('listitem').then((rows) =>
    // Formatted lists add nested items; the three message rows are the top-level ones.
    rows.filter((row) => row.classList.contains('msg')),
  );
  if (!opening || !consultant || !staff) throw new Error('Expected three message rows');

  expect(within(consultant).getByText('1.').tagName).toBe('STRONG');
  expect(
    within(consultant)
      .getAllByRole('listitem')
      .map((item) => item.textContent),
  ).toEqual(['預算', '時程']);
  expect(consultant.textContent).not.toContain('**');

  // Verbatim: markers stay as typed, and HTML is text, never an element.
  expect(staff.querySelector('.interview-text')?.textContent).toBe(employee);
  expect(staff.querySelector('strong')).toBeNull();
  expect(opening.querySelector('.interview-text')?.textContent).toBe(app);
  expect(opening.querySelector('b')).toBeNull();
});

test('each message is headed by its speaker only; the formal sequence number is not shown', async () => {
  vi.stubGlobal(
    'fetch',
    vi.fn(() =>
      Promise.resolve(Response.json({ messages: [message(7, 'consultant', '請說明工作。')] })),
    ),
  );
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  clients.push(client);
  render(
    <QueryClientProvider client={client}>
      <InterviewHistory jobFileId={fileId} />
    </QueryClientProvider>,
  );
  expect(await screen.findByRole('heading', { name: '職務顧問' })).toBeVisible();
  expect(screen.queryByText(/訪談序號/)).not.toBeInTheDocument();
});
