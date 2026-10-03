/**
 * Section navigation for a long JD (SAP Fiori's anchor bar): jump to a section, and show which one
 * the reader is in. Sections are looked up by id when used, because they mount as data arrives.
 */
import { useEffect, useRef, useState } from 'react';
import { Chip } from '@mui/material';
import { jdSections, revealSectionEvent } from './jd-section-ids';

/** Distance from the top of the scroll area within which a section counts as the current one. */
const CURRENT_OFFSET_PX = 96;

function currentSectionId(scroller: Element): string | null {
  const top = scroller.getBoundingClientRect().top;
  let current: string | null = null;
  for (const { id } of jdSections) {
    const section = document.getElementById(id);
    if (!section) continue;
    if (current === null || section.getBoundingClientRect().top - top <= CURRENT_OFFSET_PX)
      current = id;
  }
  return current;
}

function isInView(scroller: Element, id: string): boolean {
  const section = document.getElementById(id);
  if (!section) return false;
  const view = scroller.getBoundingClientRect();
  const box = section.getBoundingClientRect();
  return box.top < view.bottom && box.bottom > view.top;
}

export function JdOutline() {
  const nav = useRef<HTMLElement>(null);
  // A section near the end cannot be scrolled up to the top, so the chosen one stays current
  // for as long as it is on screen.
  const chosen = useRef<string | null>(null);
  const [current, setCurrent] = useState<string | null>(null);

  useEffect(() => {
    const scroller = nav.current?.closest('.pane-scroll');
    if (!scroller) return;
    let frame = 0;
    const update = () => {
      cancelAnimationFrame(frame);
      frame = requestAnimationFrame(() => {
        if (chosen.current !== null && isInView(scroller, chosen.current)) {
          setCurrent(chosen.current);
          return;
        }
        chosen.current = null;
        setCurrent(currentSectionId(scroller));
      });
    };
    update();
    scroller.addEventListener('scroll', update, { passive: true });
    window.addEventListener('resize', update);
    return () => {
      cancelAnimationFrame(frame);
      scroller.removeEventListener('scroll', update);
      window.removeEventListener('resize', update);
    };
  }, []);

  function choose(id: string): void {
    chosen.current = id;
    setCurrent(id);
    const section = document.getElementById(id);
    // A folded section opens itself; the jump goes to its heading either way.
    section?.dispatchEvent(new Event(revealSectionEvent));
    section?.scrollIntoView({ block: 'start' });
  }

  return (
    <nav ref={nav} className="jd-outline" aria-label="JD 章節導覽">
      {jdSections.map(({ id, label }) => (
        <Chip
          key={id}
          size="small"
          label={label}
          clickable
          color={current === id ? 'primary' : 'default'}
          variant={current === id ? 'filled' : 'outlined'}
          aria-current={current === id ? 'location' : undefined}
          onClick={() => choose(id)}
        />
      ))}
    </nav>
  );
}
