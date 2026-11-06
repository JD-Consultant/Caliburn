import { act, render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { useState } from 'react';
import { beforeEach, expect, it, vi } from 'vitest';
import { jobDescription } from '../../../../tests/fixtures';
import type {
  JobDescriptionResponse,
  TaskResponse,
} from '../../../shared/api/generated/types.gen';
import { JobDescriptionEditorProvider } from '../editing/JobDescriptionEditorProvider';
import { JobDescriptionEditor } from './JobDescriptionEditor';

const task: TaskResponse = {
  id: '22222222-2222-4222-8222-222222222222',
  name: '分析作業',
  description: null,
  competency_level: null,
  duty_id: null,
  outcomes: [],
  requirements: [],
  knowledge_ids: [],
  skill_ids: [],
};
const knowledge = {
  id: '33333333-3333-4333-8333-333333333333',
  name: '分析知識',
  description: null,
};
const initial: JobDescriptionResponse = { ...jobDescription, tasks: [task] };

function Harness({
  initialValue = initial,
  readOnly = false,
}: {
  initialValue?: JobDescriptionResponse;
  readOnly?: boolean;
}) {
  const [current, setCurrent] = useState(initialValue);
  return (
    <JobDescriptionEditorProvider
      jobDescription={current}
      onSaved={setCurrent}
      readOnly={readOnly}
    >
      <JobDescriptionEditor />
    </JobDescriptionEditorProvider>
  );
}

beforeEach(() => {
  sessionStorage.clear();
  HTMLElement.prototype.scrollIntoView = vi.fn();
});

const titledDuty = {
  id: '88888888-8888-4888-8888-888888888888',
  name: '營運資訊分析',
  scope: '固定職責範圍',
};
const titledDocument = {
  ...initial,
  duties: [titledDuty],
  tasks: [{ ...task, duty_id: titledDuty.id, description: '固定任務說明' }],
};

it.each([
  {
    name: titledDuty.name,
    field: '職責名稱',
    toggle: `職責 ${titledDuty.name}`,
    content: '固定職責範圍',
  },
  {
    name: task.name,
    field: '任務名稱',
    toggle: `任務 ${task.name}`,
    content: '固定任務說明',
  },
])(
  '$field 只呈現一份標題，文字編輯與箭頭收合互不干擾',
  async ({ name, field, toggle, content }) => {
    const user = userEvent.setup();
    const fetch = vi.fn();
    vi.stubGlobal('fetch', fetch);
    render(<Harness initialValue={titledDocument} />);
    expect(
      screen.getAllByText(name, { selector: '.inline-text__value, h3, h4' }),
    ).toHaveLength(1);
    await user.click(within(screen.getByRole('heading', { name })).getByText(name));
    expect(screen.getByRole('textbox', { name: field })).toHaveValue(name);
    expect(screen.getByText(content)).toBeVisible();
    const toggleButton = screen.getByRole('button', { name: `收合${toggle}` });
    expect(toggleButton).toHaveAttribute('aria-expanded', 'true');
    await user.keyboard('{Escape}');
    await user.click(toggleButton);
    expect(screen.queryByRole('textbox', { name: field })).not.toBeInTheDocument();
    expect(screen.getByText(content)).toBeInTheDocument();
    expect(screen.getByText(content)).not.toBeVisible();
    await user.click(screen.getByRole('button', { name: `展開${toggle}` }));
    expect(screen.getByText(content)).toBeVisible();
    expect(fetch).not.toHaveBeenCalled();
  },
);

function deferredResponse() {
  let resolve: (response: Response) => void = () => {
    throw new Error('Promise尚未初始化');
  };
  let reject: (reason: unknown) => void = () => {
    throw new Error('Promise尚未初始化');
  };
  const promise = new Promise<Response>((resolvePromise, rejectPromise) => {
    resolve = resolvePromise;
    reject = rejectPromise;
  });
  return { promise, resolve, reject };
}

it('既有文字明確保存原文，保留前後空白與換行', async () => {
  const purpose = '  工作目的\n保留原文  ';
  const fetch = vi
    .fn()
    .mockResolvedValue(Response.json({ ...initial, purpose, version: 2 }));
  vi.stubGlobal('fetch', fetch);
  const user = userEvent.setup();
  render(<Harness />);
  await user.click(screen.getByRole('button', { name: '修改職務目的' }));
  await user.type(screen.getByRole('textbox', { name: '職務目的' }), purpose);
  await user.keyboard('{Control>}{Enter}{/Control}');
  await waitFor(() => expect(fetch).toHaveBeenCalledTimes(1));
  expect(fetch).toHaveBeenCalledWith(
    expect.stringContaining('/job-descriptions/'),
    expect.objectContaining({
      method: 'PATCH',
      body: JSON.stringify({ expected_version: 1, purpose }),
    }),
  );
  expect(screen.getByRole('button', { name: '修改職務目的' })).toBeInTheDocument();
  expect(screen.getByText(/工作目的.*保留原文/)).toBeInTheDocument();
});

it('解除任務引用保留共用定義', async () => {
  const linked = {
    ...initial,
    knowledge: [knowledge],
    tasks: [{ ...task, knowledge_ids: [knowledge.id] }],
  };
  const fetch = vi
    .fn()
    .mockResolvedValue(Response.json({ ...linked, version: 2, tasks: [task] }));
  vi.stubGlobal('fetch', fetch);
  const user = userEvent.setup();
  render(<Harness initialValue={linked} />);
  await user.click(screen.getByRole('button', { name: '解除知識「分析知識」的引用' }));
  await waitFor(() =>
    expect(
      screen.queryByRole('button', { name: '解除知識「分析知識」的引用' }),
    ).not.toBeInTheDocument(),
  );
  expect(screen.getByRole('button', { name: '修改知識名稱' })).toBeInTheDocument();
  expect(fetch).toHaveBeenCalledWith(
    expect.stringContaining(`/tasks/${task.id}`),
    expect.objectContaining({
      method: 'PATCH',
      body: JSON.stringify({
        expected_version: 1,
        changes: [{ action: 'unlink_knowledge', id: knowledge.id }],
      }),
    }),
  );
});

it('解除引用連按只送出一次', async () => {
  const linked = {
    ...initial,
    knowledge: [knowledge],
    tasks: [{ ...task, knowledge_ids: [knowledge.id] }],
  };
  const unlinked = { ...linked, version: 2, tasks: [task] };
  const delayed = deferredResponse();
  const fetch = vi
    .fn()
    .mockReturnValueOnce(delayed.promise)
    .mockResolvedValue(Response.json(unlinked));
  vi.stubGlobal('fetch', fetch);
  const user = userEvent.setup();
  render(<Harness initialValue={linked} />);
  await user.dblClick(screen.getByRole('button', { name: '解除知識「分析知識」的引用' }));
  await act(async () => {
    delayed.resolve(Response.json(unlinked));
    await delayed.promise;
  });
  await waitFor(() =>
    expect(
      screen.queryByRole('button', { name: '解除知識「分析知識」的引用' }),
    ).not.toBeInTheDocument(),
  );
  expect(fetch).toHaveBeenCalledTimes(1);
});

it('建立並引用新知識只送一次Task PATCH，成功後同時顯示定義與引用', async () => {
  const linked: JobDescriptionResponse = {
    ...initial,
    knowledge: [knowledge],
    tasks: [{ ...task, knowledge_ids: [knowledge.id] }],
    version: 2,
  };
  const fetch = vi.fn().mockResolvedValue(Response.json(linked));
  vi.stubGlobal('fetch', fetch);
  const user = userEvent.setup();
  render(<Harness />);
  await user.click(screen.getByRole('button', { name: '建立並引用新知識' }));
  await user.type(screen.getByRole('textbox', { name: '知識名稱' }), '分析知識');
  await user.click(screen.getByRole('button', { name: '建立並引用知識' }));
  expect(fetch).toHaveBeenCalledTimes(1);
  expect(fetch).toHaveBeenCalledWith(
    expect.stringContaining(`/tasks/${task.id}`),
    expect.objectContaining({
      method: 'PATCH',
      body: JSON.stringify({
        expected_version: 1,
        changes: [
          { action: 'create_and_link_knowledge', name: '分析知識', description: null },
        ],
      }),
    }),
  );
  await screen.findByRole('button', { name: '解除知識「分析知識」的引用' });
  expect(screen.getByRole('button', { name: '修改知識名稱' })).toBeInTheDocument();
  expect(
    screen.queryByRole('button', { name: '建立並引用知識' }),
  ).not.toBeInTheDocument();
});

it('文字保存完成才開放排序，連按只送一次並使用更新版本', async () => {
  const secondTask: TaskResponse = {
    ...task,
    id: '44444444-4444-4444-8444-444444444444',
    name: '第二項任務',
  };
  const value: JobDescriptionResponse = { ...initial, tasks: [task, secondTask] };
  const saved: JobDescriptionResponse = { ...value, purpose: '新的目的', version: 2 };
  const moved: JobDescriptionResponse = {
    ...saved,
    tasks: [secondTask, task],
    version: 3,
  };
  const delayed = deferredResponse();
  const fetch = vi
    .fn()
    .mockReturnValueOnce(delayed.promise)
    .mockResolvedValueOnce(Response.json(moved));
  vi.stubGlobal('fetch', fetch);
  const user = userEvent.setup();
  render(<Harness initialValue={value} />);
  await user.click(screen.getByRole('button', { name: '修改職務目的' }));
  await user.type(screen.getByRole('textbox', { name: '職務目的' }), '新的目的');
  expect(screen.getByRole('button', { name: '下移分析作業' })).toBeDisabled();
  await user.keyboard('{Control>}{Enter}{/Control}');
  expect(fetch).toHaveBeenCalledTimes(1);
  await act(async () => {
    delayed.resolve(Response.json(saved));
    await delayed.promise;
  });
  await user.dblClick(screen.getByRole('button', { name: '下移分析作業' }));
  await waitFor(() => expect(fetch).toHaveBeenCalledTimes(2));
  expect(fetch).toHaveBeenLastCalledWith(
    expect.stringContaining(`/tasks/${task.id}`),
    expect.objectContaining({
      method: 'PATCH',
      body: JSON.stringify({
        expected_version: 2,
        placement: { destination_duty_id: null, before_id: null },
      }),
    }),
  );
});

it.each([
  {
    label: '知識',
    kind: 'knowledge' as const,
    referenceField: 'knowledge_ids' as const,
    action: 'create_and_link_knowledge',
  },
  {
    label: '技能',
    kind: 'skills' as const,
    referenceField: 'skill_ids' as const,
    action: 'create_and_link_skill',
  },
])(
  '建立並引用$label 未確認時禁止重送，F5保留輸入供核對與放棄',
  async ({ label, kind, referenceField, action }) => {
    const definition = { ...knowledge, name: `分析${label}` };
    const saved: JobDescriptionResponse = {
      ...initial,
      [kind]: [definition],
      tasks: [{ ...task, [referenceField]: [definition.id] }],
      version: 2,
    };
    const delayed = deferredResponse();
    const fetch = vi.fn().mockReturnValueOnce(delayed.promise);
    vi.stubGlobal('fetch', fetch);
    const user = userEvent.setup();
    const view = render(<Harness />);
    await user.click(screen.getByRole('button', { name: `建立並引用新${label}` }));
    await user.type(
      screen.getByRole('textbox', { name: `${label}名稱` }),
      definition.name,
    );
    await user.type(
      screen.getByRole('textbox', { name: `${label}說明（選填）` }),
      '尚待核對的說明',
    );
    await user.dblClick(screen.getByRole('button', { name: `建立並引用${label}` }));
    expect(fetch).toHaveBeenCalledTimes(1);
    expect(fetch).toHaveBeenCalledWith(
      expect.stringContaining(`/tasks/${task.id}`),
      expect.objectContaining({
        method: 'PATCH',
        body: JSON.stringify({
          expected_version: 1,
          changes: [{ action, name: definition.name, description: '尚待核對的說明' }],
        }),
      }),
    );
    await act(async () => {
      delayed.reject(new TypeError('offline'));
      await delayed.promise.catch(() => undefined);
    });
    expect(screen.getByRole('button', { name: `建立並引用${label}` })).toBeDisabled();
    view.unmount();
    render(<Harness />);
    expect(screen.getByRole('textbox', { name: `${label}名稱` })).toHaveValue(
      definition.name,
    );
    expect(screen.getByRole('textbox', { name: `${label}說明（選填）` })).toHaveValue(
      '尚待核對的說明',
    );
    expect(screen.getByRole('button', { name: `建立並引用${label}` })).toBeDisabled();
    expect(fetch).toHaveBeenCalledTimes(1);
    fetch.mockResolvedValueOnce(Response.json(saved));
    await user.click(screen.getByRole('button', { name: '重新讀取' }));
    await screen.findByRole('button', {
      name: `解除${label}「${definition.name}」的引用`,
    });
    await user.click(screen.getByRole('button', { name: '放棄新增' }));
    expect(
      screen.queryByRole('button', { name: `建立並引用${label}` }),
    ).not.toBeInTheDocument();
    expect(fetch).toHaveBeenCalledTimes(2);
    expect(fetch.mock.calls[1]?.[0]).toBe(
      `/api/workspaces/${initial.workspace_id}/job-description`,
    );
    expect(fetch.mock.calls[1]?.[1]).not.toHaveProperty('method');
  },
);

it('文字保存期間不能開第二槽，完成後新增使用最新版本', async () => {
  const duty = {
    id: '55555555-5555-4555-8555-555555555555',
    name: '新增的職責',
    scope: null,
  };
  const saved: JobDescriptionResponse = { ...initial, purpose: '修改目的', version: 2 };
  const added: JobDescriptionResponse = { ...saved, duties: [duty], version: 3 };
  const delayed = deferredResponse();
  const fetch = vi
    .fn()
    .mockReturnValueOnce(delayed.promise)
    .mockResolvedValueOnce(Response.json(added, { status: 201 }));
  vi.stubGlobal('fetch', fetch);
  const user = userEvent.setup();
  render(<Harness />);
  await user.click(screen.getByRole('button', { name: '修改職務目的' }));
  await user.type(screen.getByRole('textbox', { name: '職務目的' }), '修改目的');
  await user.keyboard('{Control>}{Enter}{/Control}');
  expect(screen.getByRole('button', { name: '新增職責' })).toBeDisabled();
  expect(fetch).toHaveBeenCalledTimes(1);
  await act(async () => {
    delayed.resolve(Response.json(saved));
    await delayed.promise;
  });
  await user.click(screen.getByRole('button', { name: '新增職責' }));
  await user.type(screen.getByRole('textbox', { name: '職責名稱' }), duty.name);
  await user.click(screen.getByRole('button', { name: '建立職責' }));
  await waitFor(() => expect(fetch).toHaveBeenCalledTimes(2));
  expect(fetch).toHaveBeenLastCalledWith(
    expect.stringContaining('/duties'),
    expect.objectContaining({
      method: 'POST',
      body: JSON.stringify({ expected_version: 2, name: duty.name, scope: null }),
    }),
  );
  expect(screen.queryByRole('button', { name: '建立職責' })).not.toBeInTheDocument();
});

it('建立並引用遇版本衝突保留輸入，核對後明示重送才使用新版本', async () => {
  const current = { ...initial, purpose: '其他編輯者更新的目的', version: 2 };
  const linked: JobDescriptionResponse = {
    ...current,
    knowledge: [knowledge],
    tasks: [{ ...task, knowledge_ids: [knowledge.id] }],
    version: 3,
  };
  const fetch = vi.fn().mockResolvedValueOnce(
    Response.json(
      {
        detail: { code: 'jd_concurrency_conflict', commit_status: 'not_committed' },
      },
      { status: 409 },
    ),
  );
  vi.stubGlobal('fetch', fetch);
  const user = userEvent.setup();
  render(<Harness />);
  await user.click(screen.getByRole('button', { name: '建立並引用新知識' }));
  await user.type(screen.getByRole('textbox', { name: '知識名稱' }), knowledge.name);
  await user.click(screen.getByRole('button', { name: '建立並引用知識' }));
  await screen.findByText(/這份 JD 已有其他變更/);
  expect(screen.getByRole('textbox', { name: '知識名稱' })).toHaveValue(knowledge.name);
  expect(screen.getByRole('button', { name: '建立並引用知識' })).toBeDisabled();
  expect(fetch).toHaveBeenCalledTimes(1);
  fetch.mockResolvedValueOnce(Response.json(current));
  await user.click(screen.getByRole('button', { name: '重新讀取' }));
  await user.click(await screen.findByRole('button', { name: '已核對，繼續編輯' }));
  expect(fetch).toHaveBeenCalledTimes(2);
  fetch.mockResolvedValueOnce(Response.json(linked));
  await user.click(screen.getByRole('button', { name: '建立並引用知識' }));
  await screen.findByRole('button', { name: '解除知識「分析知識」的引用' });
  expect(fetch).toHaveBeenCalledTimes(3);
  expect(fetch).toHaveBeenLastCalledWith(
    expect.stringContaining(`/tasks/${task.id}`),
    expect.objectContaining({
      method: 'PATCH',
      body: JSON.stringify({
        expected_version: 2,
        changes: [
          {
            action: 'create_and_link_knowledge',
            name: knowledge.name,
            description: null,
          },
        ],
      }),
    }),
  );
});

it('文字保存未確認時保留草稿，其他新增槽保持鎖定', async () => {
  const delayed = deferredResponse();
  const fetch = vi.fn().mockReturnValueOnce(delayed.promise);
  vi.stubGlobal('fetch', fetch);
  const user = userEvent.setup();
  render(<Harness />);
  await user.click(screen.getByRole('button', { name: '修改職務目的' }));
  await user.type(screen.getByRole('textbox', { name: '職務目的' }), '尚未確認的目的');
  await user.keyboard('{Control>}{Enter}{/Control}');
  await act(async () => {
    delayed.reject(new TypeError('offline'));
    await delayed.promise.catch(() => undefined);
  });
  await waitFor(() =>
    expect(screen.getByRole('button', { name: '新增職責' })).toBeDisabled(),
  );
  expect(screen.getByRole('textbox', { name: '職務目的' })).toHaveValue('尚未確認的目的');
  expect(fetch).toHaveBeenCalledTimes(1);
});

it('任務跨職責移動成功會展開目的職責，焦點落在任務收合按鈕', async () => {
  const source = {
    id: '66666666-6666-4666-8666-666666666666',
    name: '職責甲',
    scope: null,
  };
  const destination = {
    id: '77777777-7777-4777-8777-777777777777',
    name: '職責乙',
    scope: null,
  };
  const value: JobDescriptionResponse = {
    ...initial,
    duties: [source, destination],
    tasks: [{ ...task, duty_id: source.id }],
  };
  const moved: JobDescriptionResponse = {
    ...value,
    tasks: [{ ...task, duty_id: destination.id }],
    version: 2,
  };
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue(Response.json(moved)));
  const user = userEvent.setup();
  render(<Harness initialValue={value} />);
  const destinationToggle = screen.getByRole('button', { name: '收合職責 職責乙' });
  await user.click(destinationToggle);
  expect(destinationToggle).toHaveAttribute('aria-expanded', 'false');
  await user.selectOptions(
    screen.getByRole('combobox', { name: '移至職責' }),
    destination.id,
  );
  await waitFor(() => expect(destinationToggle).toHaveAttribute('aria-expanded', 'true'));
  const taskToggle = screen.getByRole('button', { name: `收合任務 ${task.name}` });
  expect(taskToggle).toHaveFocus();
  expect(taskToggle).toHaveAttribute('aria-expanded', 'true');
});

