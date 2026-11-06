import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, expect, it, vi } from 'vitest';
import { jobDescription } from '../../../../tests/fixtures';
import { JobDescriptionEditorProvider } from '../editing/JobDescriptionEditorProvider';
import { JobDescriptionEditor } from './JobDescriptionEditor';

beforeEach(() => {
  sessionStorage.clear();
  HTMLElement.prototype.scrollIntoView = vi.fn();
});

it('收合保留新增草稿，章節導覽展開並聚焦目標', async () => {
  const user = userEvent.setup();
  vi.stubGlobal('fetch', vi.fn());
  render(
    <JobDescriptionEditorProvider
      jobDescription={jobDescription}
      onSaved={() => undefined}
    >
      <JobDescriptionEditor />
    </JobDescriptionEditorProvider>,
  );
  await user.click(screen.getByRole('button', { name: '新增知識' }));
  await user.type(screen.getByRole('textbox', { name: '知識名稱' }), '尚未保存的知識');
  const input = screen.getByRole('textbox', { name: '知識名稱' });
  await user.click(screen.getByRole('button', { name: '收合知識與技能' }));
  expect(input).toBeInTheDocument();
  expect(input).not.toBeVisible();
  await user.click(screen.getByRole('button', { name: '知識與技能' }));
  expect(input).toBeVisible();
  expect(input).toHaveValue('尚未保存的知識');
  expect(screen.getByRole('region', { name: '知識與技能' })).toHaveFocus();
  expect(fetch).not.toHaveBeenCalled();
});
