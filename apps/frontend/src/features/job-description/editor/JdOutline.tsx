import { Chip } from '@mui/material';
import { useState } from 'react';
import { revealJdTarget } from './jd-navigation';

const sections = [
  { id: 'basic', label: '基本資料' },
  { id: 'duties', label: '職責與任務' },
  { id: 'competencies', label: '知識與技能' },
  { id: 'conditions', label: '協作與條件' },
];

export function JdOutline() {
  const [current, setCurrent] = useState<string | null>(null);
  return (
    <nav className="jd-outline" aria-label="JD 章節導覽">
      {sections.map(({ id, label }) => (
        <Chip
          key={id}
          size="small"
          label={label}
          clickable
          color={current === id ? 'primary' : 'default'}
          variant={current === id ? 'filled' : 'outlined'}
          aria-current={current === id ? 'location' : undefined}
          onClick={() => {
            setCurrent(id);
            revealJdTarget(`jd-${id}`);
          }}
        />
      ))}
    </nav>
  );
}
