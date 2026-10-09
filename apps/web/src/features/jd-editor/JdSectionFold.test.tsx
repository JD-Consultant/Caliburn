import { formalJdQueries } from './jd-queries';
import { refreshQueries } from '../../shared/api/refresh-queries';
/** The four supporting sections fold to their heading and count (Notion toggles, GOV.UK accordion); the section bar opens them. */
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, beforeEach, expect, test, vi } from 'vitest';
import type { JdWorkView } from '../../shared/api/generated/jd-work-view';
import { JdOutline } from './JdOutline';
import { JdWorkEditor } from './JdWorkEditor';

const fileId = '10000000-0000-4000-8000-000000000001';
const jd: JdWorkView = {
  revision_id: '20000000-0000-4000-8000-000000000002',
  areas: [],
  tasks: [],
  capabilities: [
    {
      capability_id: '31000000-0000-4000-8000-000000000001',
      kind: 'knowledge',
      name: '財務知識',
      description: null,
    },
    {
      capability_id: '31000000-0000-4000-8000-000000000002',
      kind: 'knowledge',
      name: '合約知識',
      description: null,
    },
    {
      capability_id: '32000000-0000-4000-8000-000000000001',
      kind: 'skill',
      name: '協調能力',
      description: null,
    },
  ],
  task_links: [],
  collaborators: [
    { collaborator_id: '41000000-0000-4000-8000-000000000001', name: '採購部', scope_text: null },
    { collaborator_id: '41000000-0000-4000-8000-000000000002', name: '法務部', scope_text: null },
  ],
  conditions: [
    {
      condition_id: '51000000-0000-4000-8000-000000000001',
      kind: 'work_environment',
      text: '辦公室工作',
    },
    {
      condition_id: '51000000-0000-4000-8000-000000000002',
      kind: 'work_environment',
      text: '偶爾出差',
    },
    {
      condition_id: '51000000-0000-4000-8000-000000000003',
      kind: 'schedule_travel',
      text: '彈性上下班',
    },
  ],
};
const clients: QueryClient[] = [];

const areaId = '61000000-0000-4000-8000-000000000001';
function task(n: number, title: string, area: string | null): JdWorkView['tasks'][number] {
  return {
    task_id: `62000000-0000-4000-8000-00000000000${String(n)}`,
    area_id: area,
    title,
    description: null,
    outcomes: [],
    requirements: [],
  };
}
/** One responsibility with a task, and two tasks that belong to none. */
const workJd: JdWorkView = {
  ...jd,
  areas: [{ area_id: areaId, title: '網站交付', scope_text: null }],
  tasks: [task(1, '實作網頁', areaId), task(2, '整理雜務', null), task(3, '回覆來信', null)],
};

function renderEditor(withOutline = false, view: JdWorkView = jd) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  clients.push(client);
  vi.stubGlobal(
    'fetch',
    vi.fn(() => Promise.resolve(Response.json(view))),
  );
  return render(
    <QueryClientProvider client={client}>
      {withOutline && <JdOutline />}
      <JdWorkEditor
        refresh={() => refreshQueries(client, formalJdQueries(fileId))}
        key={fileId}
        jobFileId={fileId}
      />
    </QueryClientProvider>,
  );
}

beforeEach(() => sessionStorage.clear());
afterEach(() => {
  clients.splice(0).forEach((client) => client.clear());
  vi.unstubAllGlobals();
  Reflect.deleteProperty(Element.prototype, 'scrollIntoView');
});

const sections = [
  { name: '所需知識', first: '財務知識', count: '2 項', add: '新增知識' },
  { name: '所需技能', first: '協調能力', count: '1 項', add: '新增技能' },
  { name: '主要協作對象', first: '採購部', count: '2 項', add: '新增協作對象' },
  { name: '工作條件與責任邊界', first: '辦公室工作', count: '3 項', add: '新增條件' },
];

