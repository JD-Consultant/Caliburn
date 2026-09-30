import { useEffect, useRef } from 'react';
import type { RefObject } from 'react';

const NEAR_BOTTOM_PX = 80;

/**
 * Keep a scroll container on its newest content, but only while the reader is already near the
 * bottom: reading older messages must never be interrupted by new content (Cloudscape chat rule).
 * The container must have one child that wraps all content; its size changes drive the follow.
 */
export function useStickToBottom<T extends HTMLElement>(): RefObject<T | null> {
  const ref = useRef<T>(null);
  useEffect(() => {
    const scroller = ref.current;
    if (!scroller) return;
    let followLatest = true;
    const onScroll = () => {
      followLatest =
        scroller.scrollHeight - scroller.scrollTop - scroller.clientHeight < NEAR_BOTTOM_PX;
    };
    const toBottom = () => {
      scroller.scrollTop = scroller.scrollHeight;
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
  return ref;
}
