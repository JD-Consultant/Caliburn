import { fireEvent, render, screen } from '@testing-library/react';
import { beforeEach, expect, it, vi } from 'vitest';
import { Dialog } from './Dialog';

beforeEach(() => {
  HTMLDialogElement.prototype.showModal = function () {
    this.setAttribute('open', '');
  };
  HTMLDialogElement.prototype.close = function () {
    this.removeAttribute('open');
  };
});

it('Escape 的原生 cancel 預設關閉由受控 onClose 裁決', () => {
  const onClose = vi.fn();
  render(
    <Dialog title="待確認保存" onClose={onClose}>
      <p>寫入尚未完成</p>
    </Dialog>,
  );
  const dialog = screen.getByRole('dialog');
  const event = new Event('cancel', { bubbles: false, cancelable: true });
  fireEvent(dialog, event);
  expect(event.defaultPrevented).toBe(true);
  expect(onClose).toHaveBeenCalledOnce();
  expect(dialog).toHaveAttribute('open');
});
