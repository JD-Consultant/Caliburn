/** Fragment links keep browser alternate activation while revealing normal keyboard/click destinations. */
import { fireEvent, render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, expect, test, vi } from 'vitest';
import { FoldableSection } from './FoldableSection';
import { navigateJdLink } from './jd-navigation';

afterEach(() => {
  Reflect.deleteProperty(Element.prototype, 'scrollIntoView');
  window.history.replaceState(null, '', window.location.pathname);
});

test('modified clicks retain their native fragment link behavior', async () => {
  const scroll = vi.fn();
  Object.defineProperty(Element.prototype, 'scrollIntoView', { value: scroll, configurable: true });
  render(
    <>
      <a href="#destination" onClick={navigateJdLink}>
        跳轉
      </a>
      <FoldableSection id="destination" title="目標" count={1}>
        正文
      </FoldableSection>
    </>,
  );
  await userEvent.click(screen.getByRole('button', { name: '收合目標' }));
  const link = screen.getByRole('link', { name: '跳轉' });
  for (const modifier of ['ctrlKey', 'metaKey', 'shiftKey', 'altKey']) {
    expect(fireEvent.click(link, { [modifier]: true })).toBe(true);
  }
  expect(scroll).not.toHaveBeenCalled();
  expect(screen.getByText('正文')).not.toBeVisible();
});

test('keyboard navigation commits reveal before scrolling and retains a mounted draft on repeated jumps', async () => {
  const scroll = vi.fn(function (this: HTMLElement) {
    expect(this.querySelector('[hidden]')).toBeNull();
  });
  Object.defineProperty(Element.prototype, 'scrollIntoView', { value: scroll, configurable: true });
  render(
    <>
      <a href="#destination" onClick={navigateJdLink}>
        跳轉
      </a>
      <FoldableSection id="destination" title="目標" count={1}>
        <input aria-label="未送出草稿" />
      </FoldableSection>
    </>,
  );
  const draft = screen.getByRole('textbox', { name: '未送出草稿' });
  await userEvent.type(draft, '保留文字');
  for (let index = 0; index < 2; index++) {
    await userEvent.click(screen.getByRole('button', { name: '收合目標' }));
    screen.getByRole('link', { name: '跳轉' }).focus();
    await userEvent.keyboard('{Enter}');
    expect(screen.getByRole('region', { name: '目標' })).toHaveFocus();
    expect(draft).toBeVisible();
    expect(draft).toHaveValue('保留文字');
    expect(window.location.hash).toBe('#destination');
  }
  expect(scroll).toHaveBeenCalledTimes(2);
});
