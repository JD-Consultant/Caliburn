/**
 * Section navigation for a long JD (SAP Fiori's anchor bar): jump to a section, and show which one
 * the reader is in. Sections are looked up by id when used, because they mount as data arrives.
 */
import { useEffect, useRef, useState } from 'react';
import { Chip } from '@mui/material';
import { jdSections } from './jd-section-ids';

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

export function JdOutline() {
  const nav = useRef<HTMLElement>(null);
  const [current, setCurrent] = useState<string | null>(null);

  useEffect(() => {
    const scroller = nav.current?.closest('.pane-scroll');
    if (!scroller) return;
    let frame = 0;
    const update = () => {
      cancelAnimationFrame(frame);
      frame = requestAnimationFrame(() => setCurrent(currentSectionId(scroller)));
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
          onClick={() => document.getElementById(id)?.scrollIntoView({ block: 'start' })}
        />
      ))}
    </nav>
  );
}
