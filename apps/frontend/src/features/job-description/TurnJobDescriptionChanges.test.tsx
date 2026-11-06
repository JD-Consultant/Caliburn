import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import { jobDescription, workspaceId } from '../../../tests/fixtures';
import { jobDescriptionOptions } from './queries';
import { TurnJobDescriptionChanges } from './TurnJobDescriptionChanges';
import { storeDrafts } from './editing/drafts';

const turnId = '55112233-4455-6677-8899-aabbccddeeff';
const jdId = jobDescription.job_description_id;
const content = { ...jobDescription, version: undefined };
const changes = {
  workspace_id: workspaceId,
  job_description_id: jdId,
  turn_id: turnId,
  before_version: 9,
  after_version: 3,
  before: content,
  after: content,
  difference: {
    job_description_id: jdId,
    before_version: 9,
    after_version: 3,
    items: [],
    collections: [],
  },
};
const caches: QueryClient[] = [];
beforeEach(() => sessionStorage.clear());
afterEach(() => caches.splice(0).forEach((cache) => cache.clear()));
function mount(readOnly = false) {
  const cache = new QueryClient({
    defaultOptions: {
      queries: { retry: false, staleTime: Infinity },
      mutations: { retry: false },
    },
  });
  caches.push(cache);
  cache.setQueryData(jobDescriptionOptions(workspaceId).queryKey, jobDescription);
  const onChanged = vi.fn();
  render(
    <QueryClientProvider client={cache}>
      <TurnJobDescriptionChanges
        workspaceId={workspaceId}
        turnId={turnId}
        readOnly={readOnly}
        onChanged={onChanged}
      />
    </QueryClientProvider>,
  );
  return { cache, onChanged };
}

it('未參與JD的完成輪404是正常空狀態，不顯示故障或撤銷入口', async () => {
  vi.stubGlobal(
    'fetch',
    vi
      .fn()
      .mockResolvedValue(
        Response.json({ detail: { code: 'jd_turn_not_found' } }, { status: 404 }),
      ),
  );
  mount();
  await userEvent.click(screen.getByRole('button', { name: '該輪 JD 變更' }));
  expect(await screen.findByText('此輪沒有可回看的 JD 保存點。')).toBeVisible();
  expect(screen.queryByRole('alert')).not.toBeInTheDocument();
  expect(
    screen.queryByRole('button', { name: '撤銷此輪 JD 改動' }),
  ).not.toBeInTheDocument();
});

it('空diff仍提供單輪撤銷，固定9到3方向並保持其他資料', async () => {
  const fetch = vi.fn((url: string) =>
    Promise.resolve(
      Response.json(
        url.endsWith(':restore') ? { ...jobDescription, version: 10 } : changes,
      ),
    ),
  );
  vi.stubGlobal('fetch', fetch);
  const { onChanged, cache } = mount();
  const user = userEvent.setup();
  await user.click(screen.getByRole('button', { name: '該輪 JD 變更' }));
  expect(await screen.findByText('這兩個版本沒有內容差異。')).toBeVisible();
  expect(screen.getByText(/輪前版本 9 → 模型完成時已見版本 3/)).toBeVisible();
  await user.click(screen.getByRole('button', { name: '撤銷此輪 JD 改動' }));
  await user.click(screen.getByRole('button', { name: '確認撤銷此輪 JD 改動' }));
  await waitFor(() => expect(onChanged).toHaveBeenCalledOnce());
  expect(cache.getQueryData(jobDescriptionOptions(workspaceId).queryKey)).toMatchObject({
    version: 10,
  });
  expect(fetch.mock.calls.map(([url]) => url)).toEqual([
    `/api/workspaces/${workspaceId}/job-descriptions/${jdId}/turns/${turnId}/changes`,
    `/api/workspaces/${workspaceId}/job-descriptions/${jdId}/turns/${turnId}:restore`,
  ]);
});

it('唯讀不可撤銷；未確認草稿在最後按下確認時仍阻止送出', async () => {
  const fetch = vi.fn().mockResolvedValue(Response.json(changes));
  vi.stubGlobal('fetch', fetch);
  mount();
  const user = userEvent.setup();
  await user.click(screen.getByRole('button', { name: '該輪 JD 變更' }));
  await user.click(await screen.findByRole('button', { name: '撤銷此輪 JD 改動' }));
  storeDrafts(workspaceId, jdId, {
    'basic.purpose': { value: '草稿', baseValue: null, label: '職務目的' },
  });
  await user.click(screen.getByRole('button', { name: '確認撤銷此輪 JD 改動' }));
  expect(
    screen.getByText('JD 還有未確認輸入。請先處理草稿，再撤銷此輪改動。'),
  ).toBeVisible();
  expect(fetch).toHaveBeenCalledOnce();
});

it('readOnly 允許回看但停用撤銷', async () => {
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue(Response.json(changes)));
  mount(true);
  await userEvent.click(screen.getByRole('button', { name: '該輪 JD 變更' }));
  expect(await screen.findByRole('button', { name: '撤銷此輪 JD 改動' })).toBeDisabled();
});

it('後續修改409保留固定比較，不自動重送撤銷', async () => {
  const fetch = vi.fn((url: string) =>
    Promise.resolve(
      url.endsWith(':restore')
        ? Response.json(
            {
              detail: {
                code: 'jd_concurrency_conflict',
                reason: 'version',
                commit_status: 'not_committed',
              },
            },
            { status: 409 },
          )
        : Response.json(
            url.endsWith('/changes') ? changes : { ...jobDescription, version: 12 },
          ),
    ),
  );
  vi.stubGlobal('fetch', fetch);
  const { onChanged } = mount();
  const user = userEvent.setup();
  await user.click(screen.getByRole('button', { name: '該輪 JD 變更' }));
  await user.click(await screen.findByRole('button', { name: '撤銷此輪 JD 改動' }));
  await user.click(screen.getByRole('button', { name: '確認撤銷此輪 JD 改動' }));
  expect(
    await screen.findByText(
      '目前 JD 有後續或交錯修改，這次未撤銷。已保留目前 JD 與原比較。',
    ),
  ).toBeVisible();
  expect(screen.getByText(/輪前版本 9 → 模型完成時已見版本 3/)).toBeVisible();
  expect(screen.getByRole('button', { name: '確認撤銷此輪 JD 改動' })).toBeDisabled();
  expect(fetch.mock.calls.filter(([url]) => url.endsWith(':restore'))).toHaveLength(1);
  expect(onChanged).not.toHaveBeenCalled();
});
