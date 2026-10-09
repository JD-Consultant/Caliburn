/** Reveal mounted JD ancestors before browser scrolling and focus; links retain their fragment URLs. */
import type { MouseEvent } from 'react';
import { flushSync } from 'react-dom';
import { revealSectionEvent } from './jd-section-ids';

export function revealJdTarget(id: string): boolean {
  const target = document.getElementById(id);
  if (!target) return false;
  // Browser scrolling/focus needs the committed DOM, including every ancestor's hidden body.
  flushSync(() => target.dispatchEvent(new Event(revealSectionEvent, { bubbles: true })));
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
  const link = event.currentTarget;
  if (link.target && link.target !== '_self') return;
  const hash = link.hash;
  if (!hash || !revealJdTarget(decodeURIComponent(hash.slice(1)))) return;
  event.preventDefault();
  if (window.location.hash !== hash) window.history.pushState(window.history.state, '', hash);
}