it('唯讀保留內容與導覽，禁止新增、排序、級別與刪除', () => {
  render(
    <Harness
      readOnly
      initialValue={{
        ...initial,
        knowledge: [knowledge],
        tasks: [{ ...task, knowledge_ids: [knowledge.id] }],
      }}
    />,
  );
  expect(screen.getByRole('button', { name: '新增職責' })).toBeDisabled();
  expect(screen.getByRole('button', { name: '新增知識' })).toBeDisabled();
  expect(screen.getByRole('button', { name: '刪除知識「分析知識」' })).toBeDisabled();
  expect(
    screen.getByRole('button', { name: '解除知識「分析知識」的引用' }),
  ).toBeDisabled();
  expect(screen.getByRole('combobox', { name: '移至職責' })).toBeDisabled();
  for (const radio of screen.getAllByRole('radio')) expect(radio).toBeDisabled();
  expect(screen.getByRole('button', { name: '修改職務目的' })).toHaveAttribute(
    'aria-disabled',
    'true',
  );
  expect(screen.getByRole('button', { name: '收合職責與任務' })).not.toBeDisabled();
});

it('刪除使用中的知識明示解除引用，確認後保留任務', async () => {
  const linked = {
    ...initial,
    knowledge: [knowledge],
    tasks: [{ ...task, knowledge_ids: [knowledge.id] }],
  };
  const fetch = vi.fn().mockResolvedValue(Response.json({ ...initial, version: 2 }));
  vi.stubGlobal('fetch', fetch);
  const user = userEvent.setup();
  render(<Harness initialValue={linked} />);
  await user.click(screen.getByRole('button', { name: '刪除知識「分析知識」' }));
  expect(
    screen.getByText('刪除「分析知識」會解除 1 個任務的引用；任務本身會保留。'),
  ).toBeInTheDocument();
  await user.click(screen.getByRole('button', { name: '確認刪除' }));
  await waitFor(() =>
    expect(
      screen.queryByRole('button', { name: '刪除知識「分析知識」' }),
    ).not.toBeInTheDocument(),
  );
  expect(screen.getByRole('heading', { name: '分析作業' })).toBeInTheDocument();
  expect(fetch).toHaveBeenCalledWith(
    expect.stringContaining(`/knowledge/${knowledge.id}?expected_version=1`),
    expect.objectContaining({ method: 'DELETE' }),
  );
});
