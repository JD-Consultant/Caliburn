import { useState } from 'react';
import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, expect, it, vi } from 'vitest';
import { jobDescription } from '../../../../tests/fixtures';
import type { JobDescriptionResponse } from '../../../shared/api/generated/types.gen';
import { JobDescriptionEditorProvider } from './JobDescriptionEditorProvider';
import { EditableText } from './EditableText';
import { useJobDescriptionEditor } from './useJobDescriptionEditor';
import { storeDrafts } from './drafts';

beforeEach(() => sessionStorage.clear());

type Save = (
  text: string,
  current: JobDescriptionResponse,
) => Promise<JobDescriptionResponse>;
function Fields({ save }: { save: Save }) {
  const editor = useJobDescriptionEditor();
  return (
    <>
      <EditableText
        draftKey="purpose"
        label="職務目的"
        value={editor.jobDescription.purpose}
        onSave={save}
      />
      <button
        onClick={() => {
          void editor.execute((current) => save('第一筆', current));
          void editor.execute((current) => save('第二筆', current));
        }}
      >
        排入兩筆修改
      </button>
    </>
  );
}
function Editor({ save, readOnly = false }: { save: Save; readOnly?: boolean }) {
  const [current, setCurrent] = useState(jobDescription);
  return (
    <JobDescriptionEditorProvider
      jobDescription={current}
      onSaved={setCurrent}
      readOnly={readOnly}
    >
      <Fields save={save} />
    </JobDescriptionEditorProvider>
  );
}

it('保存佇列依序使用上筆成功版號', async () => {
  let finish: (jd: JobDescriptionResponse) => void = () => {
    throw new Error('尚未開始');
  };
  const save = vi
    .fn<Save>()
    .mockImplementationOnce(
      () =>
        new Promise((resolve) => {
          finish = resolve;
        }),
    )
    .mockImplementation((text, current) =>
      Promise.resolve({ ...current, purpose: text, version: current.version + 1 }),
    );
  render(<Editor save={save} />);
  fireEvent.click(screen.getByRole('button', { name: '排入兩筆修改' }));
  await waitFor(() => expect(save).toHaveBeenCalledTimes(1));
  await act(() => {
    finish({ ...jobDescription, purpose: '第一筆', version: 2 });
    return Promise.resolve();
  });
  await waitFor(() => expect(save).toHaveBeenCalledTimes(2));
  expect(save.mock.calls[1]?.[1].version).toBe(2);
});

it('第一筆結果不明停止後續佇列，不自動重送', async () => {
  const save = vi.fn<Save>().mockRejectedValue(new TypeError('offline'));
  render(<Editor save={save} />);
  fireEvent.click(screen.getByRole('button', { name: '排入兩筆修改' }));
  expect(await screen.findByRole('alert')).toHaveTextContent('無法確認');
  expect(save).toHaveBeenCalledTimes(1);
});

it('重開編輯頁取回同份 JD 草稿，核對前不能送出', async () => {
  storeDrafts(jobDescription.workspace_id, jobDescription.job_description_id, {
    purpose: { value: '尚未確認文字', baseValue: null, label: '職務目的' },
  });
  const save = vi.fn();
  render(<Editor save={save} />);
  await userEvent.setup().click(screen.getByRole('button', { name: '修改職務目的' }));
  expect(screen.getByRole('textbox', { name: '職務目的' })).toHaveValue('尚未確認文字');
  expect(screen.getByRole('button', { name: '套用輸入' })).toBeDisabled();
  fireEvent.keyDown(screen.getByRole('textbox'), { key: 'Enter' });
  expect(save).not.toHaveBeenCalled();
  expect(screen.getByRole('alert')).toHaveTextContent('保留');
});

it('背景新版本不覆蓋草稿，也不偷偷提升草稿寫入版號', async () => {
  const save = vi.fn<Save>().mockRejectedValue(new TypeError('conflict'));
  const saved = vi.fn();
  const view = render(
    <JobDescriptionEditorProvider jobDescription={jobDescription} onSaved={saved}>
      <Fields save={save} />
    </JobDescriptionEditorProvider>,
  );
  const user = userEvent.setup();
  await user.click(screen.getByRole('button', { name: '修改職務目的' }));
  await user.type(screen.getByRole('textbox'), '人工草稿');
  view.rerender(
    <JobDescriptionEditorProvider
      jobDescription={{ ...jobDescription, version: 2, purpose: '外部改版' }}
      onSaved={saved}
    >
      <Fields save={save} />
    </JobDescriptionEditorProvider>,
  );
  expect(screen.getByRole('textbox')).toHaveValue('人工草稿');
  await user.keyboard('{Enter}');
  await waitFor(() => expect(save).toHaveBeenCalledTimes(1));
  expect(save.mock.calls[0]?.[1].version).toBe(1);
  expect(screen.getByRole('textbox')).toHaveValue('人工草稿');
});

it('唯讀期間既有寫入入口與排隊工作都不送出', async () => {
  const save = vi.fn<Save>();
  render(<Editor save={save} readOnly />);
  fireEvent.click(screen.getByRole('button', { name: '排入兩筆修改' }));
  await act(async () => {});
  expect(save).not.toHaveBeenCalled();
});
