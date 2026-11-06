import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, expect, it } from 'vitest';
import { jobDescription } from '../../../../tests/fixtures';
import { loadDrafts, storeDrafts } from '../editing/drafts';
import { JobDescriptionEditorProvider } from '../editing/JobDescriptionEditorProvider';
import { CreatePanel, TextCreateForm } from './EditorForms';

beforeEach(() => sessionStorage.clear());

function Harness({
  showFirst = true,
  showSecond = false,
}: { showFirst?: boolean; showSecond?: boolean } = {}) {
  return (
    <JobDescriptionEditorProvider
      jobDescription={jobDescription}
      onSaved={() => undefined}
    >
      {showFirst && (
        <CreatePanel title="新增工作成果" draftKey="create-outcome">
          {(close) => (
            <TextCreateForm
              label="工作成果"
              onCreate={() => Promise.resolve(true)}
              onDone={close}
              disabled={false}
              draftKey="create-outcome"
            />
          )}
        </CreatePanel>
      )}
      {showSecond && (
        <CreatePanel title="新增第二筆" draftKey="create-second">
          {(close) => (
            <TextCreateForm
              label="第二筆"
              onCreate={() => Promise.resolve(true)}
              onDone={close}
              disabled={false}
              draftKey="create-second"
            />
          )}
        </CreatePanel>
      )}
    </JobDescriptionEditorProvider>
  );
}

it('持久草稿初次展開不搶焦點，放棄後焦點返回新增按鈕', async () => {
  storeDrafts(jobDescription.workspace_id, jobDescription.job_description_id, {
    'create-outcome': {
      value: JSON.stringify({ text: '保留的工作成果' }),
      baseValue: null,
      label: '新增工作成果',
    },
  });
  render(<button type="button">文件工具</button>);
  const currentControl = screen.getByRole('button', { name: '文件工具' });
  currentControl.focus();
  render(<Harness />);
  expect(screen.getByRole('textbox', { name: '工作成果' })).toHaveValue('保留的工作成果');
  expect(currentControl).toHaveFocus();

  const user = userEvent.setup();
  await user.click(screen.getByRole('button', { name: '放棄新增' }));
  expect(screen.queryByRole('textbox', { name: '工作成果' })).not.toBeInTheDocument();
  expect(screen.getByRole('button', { name: '新增工作成果' })).toHaveFocus();
});

it('使用者開啟表單會聚焦輸入，放棄後可再次開啟並聚焦', async () => {
  const user = userEvent.setup();
  render(<Harness />);
  await user.click(screen.getByRole('button', { name: '新增工作成果' }));
  expect(screen.getByRole('textbox', { name: '工作成果' })).toHaveFocus();
  await user.type(screen.getByRole('textbox', { name: '工作成果' }), '尚未建立的成果');
  await user.click(screen.getByRole('button', { name: '放棄新增' }));
  expect(screen.getByRole('button', { name: '新增工作成果' })).toHaveFocus();

  await user.click(screen.getByRole('button', { name: '新增工作成果' }));
  expect(screen.getByRole('textbox', { name: '工作成果' })).toHaveFocus();
});

it('新增目標被外部移除時釋放編輯槽，保留尚未確認草稿', async () => {
  const user = userEvent.setup();
  const view = render(<Harness showSecond />);
  await user.click(screen.getByRole('button', { name: '新增工作成果' }));
  await user.type(screen.getByRole('textbox', { name: '工作成果' }), '不應遺失的草稿');
  expect(screen.getByRole('button', { name: '新增第二筆' })).toBeDisabled();
  view.rerender(<Harness showFirst={false} showSecond />);
  expect(screen.getByRole('button', { name: '新增第二筆' })).not.toBeDisabled();
  expect(
    loadDrafts(jobDescription.workspace_id, jobDescription.job_description_id)[
      'create-outcome'
    ]?.value,
  ).toBe(JSON.stringify({ text: '不應遺失的草稿' }));
});
