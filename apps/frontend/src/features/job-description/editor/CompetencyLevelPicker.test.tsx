import { act, render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { useState } from 'react';
import { expect, it, vi } from 'vitest';
import { CompetencyLevelPicker } from './CompetencyLevelPicker';

it('級別可直接選取、用方向鍵切換，並清回未填', async () => {
  const onChange = vi.fn();
  function Field() {
    const [value, setValue] = useState<number | null>(null);
    return (
      <CompetencyLevelPicker
        label="基準職能級別"
        value={value}
        onChange={(next) => {
          setValue(next);
          onChange(next);
        }}
      />
    );
  }
  render(<Field />);
  const user = userEvent.setup();
  const group = within(screen.getByRole('group', { name: '基準職能級別' }));
  await user.click(group.getByRole('radio', { name: '第 3 級' }));
  expect(onChange).toHaveBeenLastCalledWith(3);
  await user.keyboard('{ArrowRight}');
  expect(onChange).toHaveBeenLastCalledWith(4);
  await user.click(group.getByRole('radio', { name: '未填' }));
  expect(onChange).toHaveBeenLastCalledWith(null);
});

it('禁止編輯時，全部級別都不可操作', () => {
  render(
    <CompetencyLevelPicker label="任務職能級別" value={4} disabled onChange={vi.fn()} />,
  );
  for (const radio of screen.getAllByRole('radio')) expect(radio).toBeDisabled();
  expect(screen.getByRole('radio', { name: '第 4 級' })).toBeChecked();
});

it('等待保存期間停用整組，完成後恢復因停用掉到頁面的焦點', async () => {
  let finish: () => void = () => {
    throw new Error('尚未建立保存');
  };
  const response = new Promise<boolean>((resolve) => {
    finish = () => resolve(true);
  });
  const save = vi.fn(() => response);
  render(<CompetencyLevelPicker label="級別" value={2} onChange={save} />);
  const user = userEvent.setup();
  const chosen = screen.getByRole('radio', { name: '第 3 級' });
  await user.click(chosen);
  for (const radio of screen.getAllByRole('radio')) expect(radio).toBeDisabled();
  await user.click(screen.getByRole('radio', { name: '第 2 級' }));
  expect(save).toHaveBeenCalledTimes(1);
  document.body.tabIndex = -1;
  document.body.focus();
  document.body.removeAttribute('tabindex');
  expect(document.body).toHaveFocus();
  await act(async () => {
    finish();
    await response;
  });
  expect(screen.getByRole('radio', { name: '第 2 級' })).toBeEnabled();
  expect(chosen).toHaveFocus();
});

it('保存期間使用者移到其他控制，完成後不搶回焦點', async () => {
  let finish: (value: boolean) => void = () => undefined;
  const response = new Promise<boolean>((resolve) => {
    finish = resolve;
  });
  render(
    <>
      <CompetencyLevelPicker label="級別" value={2} onChange={() => response} />
      <button type="button">其他操作</button>
    </>,
  );
  const user = userEvent.setup();
  await user.click(screen.getByRole('radio', { name: '第 3 級' }));
  const other = screen.getByRole('button', { name: '其他操作' });
  await user.click(other);
  await act(async () => {
    finish(true);
    await response;
  });
  expect(other).toHaveFocus();
});
