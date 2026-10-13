import { stubHttp } from '../../test-http';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { cleanup, render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, expect, test, vi } from 'vitest';
import { TurnTools } from './TurnTools';

const file = '10000000-0000-4000-8000-000000000001';
const run = '20000000-0000-4000-8000-000000000002';
const clients: QueryClient[] = [];

function setup() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  clients.push(client);
  render(
    <QueryClientProvider client={client}>
      <TurnTools jobFileId={file} executionId={run} />
    </QueryClientProvider>,
  );
}

afterEach(() => {
  cleanup();
  clients.splice(0).forEach((client) => client.clear());
  vi.unstubAllGlobals();
});

test('saved tool strings preserve large numbers, duplicate keys and original whitespace', async () => {
  const original = '{ "n":9007199254740993,"x":1,"x":2 }';
  stubHttp(() =>
    Promise.resolve(
      Response.json({
        execution_id: run,
        calls: [
          {
            request_id: file,
            response_id: 'r1',
            call_id: 'c1',
            name: 'rejected_tool',
            arguments: original,
            result_state: 'recorded',
            output: original,
          },
        ],
      }),
    ),
  );
  setup();
  await userEvent.click(screen.getByRole('button', { name: '查看這輪工具紀錄' }));
  await userEvent.click(await screen.findByText('rejected_tool'));
  const originals = screen.getByRole('dialog').querySelectorAll('pre');
  expect(originals).toHaveLength(2);
  expect([...originals].map((item) => item.textContent)).toEqual([original, original]);
});

test('failed read offers retry without claiming no tools; a successful empty original is explicit', async () => {
  const fetch = vi
    .fn()
    .mockResolvedValueOnce(Response.json({}, { status: 503 }))
    .mockResolvedValueOnce(Response.json({ execution_id: run, calls: [] }));
  stubHttp(fetch);
  setup();
  expect(fetch).not.toHaveBeenCalled();
  await userEvent.click(screen.getByRole('button', { name: '查看這輪工具紀錄' }));
  const dialog = screen.getByRole('dialog', { name: '這輪工具紀錄' });
  expect(await within(dialog).findByRole('alert')).toBeVisible();
  expect(screen.queryByText('這輪沒有已保存的工具呼叫。')).not.toBeInTheDocument();
  await userEvent.click(screen.getByRole('button', { name: '重新讀取工具紀錄' }));
  expect(await screen.findByText('這輪沒有已保存的工具呼叫。')).toBeVisible();
  expect(fetch).toHaveBeenCalledTimes(2);
});
