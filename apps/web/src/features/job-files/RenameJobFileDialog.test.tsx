import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { act, fireEvent, render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, beforeEach, expect, test, vi } from 'vitest';
import type { JobFile } from '../../shared/api/generated/job-file-list';
import { RenameJobFileDialog } from './RenameJobFileDialog';
import { pendingRename } from './job-file-commands';

const file: JobFile = {
  job_file_id: '10000000-0000-4000-8000-000000000001',
  display_name: '合成原名稱',
  employee_name: '合成員工',
  created_at: '2026-10-09T00:00:00Z',
  name_revision: 1,
};
const command = {
  command_id: '20000000-0000-4000-8000-000000000002',
  display_name: '合成改名',
  expected_name_revision: 1,
};
const clients: QueryClient[] = [];

function renderDialog() {
  const client = new QueryClient();
  clients.push(client);
  const invalidate = vi.spyOn(client, 'invalidateQueries');
  const onClose = vi.fn();
  const view = render(
    <QueryClientProvider client={client}>
      <RenameJobFileDialog file={file} onClose={onClose} />
    </QueryClientProvider>,
  );
  return { ...view, onClose, invalidate };
}

beforeEach(() => sessionStorage.clear());
afterEach(() => {
  clients.splice(0).forEach((client) => client.clear());
  vi.unstubAllGlobals();
});

test('未知改名結果仍以原命令重新確認，成功後才刷新目前名稱', async () => {
  pendingRename(file.job_file_id).retain(command);
  const fetch = vi.fn().mockRejectedValueOnce(new TypeError('lost response'));
  fetch.mockResolvedValue(
    Response.json({ ...file, display_name: command.display_name, name_revision: 2 }),
  );
  vi.stubGlobal('fetch', fetch);
  const view = renderDialog();
  await userEvent.click(screen.getByRole('button', { name: '重新確認改名結果' }));
  expect(await screen.findByRole('alert')).toHaveTextContent('結果尚未確認');
  expect(pendingRename(file.job_file_id).read()).toEqual(command);
  expect(view.onClose).not.toHaveBeenCalled();
  expect(view.invalidate).not.toHaveBeenCalled();
  await userEvent.click(screen.getByRole('button', { name: '重新確認改名結果' }));
  expect(view.onClose).toHaveBeenCalledOnce();
  expect(view.invalidate).toHaveBeenCalledWith(
    {
      queryKey: ['job-file', file.job_file_id],
      exact: true,
    },
    { throwOnError: true },
  );
  expect(view.invalidate).toHaveBeenCalledWith(
    { queryKey: ['job-files'], exact: true },
    { throwOnError: true },
  );
  // The file and the list are each re-read once, not once per code path that noticed the success.
  expect(view.invalidate).toHaveBeenCalledTimes(2);
  expect(pendingRename(file.job_file_id).read()).toBeNull();
  expect(fetch.mock.calls.map((call) => (call[1] as RequestInit).body)).toEqual([
    JSON.stringify(command),
    JSON.stringify(command),
  ]);
});

test.each(['success', 'rejected'] as const)(
  '改名 ACK 儲存清理失敗時 %s 保留原識別與既有成功／拒絕效果',
  async (outcome) => {
    pendingRename(file.job_file_id).retain(command);
    vi.stubGlobal('fetch', () =>
      Promise.resolve(
        outcome === 'success'
          ? Response.json({ ...file, display_name: command.display_name, name_revision: 2 })
          : Response.json({ detail: { code: 'stale_job_file_name' } }, { status: 409 }),
      ),
    );
    vi.spyOn(Storage.prototype, 'removeItem').mockImplementation(() => {
      throw new DOMException('Storage blocked', 'SecurityError');
    });
    const view = renderDialog();
    await userEvent.click(screen.getByRole('button', { name: '重新確認改名結果' }));
    if (outcome === 'success') expect(view.onClose).toHaveBeenCalledOnce();
    else {
      expect(await screen.findByRole('alert')).toHaveTextContent('待確認紀錄無法清除');
      expect(view.onClose).not.toHaveBeenCalled();
      expect(screen.getByLabelText(/職務檔案名稱/)).toBeDisabled();
    }
    expect(pendingRename(file.job_file_id).read()).toEqual(command);
  },
);

test.each(['success', 'rejected', 'unknown'] as const)(
  '卸載後 %s 回覆只整理相符改名命令，不回呼已離開畫面',
  async (outcome) => {
    pendingRename(file.job_file_id).retain(command);
    let finish: (response: Response) => void = () => {};
    const request = new Promise<Response>((resolve) => {
      finish = resolve;
    });
    vi.stubGlobal('fetch', () => request);
    const view = renderDialog();
    await userEvent.click(screen.getByRole('button', { name: '重新確認改名結果' }));
    view.unmount();
    await act(async () => {
      finish(
        outcome === 'success'
          ? Response.json({ ...file, display_name: command.display_name, name_revision: 2 })
          : Response.json(
              { detail: { code: 'stale_job_file_name' } },
              { status: outcome === 'rejected' ? 409 : 503 },
            ),
      );
      await request;
    });
    expect(pendingRename(file.job_file_id).read()).toEqual(outcome === 'unknown' ? command : null);
    expect(view.onClose).not.toHaveBeenCalled();
    if (outcome === 'success') {
      expect(view.invalidate).toHaveBeenCalledWith(
        {
          queryKey: ['job-file', file.job_file_id],
          exact: true,
        },
        { throwOnError: true },
      );
      expect(view.invalidate).toHaveBeenCalledWith(
        { queryKey: ['job-files'], exact: true },
        { throwOnError: true },
      );
    } else expect(view.invalidate).not.toHaveBeenCalled();
  },
);

