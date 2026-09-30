/** A long JD is navigated by section (Fiori anchor bar) instead of by scrolling past everything. */
import { render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, expect, test, vi } from 'vitest';
import { JdOutline } from './JdOutline';

// jsdom has no layout, so scrollIntoView is absent; keep whatever was there and put it back.
const saved = Object.getOwnPropertyDescriptor(Element.prototype, 'scrollIntoView');

function stubScrollIntoView() {
  const scrollIntoView = vi.fn();
  Object.defineProperty(Element.prototype, 'scrollIntoView', {
    value: scrollIntoView,
    configurable: true,
    writable: true,
  });
  return scrollIntoView;
}

afterEach(() => {
  if (saved) Object.defineProperty(Element.prototype, 'scrollIntoView', saved);
  else Reflect.deleteProperty(Element.prototype, 'scrollIntoView');
});

test('lists the JD sections in reading order and scrolls the chosen one into view', async () => {
  const scrollIntoView = stubScrollIntoView();
  render(
    <>
      <JdOutline />
      <section id="jd-knowledge">知識區</section>
    </>,
  );
  const nav = screen.getByRole('navigation', { name: 'JD 章節導覽' });
  expect(
    within(nav)
      .getAllByRole('button')
      .map((button) => button.textContent),
  ).toEqual(['基本資料', '職責與任務', '所需知識', '所需技能', '協作對象', '工作條件']);

  await userEvent.click(within(nav).getByRole('button', { name: '所需知識' }));
  expect(scrollIntoView).toHaveBeenCalledTimes(1);
  expect(scrollIntoView.mock.contexts[0]).toBe(document.getElementById('jd-knowledge'));
});

test('choosing a section that has not loaded yet does nothing instead of failing', async () => {
  const scrollIntoView = stubScrollIntoView();
  render(<JdOutline />);
  await userEvent.click(screen.getByRole('button', { name: '工作條件' }));
  expect(scrollIntoView).not.toHaveBeenCalled();
});