test.each([false, true])(
  'cross links reveal nested task folds before scrolling (unassigned=%s)',
  async (unassigned) => {
    const targetTask = task(1, '實作網頁', unassigned ? null : areaId);
    const view: JdWorkView = {
      ...workJd,
      tasks: [targetTask],
      task_links: [
        { task_id: targetTask.task_id, capability_id: '31000000-0000-4000-8000-000000000001' },
      ],
    };
    const scrollIntoView = vi.fn(function (this: HTMLElement) {
      expect(this.closest('[hidden]')).toBeNull();
    });
    Object.defineProperty(Element.prototype, 'scrollIntoView', {
      value: scrollIntoView,
      configurable: true,
    });
    renderEditor(false, view);
    await screen.findByRole('button', { name: '收合任務 實作網頁' });
    await userEvent.click(screen.getByRole('button', { name: '收合任務 實作網頁' }));
    await userEvent.click(
      screen.getByRole('button', { name: unassigned ? '收合未歸屬任務' : '收合職責 網站交付' }),
    );
    await userEvent.click(screen.getByRole('button', { name: '收合職責與任務' }));
    const knowledge = screen.getByRole('region', { name: '所需知識' });
    await userEvent.click(within(knowledge).getByRole('link', { name: /實作網頁/ }));
    expect(screen.getByRole('button', { name: '收合職責與任務' })).toHaveAttribute(
      'aria-expanded',
      'true',
    );
    expect(screen.getByRole('button', { name: '收合任務 實作網頁' })).toHaveAttribute(
      'aria-expanded',
      'true',
    );
    const article = screen.getByRole('article', { name: '實作網頁' });
    expect(article).toHaveFocus();
    expect(window.location.hash).toBe(`#jd-task-${targetTask.task_id}`);
    expect(scrollIntoView.mock.contexts.at(-1)).toBe(article);
    await userEvent.click(within(knowledge).getByRole('button', { name: '收合所需知識' }));
    await userEvent.click(within(article).getByRole('link', { name: '財務知識' }));
    const capability = screen.getByRole('article', { name: '知識：財務知識' });
    expect(capability).toBeVisible();
    expect(capability).toHaveFocus();
    expect(within(knowledge).getByRole('button', { name: '收合所需知識' })).toHaveAttribute(
      'aria-expanded',
      'true',
    );
    expect(scrollIntoView.mock.contexts.at(-1)).toBe(capability);
  },
);

test.each(sections)(
  '$name folds to its heading and count and opens again',
  async ({ name, first, count, add }) => {
    renderEditor();
    const section = await screen.findByRole('region', { name });
    const toggle = within(section).getByRole('button', { name: `收合${name}` });
    expect(toggle).toHaveAttribute('aria-expanded', 'true');
    expect(within(section).getByText(count)).toBeVisible();
    expect(within(section).getByText(first)).toBeVisible();

    await userEvent.click(toggle);
    const closed = within(section).getByRole('button', { name: `展開${name}` });
    expect(closed).toHaveAttribute('aria-expanded', 'false');
    expect(within(section).getByRole('heading', { name })).toBeVisible();
    expect(within(section).getByText(count)).toBeVisible();
    expect(within(section).queryByText(first)).not.toBeVisible();
    expect(within(section).queryByRole('button', { name: add })).not.toBeInTheDocument();

    await userEvent.click(closed);
    expect(within(section).getByText(first)).toBeVisible();
    expect(within(section).getByRole('button', { name: add })).toBeVisible();
  },
);

test('choosing a folded section in the section bar opens it and scrolls to it', async () => {
  const scrollIntoView = vi.fn();
  Object.defineProperty(Element.prototype, 'scrollIntoView', {
    value: scrollIntoView,
    configurable: true,
    writable: true,
  });
  renderEditor(true);
  const section = await screen.findByRole('region', { name: '所需知識' });
  await userEvent.click(within(section).getByRole('button', { name: '收合所需知識' }));
  expect(within(section).queryByText('財務知識')).not.toBeVisible();

  const nav = screen.getByRole('navigation', { name: 'JD 章節導覽' });
  await userEvent.click(within(nav).getByRole('button', { name: '所需知識' }));
  expect(within(section).getByRole('button', { name: '收合所需知識' })).toHaveAttribute(
    'aria-expanded',
    'true',
  );
  expect(within(section).getByText('財務知識')).toBeVisible();
  expect(scrollIntoView.mock.contexts.at(-1)).toBe(section);
});

