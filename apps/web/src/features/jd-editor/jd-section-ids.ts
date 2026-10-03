/** Anchors of the JD's top-level sections, shared by the sections and the outline that jumps to them. */
export const jdSections = [
  { id: 'jd-profile', label: '基本資料' },
  { id: 'jd-work', label: '職責與任務' },
  { id: 'jd-knowledge', label: '所需知識' },
  { id: 'jd-skill', label: '所需技能' },
  { id: 'jd-collaborators', label: '協作對象' },
  { id: 'jd-conditions', label: '工作條件' },
] as const;

/** Sent to a section element to ask it to open itself; the section bar sends it before jumping there. */
export const revealSectionEvent = 'jd-reveal-section';
