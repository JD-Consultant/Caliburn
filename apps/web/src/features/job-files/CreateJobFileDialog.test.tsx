import { QueryClient, QueryClientProvider, QueryObserver } from '@tanstack/react-query';
import { act, fireEvent, render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, beforeEach, expect, test, vi } from 'vitest';
import type { CreateJobFileRequest } from '../../shared/api/generated/create-job-file-request';
import { CreateJobFileDialog } from './CreateJobFileDialog';
import { pendingCreation } from './job-file-commands';

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
  const invalidate = vi.spyOn(client, 'invalidateQueries');
  const onCreated = vi.fn();
  const onClose = vi.fn();
  const view = render(
    <QueryClientProvider client={client}>
      <CreateJobFileDialog onCreated={onCreated} onClose={onClose} />
    </QueryClientProvider>,
  );
  return { ...view, client, onCreated, onClose, invalidate };
}

async function fillCreation(): Promise<void> {
  await userEvent.type(screen.getByLabelText(/職務檔案名稱/), command.display_name);
  await userEvent.type(screen.getByLabelText(/受訪員工姓名/), command.employee_name);
}

beforeEach(() => sessionStorage.clear());

test('a deleted original result is terminal, refreshes the list and never announces creation', async () => {
  pendingCreation.retain(command);
  vi.stubGlobal(
    'fetch',
    vi
      .fn()
      .mockResolvedValue(
        Response.json({ detail: { code: 'creation_result_deleted' } }, { status: 410 }),
      ),
  );
  const { onCreated, invalidate } = renderDialog();
  await userEvent.click(screen.getByRole('button', { name: '重新確認建立結果' }));
  expect(await screen.findByText(/原請求不會重新建立/)).toBeInTheDocument();
  expect(pendingCreation.read()).toBeNull();
  expect(invalidate).toHaveBeenCalled();
  expect(onCreated).not.toHaveBeenCalled();
});
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
  const pending = pendingCreation.read();
  expect(pending?.command_id).toBeTruthy();
  expect(first.onCreated).not.toHaveBeenCalled();
  first.unmount();
  const second = renderDialog();
  expect(screen.getByLabelText(/職務檔案名稱/)).toBeDisabled();
  await userEvent.click(screen.getByRole('button', { name: '重新確認建立結果' }));
  expect(second.onCreated).toHaveBeenCalledWith(result.job_file_id);
  expect(pendingCreation.read()).toBeNull();
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
  expect(pendingCreation.read()?.display_name).toBe(command.display_name);
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
  pendingCreation.retain(command);
  const fetch = vi
    .fn()
    .mockResolvedValueOnce(
      Response.json({ detail: { code: 'creation_command_conflict' } }, { status: 409 }),
    );
  fetch.mockResolvedValue(Response.json({ job_file_id: 'invalid' }));
  vi.stubGlobal('fetch', fetch);
  const { onCreated } = renderDialog();
  await userEvent.click(screen.getByRole('button', { name: '重新確認建立結果' }));
  expect(await screen.findByRole('alert')).toHaveTextContent('未被接受');
  expect(screen.getByLabelText(/職務檔案名稱/)).toBeEnabled();
  expect(pendingCreation.read()).toBeNull();
  await userEvent.click(screen.getByRole('button', { name: '建立' }));
  expect(await screen.findByRole('alert')).toHaveTextContent('結果尚未確認');
  expect(pendingCreation.read()?.command_id).not.toBe(command.command_id);
  expect(onCreated).not.toHaveBeenCalled();
});

test('建立受理後真實 Query observer 重讀失敗，仍顯示已成功且不重送', async () => {
  pendingCreation.retain(command);
  const fetch = vi.fn(() => Promise.resolve(Response.json(result)));
  vi.stubGlobal('fetch', fetch);
  const view = renderDialog();
  const queryKey = ['job-files'];
  view.client.setQueryData(queryKey, { job_files: [] });
  const observer = new QueryObserver(view.client, {
    queryKey,
    queryFn: () => Promise.reject(new TypeError('Synthetic list GET failure')),
    staleTime: Infinity,
    retry: false,
  });
  const unsubscribe = observer.subscribe(() => {});
  try {
    await userEvent.click(screen.getByRole('button', { name: '重新確認建立結果' }));
    expect(await screen.findByRole('alert')).toHaveTextContent(
      '本次建立已成功，但清單未能重新讀取',
    );
    expect(view.client.getQueryState(queryKey)?.status).toBe('error');
    expect(pendingCreation.read()).toBeNull();
    expect(view.onCreated).not.toHaveBeenCalled();
    const form = screen.getByLabelText(/職務檔案名稱/).closest('form');
    if (!form) throw new Error('Missing creation form');
    fireEvent.submit(form);
    expect(fetch).toHaveBeenCalledTimes(1);
  } finally {
    unsubscribe();
  }
});

