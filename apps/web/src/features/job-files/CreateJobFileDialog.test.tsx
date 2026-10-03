import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { act, render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, beforeEach, expect, test, vi } from 'vitest';
import type { CreateJobFileRequest } from '../../shared/api/generated/create-job-file-request';
import { CreateJobFileDialog } from './CreateJobFileDialog';
import { readPendingCreation, retainPendingCreation } from './creation-command';

const command: CreateJobFileRequest = {
  command_id: '10000000-0000-4000-8000-000000000001',
  display_name: '合成職務',
  employee_name: '合成員工',
};
const result = {
  job_file_id: '20000000-0000-4000-8000-000000000002',
  display_name: command.display_name,
  employee_name: command.employee_name,
  created_at: '2026-09-29T10:00:00Z',
  name_revision: 1,
};
const clients: QueryClient[] = [];

function renderDialog() {
  const client = new QueryClient();
  clients.push(client);
  const onCreated = vi.fn();
  const onClose = vi.fn();
  const view = render(
    <QueryClientProvider client={client}>
      <CreateJobFileDialog onCreated={onCreated} onClose={onClose} />
    </QueryClientProvider>,
  );
  return { ...view, onCreated, onClose };
}

async function fillCreation(): Promise<void> {
  await userEvent.type(screen.getByLabelText(/職務檔案名稱/), command.display_name);
  await userEvent.type(screen.getByLabelText(/受訪員工姓名/), command.employee_name);
}

beforeEach(() => sessionStorage.clear());
afterEach(() => {
  clients.splice(0).forEach((client) => client.clear());
  vi.unstubAllGlobals();
});

test('不明結果重開表單後仍送同一個原命令，確認成功才清除', async () => {
  const fetch = vi
    .fn<(path: string, options?: RequestInit) => Promise<Response>>()
    .mockRejectedValueOnce(new TypeError('lost response'));
  fetch.mockResolvedValue(Response.json(result));
  vi.stubGlobal('fetch', fetch);
  const first = renderDialog();
  await fillCreation();
  await userEvent.click(screen.getByRole('button', { name: '建立' }));
  expect(await screen.findByRole('alert')).toHaveTextContent('建立結果尚未確認');
  const pending = readPendingCreation();
  expect(pending?.command_id).toBeTruthy();
  expect(first.onCreated).not.toHaveBeenCalled();
  first.unmount();
  const second = renderDialog();
  expect(screen.getByLabelText(/職務檔案名稱/)).toBeDisabled();
  await userEvent.click(screen.getByRole('button', { name: '重新確認建立結果' }));
  expect(second.onCreated).toHaveBeenCalledWith(result.job_file_id);
  expect(readPendingCreation()).toBeNull();
  const options = fetch.mock.calls.map((call) => call[1]);
  expect(options[0]?.body).toBe(JSON.stringify(pending));
  expect(options[1]?.body).toBe(options[0]?.body);
  expect(fetch).toHaveBeenCalledTimes(2);
});

test('已確認後再主動建立，是新的命令而非舊檔案重送', async () => {
  const fetch = vi
    .fn<(path: string, options?: RequestInit) => Promise<Response>>()
    .mockImplementation(() => Promise.resolve(Response.json(result)));
  vi.stubGlobal('fetch', fetch);
  const first = renderDialog();
  await fillCreation();
  await userEvent.click(screen.getByRole('button', { name: '建立' }));
  expect(first.onCreated).toHaveBeenCalled();
  first.unmount();
  renderDialog();
  await fillCreation();
  await userEvent.click(screen.getByRole('button', { name: '建立' }));
  expect(fetch).toHaveBeenCalledTimes(2);
  expect(fetch.mock.calls[0]?.[1]).not.toEqual(fetch.mock.calls[1]?.[1]);
});

test('未送出前先保留命令；進行中不重複送出或用 Escape 關閉', async () => {
  let finishRequest: (value: Response) => void = () => {
    throw new Error('Uninitialized');
  };
  const request = new Promise<Response>((resolve) => {
    finishRequest = resolve;
  });
  const fetch = vi.fn(() => request);
  vi.stubGlobal('fetch', fetch);
  const { onClose } = renderDialog();
  await fillCreation();
  await userEvent.click(screen.getByRole('button', { name: '建立' }));
  expect(readPendingCreation()?.display_name).toBe(command.display_name);
  expect(screen.getByRole('button', { name: '確認中…' })).toBeDisabled();
  expect(screen.getByRole('button', { name: '返回清單' })).toBeDisabled();
  await userEvent.keyboard('{Escape}{Enter}');
  expect(onClose).not.toHaveBeenCalled();
  expect(fetch).toHaveBeenCalledTimes(1);
  await act(async () => {
    finishRequest(Response.json(result));
    await request;
  });
});

test('空白名稱與無法保存命令都不得送出 POST', async () => {
  const fetch = vi.fn();
  vi.stubGlobal('fetch', fetch);
  const first = renderDialog();
  await userEvent.type(screen.getByLabelText(/職務檔案名稱/), '   ');
  await userEvent.type(screen.getByLabelText(/受訪員工姓名/), command.employee_name);
  await userEvent.click(screen.getByRole('button', { name: '建立' }));
  expect(await screen.findByRole('alert')).toHaveTextContent('不能只有空白');
  expect(fetch).not.toHaveBeenCalled();
  first.unmount();
  renderDialog();
  await fillCreation();
  vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => {
    throw new DOMException('Quota exceeded', 'QuotaExceededError');
  });
  await userEvent.click(screen.getByRole('button', { name: '建立' }));
  expect(await screen.findByRole('alert')).toHaveTextContent('尚未送出');
  expect(fetch).not.toHaveBeenCalled();
});

test('已知拒絕可重新編輯，非成功格式仍保留原命令', async () => {
  retainPendingCreation(command);
  const fetch = vi.fn().mockResolvedValueOnce(Response.json({}, { status: 422 }));
  fetch.mockResolvedValue(Response.json({ job_file_id: 'invalid' }));
  vi.stubGlobal('fetch', fetch);
  const { onCreated } = renderDialog();
  await userEvent.click(screen.getByRole('button', { name: '重新確認建立結果' }));
  expect(await screen.findByRole('alert')).toHaveTextContent('未被接受');
  expect(screen.getByLabelText(/職務檔案名稱/)).toBeEnabled();
  expect(readPendingCreation()).toBeNull();
  await userEvent.click(screen.getByRole('button', { name: '建立' }));
  expect(await screen.findByRole('alert')).toHaveTextContent('結果尚未確認');
  expect(readPendingCreation()?.command_id).not.toBe(command.command_id);
  expect(onCreated).not.toHaveBeenCalled();
});
