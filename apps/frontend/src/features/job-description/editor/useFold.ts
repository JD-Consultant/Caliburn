import { useEffect, useId, useState, type RefObject } from 'react';
import { revealSectionEvent } from './jd-navigation';

/** 只管理收合呈現；導覽事件沿目標祖先展開，不卸載草稿。 */
export function useFold(ref: RefObject<HTMLElement | null>): {
  expanded: boolean;
  bodyId: string;
  toggle: () => void;
} {
  const [expanded, setExpanded] = useState(true);
  const bodyId = useId();
  useEffect(() => {
    const element = ref.current;
    const reveal = () => setExpanded(true);
    element?.addEventListener(revealSectionEvent, reveal);
    return () => element?.removeEventListener(revealSectionEvent, reveal);
  }, [ref]);
  return { expanded, bodyId, toggle: () => setExpanded((value) => !value) };
}