test.each(['success', 'rejected', 'unknown'] as const)(
  '卸載後 %s 回覆只整理相符原命令，不回呼已離開畫面',
  async (outcome) => {
    pendingCreation.retain(command);
    let finish: (response: Response) => void = () => {};
    const request = new Promise<Response>((resolve) => {
      finish = resolve;
    });
    vi.stubGlobal('fetch', () => request);
    const view = renderDialog();
    await userEvent.click(screen.getByRole('button', { name: '重新確認建立結果' }));
    view.unmount();
    await act(async () => {
      finish(
        outcome === 'success'
          ? Response.json(result)
          : Response.json(
              { detail: { code: 'creation_command_conflict' } },
              { status: outcome === 'rejected' ? 409 : 503 },
            ),
      );
      await request;
    });
    expect(pendingCreation.read()).toEqual(outcome === 'unknown' ? command : null);
    expect(view.onCreated).not.toHaveBeenCalled();
    // The cached list is stale after a confirmed creation even though the screen is gone.
    if (outcome === 'success')
      expect(view.invalidate).toHaveBeenCalledWith(
        { queryKey: ['job-files'], exact: true },
        { throwOnError: true },
      );
    else expect(view.invalidate).not.toHaveBeenCalled();
  },
);

test.each(['success', 'rejected'] as const)(
  'ACK 儲存清理失敗時 %s 仍保留原識別與既有成功／拒絕效果',
  async (outcome) => {
    pendingCreation.retain(command);
    vi.stubGlobal('fetch', () =>
      Promise.resolve(
        outcome === 'success'
          ? Response.json(result)
          : Response.json({ detail: { code: 'creation_command_conflict' } }, { status: 409 }),
      ),
    );
    vi.spyOn(Storage.prototype, 'removeItem').mockImplementation(() => {
      throw new DOMException('Storage blocked', 'SecurityError');
    });
    const view = renderDialog();
    await userEvent.click(screen.getByRole('button', { name: '重新確認建立結果' }));
    if (outcome === 'success') {
      expect(view.onCreated).toHaveBeenCalledWith(result.job_file_id);
      expect(view.invalidate).toHaveBeenCalledExactlyOnceWith(
        { queryKey: ['job-files'], exact: true },
        { throwOnError: true },
      );
    } else {
      expect(await screen.findByRole('alert')).toHaveTextContent('待確認紀錄未能清除');
      expect(view.onCreated).not.toHaveBeenCalled();
      expect(screen.getByLabelText(/職務檔案名稱/)).toBeDisabled();
    }
    expect(pendingCreation.read()).toEqual(command);
  },
);

test.each(['success', 'rejected'] as const)(
  '卸載後晚到的 %s 回覆不清除新建立命令',
  async (outcome) => {
    pendingCreation.retain(command);
    let finish: (response: Response) => void = () => {};
    const request = new Promise<Response>((resolve) => {
      finish = resolve;
    });
    vi.stubGlobal('fetch', () => request);
    const view = renderDialog();
    await userEvent.click(screen.getByRole('button', { name: '重新確認建立結果' }));
    view.unmount();
    const next = { ...command, command_id: '30000000-0000-4000-8000-000000000003' };
    pendingCreation.retain(next);
    await act(async () => {
      finish(
        outcome === 'success'
          ? Response.json(result)
          : Response.json({ detail: { code: 'creation_command_conflict' } }, { status: 409 }),
      );
      await request;
    });
    expect(pendingCreation.read()).toEqual(next);
    expect(view.onCreated).not.toHaveBeenCalled();
  },
);

test.each([
  { outcome: 'success', hasNewCommand: false },
  { outcome: 'success', hasNewCommand: true },
  { outcome: 'rejected', hasNewCommand: false },
  { outcome: 'rejected', hasNewCommand: true },
] as const)(
  '同一建立命令兩次 $outcome，舊畫面先處理後目前畫面收束（新命令：$hasNewCommand）',
  async ({ outcome, hasNewCommand }) => {
    pendingCreation.retain(command);
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
    await userEvent.click(screen.getByRole('button', { name: '重新確認建立結果' }));
    first.unmount();
    const current = renderDialog();
    await userEvent.click(screen.getByRole('button', { name: '重新確認建立結果' }));
    await act(async () => {
      finishFirst(
        outcome === 'success'
          ? Response.json(result)
          : Response.json({ detail: { code: 'creation_command_conflict' } }, { status: 409 }),
      );
      await firstRequest;
    });
    expect(pendingCreation.read()).toBeNull();
    const next = { ...command, command_id: '30000000-0000-4000-8000-000000000003' };
    if (hasNewCommand) pendingCreation.retain(next);
    await act(async () => {
      finishSecond(
        outcome === 'success'
          ? Response.json(result)
          : Response.json({ detail: { code: 'creation_command_conflict' } }, { status: 409 }),
      );
      await secondRequest;
    });
    expect(await screen.findByRole('alert')).toHaveTextContent(
      `本次建立${outcome === 'success' ? '已成功' : '未被接受'}，但本分頁待確認紀錄已變更。請返回清單核對目前狀態。`,
    );
    const settled = screen.getByRole('button', {
      name: outcome === 'success' ? '建立已成功' : '建立未被接受',
    });
    expect(settled).toBeDisabled();
    const form = settled.closest('form');
    if (!form) throw new Error('Missing creation form');
    fireEvent.submit(form);
    expect(fetch).toHaveBeenCalledTimes(2);
    expect(pendingCreation.read()).toEqual(hasNewCommand ? next : null);
    expect(first.onCreated).not.toHaveBeenCalled();
    expect(current.onCreated).not.toHaveBeenCalled();
    // A success whose local record changed is still a known success: the list must be re-read.
    if (outcome === 'success') {
      expect(first.invalidate).toHaveBeenCalledWith(
        { queryKey: ['job-files'], exact: true },
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
