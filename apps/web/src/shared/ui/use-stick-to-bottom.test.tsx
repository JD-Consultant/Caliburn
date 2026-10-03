/** The chat follows new content only while the reader is at the bottom; it must never mistake its
 * own scrolling, or content that grew meanwhile, for the reader scrolling up. */
import { act, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, beforeEach, expect, test, vi } from 'vitest';
import { useStickToBottom } from './use-stick-to-bottom';

let notifyResize: () => void = () => undefined;

beforeEach(() => {
  vi.stubGlobal(
    'ResizeObserver',
    class {
      constructor(callback: () => void) {
        notifyResize = callback;
      }
      observe(): void {}
      disconnect(): void {}
    },
  );
});
afterEach(() => vi.unstubAllGlobals());

function Harness() {
  const { ref, away, scrollToBottom } = useStickToBottom<HTMLDivElement>();
  return (
    <>
      <div ref={ref} data-testid="scroller">
        <div />
      </div>
      <output data-testid="away">{String(away)}</output>
      <button onClick={scrollToBottom}>jump</button>
    </>
  );
}

/** jsdom has no layout: give the element a scroll box whose scrollTop clamps like a browser's. */
function scrollBox(element: HTMLElement, clientHeight: number, scrollHeight: number) {
  let top = 0;
  const box = { scrollHeight };
  Object.defineProperties(element, {
    clientHeight: { configurable: true, get: () => clientHeight },
    scrollHeight: { configurable: true, get: () => box.scrollHeight },
    scrollTop: {
      configurable: true,
      get: () => top,
      set: (value: number) => {
        top = Math.max(0, Math.min(value, box.scrollHeight - clientHeight));
      },
    },
  });
  return {
    grow(to: number): void {
      box.scrollHeight = to;
      const before = top;
      notifyResize();
      // A browser reports every scroll, including the ones the page makes itself.
      if (top !== before) element.dispatchEvent(new Event('scroll'));
    },
    /** The DOM grew, but the frame's resize notification has not run yet. */
    growWithoutNotice(to: number): void {
      box.scrollHeight = to;
    },
    userScrollsTo(value: number): void {
      top = value;
      element.dispatchEvent(new Event('scroll'));
    },
    scrollEvent(): void {
      element.dispatchEvent(new Event('scroll'));
    },
  };
}

test('keeps following when more content arrives before the browser reports our own scroll', () => {
  const { getByTestId } = render(<Harness />);
  const scroller = getByTestId('scroller');
  const box = scrollBox(scroller, 500, 1000);
  box.grow(1176); // a pending bubble appears: the view follows to the new bottom
  expect(scroller.scrollTop).toBe(676);
  // Next frame: more content (the "working" indicator) was added, then the browser dispatches the
  // scroll event for the scroll we made, and only afterwards runs the resize notification. The
  // handler sees a 115px gap that the reader did not cause.
  box.growWithoutNotice(1291);
  box.scrollEvent();
  notifyResize();
  expect(scroller.scrollTop).toBe(791);
});

test('stops following when the reader scrolls up, and resumes when they return to the bottom', () => {
  const { getByTestId } = render(<Harness />);
  const scroller = getByTestId('scroller');
  const box = scrollBox(scroller, 500, 1000);
  box.grow(1000);
  box.userScrollsTo(300);
  box.grow(1200);
  expect(scroller.scrollTop).toBe(300); // reading older messages is never interrupted
  box.userScrollsTo(690); // back within 80px of the bottom (1200 - 500 = 700)
  box.grow(1300);
  expect(scroller.scrollTop).toBe(800);
});

test('says when the reader is away from the newest content, and jumping back follows it again', () => {
  const { getByTestId } = render(<Harness />);
  const scroller = getByTestId('scroller');
  const box = scrollBox(scroller, 500, 1000);
  box.grow(1000);
  expect(getByTestId('away')).toHaveTextContent('false');

  act(() => box.userScrollsTo(300));
  expect(getByTestId('away')).toHaveTextContent('true');
  box.grow(1200);
  expect(scroller.scrollTop).toBe(300);

  fireEvent.click(screen.getByRole('button', { name: 'jump' }));
  expect(scroller.scrollTop).toBe(700);
  // New content can arrive before the browser reports the jump itself: it is still followed.
  box.grow(1300);
  expect(scroller.scrollTop).toBe(800);
  act(() => box.scrollEvent());
  expect(getByTestId('away')).toHaveTextContent('false');
});

test('content that grows while the reader waits at the bottom does not make them away', () => {
  const { getByTestId } = render(<Harness />);
  const scroller = getByTestId('scroller');
  const box = scrollBox(scroller, 500, 1000);
  box.grow(1000);
  box.growWithoutNotice(1400);
  act(() => box.scrollEvent());
  expect(getByTestId('away')).toHaveTextContent('false');
});
