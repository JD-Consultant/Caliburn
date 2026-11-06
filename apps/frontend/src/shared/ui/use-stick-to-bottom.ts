import { useEffect, useRef, useState } from 'react';
import type { RefObject } from 'react';

const NEAR_BOTTOM_PX = 80;

interface StickToBottom<T extends HTMLElement> {
  ref: RefObject<T | null>;
  /** True once the reader has scrolled up from the newest content, which is no longer followed. */
  away: boolean;
  /** Back to the newest content, and following it again. */
  scrollToBottom: () => void;
}

/**
 * Keep a scroll container on its newest content, but only while the reader is already near the
 * bottom: reading older messages must never be interrupted by new content (Cloudscape chat rule).
 * `away` tells the page when that has happened, so it can offer a way back (AI Elements' scroll button).
 * The container must have one child that wraps all content; its size changes drive the follow.
 */
export function useStickToBottom<T extends HTMLElement>(): StickToBottom<T> {
  const ref = useRef<T>(null);
  const [away, setAway] = useState(false);
  const jump = useRef<() => void>(() => undefined);
  useEffect(() => {
    const scroller = ref.current;
    if (!scroller) return;
    let followLatest = true;
    let lastTop = scroller.scrollTop;
    const onScroll = () => {
      const top = scroller.scrollTop;
      const gap = scroller.scrollHeight - top - scroller.clientHeight;
      // The browser reports our own scroll a frame late; if content grew meanwhile the gap is large
      // although the reader did nothing. Only scrollTop moving back means they scrolled up.
      if (gap < NEAR_BOTTOM_PX) followLatest = true;
      else if (top < lastTop) followLatest = false;
      lastTop = top;
      setAway(!followLatest);
    };
    const toBottom = () => {
      scroller.scrollTop = scroller.scrollHeight;
    };
    jump.current = () => {
      followLatest = true;
      setAway(false);
      toBottom();
    };
    scroller.addEventListener('scroll', onScroll, { passive: true });
    toBottom();
    const content = scroller.firstElementChild;
    const observer =
      content && typeof ResizeObserver !== 'undefined'
        ? new ResizeObserver(() => {
            if (followLatest) toBottom();
          })
        : null;
    if (content) observer?.observe(content);
    return () => {
      scroller.removeEventListener('scroll', onScroll);
      observer?.disconnect();
    };
  }, []);
  return { ref, away, scrollToBottom: () => jump.current() };
}
