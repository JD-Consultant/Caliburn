/**
 * The open or closed state of one foldable block of the JD: a section, a responsibility, a task. Folding is
 * presentation only, so the block's content stays mounted and nothing reloads or resets. Pass the ref of the
 * block's element so JD navigation can open it. The reveal event bubbles from the destination through its
 * foldable ancestors, without navigation owning or copying their local state.
 */
import { useEffect, useId, useState } from 'react';
import type { RefObject } from 'react';
import { revealSectionEvent } from './jd-section-ids';

export interface FoldState {
  expanded: boolean;
  /** Ties the toggle to the body it shows and hides. */
  bodyId: string;
  toggle: () => void;
}

export function useFold(reveal?: RefObject<HTMLElement | null>): FoldState {
  const [expanded, setExpanded] = useState(true);
  const bodyId = useId();
  useEffect(() => {
    const element = reveal?.current;
    const open = () => setExpanded(true);
    element?.addEventListener(revealSectionEvent, open);
    return () => element?.removeEventListener(revealSectionEvent, open);
  }, [reveal]);
  return { expanded, bodyId, toggle: () => setExpanded((value) => !value) };
}
