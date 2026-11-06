import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, expect, it, vi } from 'vitest';
import { useState, type ReactNode } from 'react';
import { jobDescription } from '../../../../tests/fixtures';
import { JobDescriptionEditorProvider } from '../editing/JobDescriptionEditorProvider';
import { JobDescriptionEditor } from './JobDescriptionEditor';
import { TaskCreateForm } from './TaskCreateForm';

beforeEach(() => sessionStorage.clear());

function Harness({ children }: { children: ReactNode }) {
  const [current, setCurrent] = useState(jobDescription);
  return (
    <JobDescriptionEditorProvider jobDescription={current} onSaved={setCurrent}>
      {children}
    </JobDescriptionEditorProvider>
  );
}

function renderForm(children: ReactNode) {
  return render(<Harness>{children}</Harness>);
}

it('建立任務一次送出獨立多筆成果、要求及新／既有知識技能', async () => {
  const onCreate = vi.fn().mockResolvedValue(true);
  const user = userEvent.setup();
  renderForm(
    <TaskCreateForm
      jobDescription={{
        ...jobDescription,
        knowledge: [{ id: 'existing-k', name: '法規', description: null }],
      }}
      dutyId="duty-a"
      onCreate={onCreate}
      onDone={() => undefined}
    />,
  );
  await user.type(screen.getByRole('textbox', { name: '任務名稱' }), '查核');
  await user.click(screen.getByText('一併加入成果、要求與知識技能'));
  await user.click(screen.getByRole('button', { name: '加入工作成果' }));
  await user.type(screen.getByRole('textbox', { name: '工作成果 1' }), '報告');
  await user.click(screen.getByRole('button', { name: '加入工作成果' }));
  await user.type(screen.getByRole('textbox', { name: '工作成果 2' }), '紀錄');
  await user.click(screen.getByRole('button', { name: '加入工作要求' }));
  await user.type(screen.getByRole('textbox', { name: '工作要求 1' }), '可追溯');
  await user.click(screen.getByRole('checkbox', { name: '法規' }));
  await user.click(screen.getByRole('button', { name: '加入新技能' }));
  await user.type(screen.getByRole('textbox', { name: '新技能名稱 1' }), '訪談');
  await user.click(screen.getByRole('button', { name: '建立任務' }));
  expect(onCreate).toHaveBeenCalledExactlyOnceWith({
    name: '查核',
    description: null,
    duty_id: 'duty-a',
    competency_level: null,
    outcomes: ['報告', '紀錄'],
    requirements: ['可追溯'],
    knowledge: [{ kind: 'existing', id: 'existing-k' }],
    skills: [{ kind: 'new', name: '訪談', description: null }],
  });
});

it('新增失敗保留表單輸入，避免使用者重填多筆內容', async () => {
  const user = userEvent.setup();
  const onDone = vi.fn();
  renderForm(
    <TaskCreateForm
      jobDescription={jobDescription}
      dutyId={null}
      onCreate={() => Promise.resolve(false)}
      onDone={onDone}
    />,
  );
  await user.type(screen.getByRole('textbox', { name: '任務名稱' }), '待確認任務');
  await user.click(screen.getByRole('button', { name: '建立任務' }));
  expect(screen.getByRole('textbox', { name: '任務名稱' })).toHaveValue('待確認任務');
  expect(onDone).not.toHaveBeenCalled();
});

it('重新掛載會展開未建立的任務草稿，核對前不送出', async () => {
  const fetch = vi.fn();
  vi.stubGlobal('fetch', fetch);
  const user = userEvent.setup();
  const view = renderForm(<JobDescriptionEditor />);
  await user.click(screen.getByRole('button', { name: '新增任務' }));
  await user.type(screen.getByRole('textbox', { name: '任務名稱' }), '保留的新增任務');
  view.unmount();
  renderForm(<JobDescriptionEditor />);
  expect(screen.getByRole('textbox', { name: '任務名稱' })).toHaveValue('保留的新增任務');
  expect(screen.getByRole('button', { name: '建立任務' })).toBeDisabled();
  expect(fetch).not.toHaveBeenCalled();
});
