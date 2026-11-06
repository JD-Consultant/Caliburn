import type { MouseEvent } from 'react';
import { flushSync } from 'react-dom';

export const revealSectionEvent = 'jd-reveal-section';

/** 展開仍掛載的祖先，再讓瀏覽器捲動及聚焦。 */
export function revealJdTarget(id: string): boolean {
  const target = document.getElementById(id);
  if (!target) return false;
  flushSync(() => target.dispatchEvent(new Event(revealSectionEvent, { bubbles: true })));
  let ancestor: HTMLElement | null = target;
  while (ancestor) {
    if (ancestor instanceof HTMLDetailsElement) ancestor.open = true;
    ancestor = ancestor.parentElement;
  }
  target.scrollIntoView({ block: 'start' });
  if (!target.hasAttribute('tabindex')) target.tabIndex = -1;
  target.focus({ preventScroll: true });
  return true;
}

export function navigateJdLink(event: MouseEvent<HTMLAnchorElement>): void {
  if (
    event.defaultPrevented ||
    event.button !== 0 ||
    event.metaKey ||
    event.ctrlKey ||
    event.shiftKey ||
    event.altKey
  )
    return;
  const hash = event.currentTarget.hash;
  if (!hash || !revealJdTarget(decodeURIComponent(hash.slice(1)))) return;
  event.preventDefault();
  if (window.location.hash !== hash)
    window.history.pushState(window.history.state, '', hash);
}
