import { render, screen } from '@testing-library/react';
import { expect, test } from 'vitest';
import { focusDialogInput } from './dialog-focus';

test('初次進入對話框可定位名稱欄', () => {
  render(
    <div role="dialog" tabIndex={-1}>
      <input aria-label="名稱" />
      <textarea aria-label="內容" />
    </div>,
  );
  screen.getByRole('dialog').focus();
  const input = screen.getByRole<HTMLInputElement>('textbox', { name: '名稱' });
  focusDialogInput(input);
  expect(input).toHaveFocus();
});

test('動畫結束前使用者已移到內容欄，就不搶回名稱欄', () => {
  render(
    <div role="dialog">
      <input aria-label="名稱" />
      <textarea aria-label="內容" />
    </div>,
  );
  const content = screen.getByRole('textbox', { name: '內容' });
  content.focus();
  focusDialogInput(screen.getByRole<HTMLInputElement>('textbox', { name: '名稱' }));
  expect(content).toHaveFocus();
});
