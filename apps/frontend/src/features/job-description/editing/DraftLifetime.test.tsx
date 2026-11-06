import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, expect, it, vi } from 'vitest';
import { jobDescription } from '../../../../tests/fixtures';
import type { JobDescriptionResponse } from '../../../shared/api/generated/types.gen';
import { JobDescriptionEditor } from '../editor/JobDescriptionEditor';
import { JobDescriptionEditorProvider } from './JobDescriptionEditorProvider';
import { EditableText } from './EditableText';
import { loadDrafts } from './drafts';
import { useJobDescriptionEditor } from './useJobDescriptionEditor';

beforeEach(() => sessionStorage.clear());

it('舊頁面晚到的成功回覆不會清掉重新進入後輸入的持久草稿', async () => {
  let finish: (value: JobDescriptionResponse) => void = () => {
    throw new Error('保存尚未開始');
  };
  const save = vi.fn(
    () =>
      new Promise<JobDescriptionResponse>((resolve) => {
        finish = resolve;
      }),
  );
  const saved = vi.fn();
  function Harness() {
    return (
      <JobDescriptionEditorProvider jobDescription={jobDescription} onSaved={saved}>
        <EditableText draftKey="purpose" label="職務目的" value={null} onSave={save} />
      </JobDescriptionEditorProvider>
    );
  }
  const first = render(<Harness />);
  fireEvent.click(screen.getByRole('button', { name: '修改職務目的' }));
  fireEvent.change(screen.getByRole('textbox', { name: '職務目的' }), {
    target: { value: '第一筆' },
  });
  fireEvent.keyDown(screen.getByRole('textbox', { name: '職務目的' }), { key: 'Enter' });
  await waitFor(() => expect(save).toHaveBeenCalledTimes(1));
  first.unmount();
  render(<Harness />);
  fireEvent.click(screen.getByRole('button', { name: '修改職務目的' }));
  fireEvent.change(screen.getByRole('textbox', { name: '職務目的' }), {
    target: { value: '回來後的新文字' },
  });
  await act(() => {
    finish({ ...jobDescription, purpose: '第一筆', version: 2 });
    return Promise.resolve();
  });
  await waitFor(() => expect(saved).toHaveBeenCalledTimes(1));
  expect(screen.getByRole('textbox', { name: '職務目的' })).toHaveValue('回來後的新文字');
  expect(
    loadDrafts(jobDescription.workspace_id, jobDescription.job_description_id).purpose
      ?.value,
  ).toBe('回來後的新文字');
});

it('建立並引用知識途中離開頁面，原子回覆仍更新快取且不改寫保留草稿', async () => {
  const task = {
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
  const initial = { ...jobDescription, tasks: [task] };
  const created = {
    ...initial,
    version: 2,
    tasks: [{ ...task, knowledge_ids: ['33333333-3333-4333-8333-333333333333'] }],
    knowledge: [
      {
        id: '33333333-3333-4333-8333-333333333333',
        name: '分析知識',
        description: null,
      },
    ],
  };
  let finish: (value: Response) => void = () => {
    throw new Error('建立尚未開始');
  };
  const fetch = vi.fn(
    () =>
      new Promise<Response>((resolve) => {
        finish = resolve;
      }),
  );
  vi.stubGlobal('fetch', fetch);
  const saved = vi.fn();
  const user = userEvent.setup();
  const view = render(
    <JobDescriptionEditorProvider jobDescription={initial} onSaved={saved}>
      <JobDescriptionEditor />
    </JobDescriptionEditorProvider>,
  );
  await user.click(screen.getByRole('button', { name: '建立並引用新知識' }));
  await user.type(screen.getByRole('textbox', { name: '知識名稱' }), '分析知識');
  await user.click(screen.getByRole('button', { name: '建立並引用知識' }));
  await waitFor(() => expect(fetch).toHaveBeenCalledTimes(1));
  const draftsBeforeLeaving = loadDrafts(
    initial.workspace_id,
    initial.job_description_id,
  );
  view.unmount();
  await act(() => {
    finish(Response.json(created));
    return Promise.resolve();
  });
  await waitFor(() => expect(saved).toHaveBeenCalledWith(created));
  expect(fetch).toHaveBeenCalledTimes(1);
  expect(loadDrafts(initial.workspace_id, initial.job_description_id)).toEqual(
    draftsBeforeLeaving,
  );
});

it('沒有保留輸入的操作失敗經核對後，新文字恢復明確保存', async () => {
  const save = vi.fn((value: string) =>
    Promise.resolve({ ...jobDescription, purpose: value, version: 2 }),
  );
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue(Response.json(jobDescription)));
  function Fields() {
    const editor = useJobDescriptionEditor();
    return (
      <>
        <button
          onClick={() => {
            void editor.execute(() => Promise.reject(new TypeError('offline')));
          }}
        >
          非文字操作
        </button>
        <EditableText draftKey="purpose" label="職務目的" value={null} onSave={save} />
      </>
    );
  }
  render(
    <JobDescriptionEditorProvider jobDescription={jobDescription} onSaved={() => {}}>
      <Fields />
    </JobDescriptionEditorProvider>,
  );
  const user = userEvent.setup();
  await user.click(screen.getByRole('button', { name: '非文字操作' }));
  await screen.findByRole('alert');
  await user.click(screen.getByRole('button', { name: '重新讀取' }));
  await user.click(await screen.findByRole('button', { name: '已核對，繼續編輯' }));
  await user.click(screen.getByRole('button', { name: '修改職務目的' }));
  fireEvent.change(screen.getByRole('textbox', { name: '職務目的' }), {
    target: { value: '新的輸入' },
  });
  fireEvent.keyDown(screen.getByRole('textbox', { name: '職務目的' }), { key: 'Enter' });
  await waitFor(() => expect(save).toHaveBeenCalledTimes(1));
});