test.each(['success', 'rejected'] as const)(
  '卸載後晚到的 %s 回覆不清除新改名命令',
  async (outcome) => {
    pendingRename(file.job_file_id).retain(command);
    let finish: (response: Response) => void = () => {};
    const request = new Promise<Response>((resolve) => {
      finish = resolve;
    });
    vi.stubGlobal('fetch', () => request);
    const view = renderDialog();
    await userEvent.click(screen.getByRole('button', { name: '重新確認改名結果' }));
    view.unmount();
    const next = { ...command, command_id: '30000000-0000-4000-8000-000000000003' };
    pendingRename(file.job_file_id).retain(next);
    await act(async () => {
      finish(
        outcome === 'success'
          ? Response.json({ ...file, display_name: command.display_name, name_revision: 2 })
          : Response.json({ detail: { code: 'stale_job_file_name' } }, { status: 409 }),
      );
      await request;
    });
    expect(pendingRename(file.job_file_id).read()).toEqual(next);
    expect(view.onClose).not.toHaveBeenCalled();
  },
);

test.each([
  { outcome: 'success', hasNewCommand: false },
  { outcome: 'success', hasNewCommand: true },
  { outcome: 'rejected', hasNewCommand: false },
  { outcome: 'rejected', hasNewCommand: true },
] as const)(
  '同一改名命令兩次 $outcome，舊畫面先處理後目前畫面收束（新命令：$hasNewCommand）',
  async ({ outcome, hasNewCommand }) => {
    pendingRename(file.job_file_id).retain(command);
    let finishFirst: (response: Response) => void = () => {};
    let finishSecond: (response: Response) => void = () => {};
    const firstRequest = new Promise<Response>((resolve) => {
      finishFirst = resolve;
    });
    const secondRequest = new Promise<Response>((resolve) => {
      finishSecond = resolve;
    });
    const fetch = vi.fn().mockReturnValueOnce(firstRequest).mockReturnValueOnce(secondRequest);
    vi.stubGlobal('fetch', fetch);
    const first = renderDialog();
    await userEvent.click(screen.getByRole('button', { name: '重新確認改名結果' }));
    first.unmount();
    const current = renderDialog();
    await userEvent.click(screen.getByRole('button', { name: '重新確認改名結果' }));
    const result = { ...file, display_name: command.display_name, name_revision: 2 };
    await act(async () => {
      finishFirst(
        outcome === 'success'
          ? Response.json(result)
          : Response.json({ detail: { code: 'stale_job_file_name' } }, { status: 409 }),
      );
      await firstRequest;
    });
    expect(pendingRename(file.job_file_id).read()).toBeNull();
    const next = { ...command, command_id: '30000000-0000-4000-8000-000000000003' };
    if (hasNewCommand) pendingRename(file.job_file_id).retain(next);
    await act(async () => {
      finishSecond(
        outcome === 'success'
          ? Response.json(result)
          : Response.json({ detail: { code: 'stale_job_file_name' } }, { status: 409 }),
      );
      await secondRequest;
    });
    expect(await screen.findByRole('alert')).toHaveTextContent(
      `本次改名${outcome === 'success' ? '已成功' : '未被接受'}，但本分頁待確認紀錄已變更。請返回清單核對目前狀態。`,
    );
    const settled = screen.getByRole('button', {
      name: outcome === 'success' ? '改名已成功' : '改名未被接受',
    });
    expect(settled).toBeDisabled();
    const form = settled.closest('form');
    if (!form) throw new Error('Missing rename form');
    fireEvent.submit(form);
    expect(fetch).toHaveBeenCalledTimes(2);
    expect(pendingRename(file.job_file_id).read()).toEqual(hasNewCommand ? next : null);
    expect(first.onClose).not.toHaveBeenCalled();
    // A success whose local record changed is still a known success: names must be re-read.
    if (outcome === 'success') {
      expect(first.invalidate).toHaveBeenCalledWith(
        { queryKey: ['job-files'], exact: true },
        { throwOnError: true },
      );
      expect(current.invalidate).toHaveBeenCalledWith(
        {
          queryKey: ['job-file', file.job_file_id],
          exact: true,
        },
        { throwOnError: true },
      );
      expect(current.invalidate).toHaveBeenCalledWith(
        { queryKey: ['job-files'], exact: true },
        { throwOnError: true },
      );
    } else {
      expect(current.invalidate).not.toHaveBeenCalled();
    }
    await userEvent.click(screen.getByRole('button', { name: '返回清單' }));
    expect(current.onClose).toHaveBeenCalledOnce();
  },
);
