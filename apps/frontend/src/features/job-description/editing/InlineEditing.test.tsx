import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, expect, it, vi } from 'vitest';
import { useState } from 'react';
import { jobDescription } from '../../../../tests/fixtures';
import { EditableText } from './EditableText';
import { JobDescriptionEditorProvider } from './JobDescriptionEditorProvider';

beforeEach(() => sessionStorage.clear());

function setup(readOnly = false) {
  const save = vi.fn((value: string) =>
    Promise.resolve({ ...jobDescription, purpose: value, version: 2 }),
  );
  render(
    <JobDescriptionEditorProvider
      jobDescription={jobDescription}
      onSaved={() => {}}
      readOnly={readOnly}
    >
      <EditableText
        draftKey="purpose"
        label="職務目的"
        value={null}
        multiline
        onSave={save}
      />
      <EditableText draftKey="title" label="職務名稱" value="分析師" onSave={save} />
    </JobDescriptionEditorProvider>,
  );
  return { save, user: userEvent.setup() };
}

it('點文字開單一編輯槽，Ctrl Enter 保存並歸還焦點', async () => {
  const { save, user } = setup();
  expect(screen.queryByRole('textbox')).not.toBeInTheDocument();
  await user.click(screen.getByRole('button', { name: '修改職務目的' }));
  const field = screen.getByRole('textbox', { name: '職務目的' });
  expect(field).toHaveFocus();
  await user.type(field, '分析需求');
  await user.click(screen.getByRole('button', { name: '修改職務名稱' }));
  expect(screen.queryByRole('textbox', { name: '職務名稱' })).not.toBeInTheDocument();
  expect(save).not.toHaveBeenCalled();
  fireEvent.keyDown(field, { key: 'Enter', ctrlKey: true });
  await waitFor(() => expect(save).toHaveBeenCalledTimes(1));
  await waitFor(() => expect(screen.queryByRole('textbox')).not.toBeInTheDocument());
  expect(screen.getByRole('button', { name: '修改職務目的' })).toHaveFocus();
});

it('單行 Enter 保存，IME Enter 不送出，Escape 取消不保存', async () => {
  const { save, user } = setup();
  await user.click(screen.getByRole('button', { name: '修改職務名稱' }));
  const field = screen.getByRole('textbox', { name: '職務名稱' });
  await user.clear(field);
  fireEvent.compositionStart(field);
  fireEvent.change(field, { target: { value: '業務' } });
  fireEvent.keyDown(field, { key: 'Enter', isComposing: true });
  expect(save).not.toHaveBeenCalled();
  fireEvent.compositionEnd(field);
  fireEvent.keyDown(field, { key: 'Enter' });
  await waitFor(() => expect(save).toHaveBeenCalledTimes(1));
  await waitFor(() => expect(screen.queryByRole('textbox')).not.toBeInTheDocument());
  await user.click(screen.getByRole('button', { name: '修改職務目的' }));
  await user.type(screen.getByRole('textbox'), '不保存');
  await user.keyboard('{Escape}');
  expect(screen.queryByRole('textbox')).not.toBeInTheDocument();
  expect(save).toHaveBeenCalledTimes(1);
});

it('唯讀不開編輯槽', async () => {
  const { save, user } = setup(true);
  await user.click(screen.getByText('分析師'));
  expect(screen.queryByRole('textbox')).not.toBeInTheDocument();
  expect(save).not.toHaveBeenCalled();
});

it('外部刪除編輯項目時釋放槽並保留可處理的草稿', async () => {
  const save = vi.fn();
  function Harness() {
    const [exists, setExists] = useState(true);
    return (
      <JobDescriptionEditorProvider jobDescription={jobDescription} onSaved={() => {}}>
        {exists && (
          <EditableText
            draftKey="removed-task"
            label="任務名稱"
            value="原任務"
            onSave={save}
          />
        )}
        <EditableText draftKey="title" label="職務名稱" value="分析師" onSave={save} />
        <button onClick={() => setExists(false)}>外部刪除任務</button>
      </JobDescriptionEditorProvider>
    );
  }
  render(<Harness />);
  const user = userEvent.setup();
  await user.click(screen.getByRole('button', { name: '修改任務名稱' }));
  await user.type(screen.getByRole('textbox'), '人工草稿');
  await user.click(screen.getByRole('button', { name: '外部刪除任務' }));
  expect(screen.getByRole('button', { name: '修改職務名稱' })).toHaveAttribute(
    'aria-disabled',
    'false',
  );
  expect(screen.getByRole('alert')).toHaveTextContent('保留');
  await user.click(screen.getByText('保留的輸入（1）'));
  expect(screen.getByText('原任務人工草稿')).toBeVisible();
  expect(save).not.toHaveBeenCalled();
});
