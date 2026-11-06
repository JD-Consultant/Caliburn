import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router';
import { expect, it, vi } from 'vitest';
import { WorkspaceListPage } from './WorkspaceListPage';

const workspace = {
  workspace_id: '00112233-4455-6677-8899-aabbccddeeff',
  interviewee_name: '林怡君',
};

function renderList(onDeleted = vi.fn<() => Promise<void>>().mockResolvedValue()) {
  const cache = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  render(
    <QueryClientProvider client={cache}>
      <MemoryRouter>
        <WorkspaceListPage onDeleted={onDeleted} />
      </MemoryRouter>
    </QueryClientProvider>,
  );
  return { cache, onDeleted };
}

it('確認刪除後先完成跨功能清理，再刷新清單並將焦點交回建立入口', async () => {
  let finishDeletion: (() => void) | undefined;
  let finishCleanup: (() => void) | undefined;
  let deleted = false;
  const fetcher = vi.fn((url: string, options?: RequestInit) => {
    if (options?.method === 'DELETE') {
      return new Promise<Response>((resolve) => {
        finishDeletion = () => {
          deleted = true;
          resolve(new Response(null, { status: 204 }));
        };
      });
    }
    return Promise.resolve(
      Response.json({ items: deleted ? [] : [workspace], next_cursor: null }),
    );
  });
  vi.stubGlobal('fetch', fetcher);
  const onDeleted = vi.fn(
    () =>
      new Promise<void>((resolve) => {
        finishCleanup = resolve;
      }),
  );
  renderList(onDeleted);
  const user = userEvent.setup();
  await user.click(await screen.findByRole('button', { name: '刪除 林怡君 的工作區' }));
  await user.click(screen.getByRole('button', { name: '永久刪除' }));
  expect(onDeleted).not.toHaveBeenCalled();
  expect(screen.getByRole('button', { name: '取消' })).toBeDisabled();
  finishDeletion?.();
  await waitFor(() => expect(onDeleted).toHaveBeenCalledWith(workspace.workspace_id));
  expect(
    fetcher.mock.calls.filter(([, options]) => options?.method !== 'DELETE'),
  ).toHaveLength(1);
  finishCleanup?.();
  await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument());
  await waitFor(() =>
    expect(screen.getByRole('button', { name: '建立工作區' })).toHaveFocus(),
  );
  expect(
    fetcher.mock.calls.filter(([, options]) => options?.method === 'DELETE'),
  ).toHaveLength(1);
});

it('建立僅送受訪者姓名至 Workspace，不另建立 JD', async () => {
  const fetcher = vi.fn((url: string, options?: RequestInit) =>
    Promise.resolve(
      options?.method === 'POST'
        ? Response.json(workspace, { status: 201 })
        : Response.json({ items: [], next_cursor: null }),
    ),
  );
  vi.stubGlobal('fetch', fetcher);
  renderList();
  const user = userEvent.setup();
  await user.click(screen.getByRole('button', { name: '建立工作區' }));
  const dialog = screen.getByRole('dialog');
  await user.type(within(dialog).getByRole('textbox', { name: '受訪者姓名' }), '林怡君');
  await user.click(within(dialog).getByRole('button', { name: '建立並開啟' }));
  await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument());
  const writes = fetcher.mock.calls.filter(([, options]) => options?.method === 'POST');
  expect(writes).toHaveLength(1);
  expect(writes[0]?.[0]).toBe('/api/workspaces');
  expect(writes[0]?.[1]?.body).toBe(JSON.stringify({ interviewee_name: '林怡君' }));
});

it('按伺服器游標續載並保留先前清單', async () => {
  const second = {
    ...workspace,
    workspace_id: '11112233-4455-6677-8899-aabbccddeeff',
    interviewee_name: '陳大文',
  };
  const fetcher = vi.fn((url: string) =>
    Promise.resolve(
      Response.json(
        url.includes('after=')
          ? { items: [second], next_cursor: null }
          : { items: [workspace], next_cursor: workspace.workspace_id },
      ),
    ),
  );
  vi.stubGlobal('fetch', fetcher);
  renderList();
  const user = userEvent.setup();
  await user.click(await screen.findByRole('button', { name: '載入更多' }));
  expect(await screen.findByRole('link', { name: '陳大文' })).toHaveAttribute(
    'href',
    `/workspaces/${second.workspace_id}/jd`,
  );
  expect(screen.getByRole('link', { name: '林怡君' })).toBeInTheDocument();
  expect(fetcher.mock.calls[1]?.[0]).toBe(
    '/api/workspaces?limit=20&after=' + workspace.workspace_id,
  );
  expect(screen.queryByRole('button', { name: '載入更多' })).not.toBeInTheDocument();
});

it('建立結果未知時保留姓名與警示，不允許重送，關閉後焦點歸還', async () => {
  const fetcher = vi.fn((url: string, options?: RequestInit) =>
    options?.method === 'POST'
      ? Promise.reject(new TypeError('network'))
      : Promise.resolve(Response.json({ items: [], next_cursor: null })),
  );
  vi.stubGlobal('fetch', fetcher);
  renderList();
  const user = userEvent.setup();
  const create = screen.getByRole('button', { name: '建立工作區' });
  await user.click(create);
  await user.type(screen.getByRole('textbox', { name: '受訪者姓名' }), '林怡君');
  await user.click(screen.getByRole('button', { name: '建立並開啟' }));
  expect(await screen.findByRole('alert')).toHaveTextContent('無法確認是否已保存');
  expect(screen.getByRole('textbox', { name: '受訪者姓名' })).toHaveValue('林怡君');
  expect(screen.getByRole('button', { name: '建立並開啟' })).toBeDisabled();
  await user.click(screen.getByRole('button', { name: '取消' }));
  await waitFor(() => expect(create).toHaveFocus());
  expect(
    fetcher.mock.calls.filter(([, options]) => options?.method === 'POST'),
  ).toHaveLength(1);
});