test('職責與任務 folds as one block: the responsibilities and the unassigned tasks go, the other sections stay', async () => {
  renderEditor(false, workJd);
  // The heading and its toggle are there while the data loads; the count and the content arrive with it.
  expect(await screen.findByText('1 項職責・3 項任務')).toBeVisible();
  const toggle = screen.getByRole('button', { name: '收合職責與任務' });
  expect(toggle).toHaveAttribute('aria-expanded', 'true');
  expect(screen.getByText('實作網頁')).toBeVisible();
  expect(screen.getByText('整理雜務')).toBeVisible();
  expect(screen.getByRole('button', { name: '新增職責' })).toBeVisible();

  await userEvent.click(toggle);
  expect(screen.getByRole('button', { name: '展開職責與任務' })).toHaveAttribute(
    'aria-expanded',
    'false',
  );
  expect(screen.getByRole('heading', { name: 'JD 職責與任務' })).toBeVisible();
  expect(screen.getByText('1 項職責・3 項任務')).toBeVisible();
  expect(screen.queryByText('實作網頁')).not.toBeVisible();
  expect(screen.queryByText('整理雜務')).not.toBeVisible();
  expect(screen.queryByRole('region', { name: '未歸屬任務' })).not.toBeInTheDocument();
  expect(screen.queryByRole('button', { name: '新增職責' })).not.toBeInTheDocument();
  expect(
    within(screen.getByRole('region', { name: '所需知識' })).getByText('財務知識'),
  ).toBeVisible();

  await userEvent.click(screen.getByRole('button', { name: '展開職責與任務' }));
  expect(screen.getByText('整理雜務')).toBeVisible();
  expect(screen.getByRole('button', { name: '新增職責' })).toBeVisible();
});

test('未歸屬任務 folds to its heading and count like a responsibility does, and opens again', async () => {
  renderEditor(false, workJd);
  const group = await screen.findByRole('region', { name: '未歸屬任務' });
  expect(within(group).getByText('2 項任務')).toBeVisible();
  expect(within(group).getByText('整理雜務')).toBeVisible();

  await userEvent.click(within(group).getByRole('button', { name: '收合未歸屬任務' }));
  expect(within(group).getByRole('button', { name: '展開未歸屬任務' })).toHaveAttribute(
    'aria-expanded',
    'false',
  );
  expect(within(group).getByRole('heading', { name: '未歸屬任務' })).toBeVisible();
  expect(within(group).getByText('2 項任務')).toBeVisible();
  expect(within(group).queryByText('整理雜務')).not.toBeVisible();
  expect(within(group).queryByRole('button', { name: '新增任務' })).not.toBeInTheDocument();
  expect(screen.getByText('實作網頁')).toBeVisible();

  await userEvent.click(within(group).getByRole('button', { name: '展開未歸屬任務' }));
  expect(within(group).getByText('整理雜務')).toBeVisible();
  expect(within(group).getByRole('button', { name: '新增任務' })).toBeVisible();
});

test('choosing 職責與任務 in the section bar opens it when it is folded', async () => {
  const scrollIntoView = vi.fn();
  Object.defineProperty(Element.prototype, 'scrollIntoView', {
    value: scrollIntoView,
    configurable: true,
    writable: true,
  });
  renderEditor(true, workJd);
  await userEvent.click(await screen.findByRole('button', { name: '收合職責與任務' }));
  expect(screen.queryByText('整理雜務')).not.toBeVisible();

  const nav = screen.getByRole('navigation', { name: 'JD 章節導覽' });
  await userEvent.click(within(nav).getByRole('button', { name: '職責與任務' }));
  expect(screen.getByRole('button', { name: '收合職責與任務' })).toHaveAttribute(
    'aria-expanded',
    'true',
  );
  expect(screen.getByText('整理雜務')).toBeVisible();
  expect(scrollIntoView).toHaveBeenCalled();
});
