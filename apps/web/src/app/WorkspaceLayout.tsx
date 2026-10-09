/** Two panes that stay mounted; narrow screens switch with tabs so polling, SSE and drafts survive. */
import { useState } from 'react';
import type { ReactNode } from 'react';
import { Tab, Tabs, useMediaQuery } from '@mui/material';

type PaneId = 'interview' | 'jd';

interface Props {
  bar: ReactNode;
  banner?: ReactNode;
  interview: ReactNode;
  document: ReactNode;
}

export function WorkspaceLayout({ bar, banner, interview, document }: Props) {
  const [active, setActive] = useState<PaneId>('interview');
  const narrow = useMediaQuery('(max-width: 899.95px)');
  return (
    <main className="workspace-root">
      {bar}
      {banner}
      <Tabs
        className="workspace-tabs"
        value={active}
        onChange={(_event, value: PaneId) => setActive(value)}
        variant="fullWidth"
        aria-label="工作區切換"
      >
        <Tab value="interview" label="訪談" id="tab-interview" aria-controls="pane-interview" />
        <Tab value="jd" label="JD" id="tab-jd" aria-controls="pane-jd" />
      </Tabs>
      <div className="workspace" data-active-pane={active}>
        <section
          id="pane-interview"
          className="pane pane--interview"
          role={narrow ? 'tabpanel' : 'region'}
          aria-label={narrow ? undefined : '訪談區'}
          aria-labelledby={narrow ? 'tab-interview' : undefined}
          hidden={narrow && active !== 'interview'}
        >
          {interview}
        </section>
        <section
          id="pane-jd"
          className="pane pane--jd"
          role={narrow ? 'tabpanel' : 'region'}
          aria-label={narrow ? undefined : '職務說明書區'}
          aria-labelledby={narrow ? 'tab-jd' : undefined}
          hidden={narrow && active !== 'jd'}
        >
          {document}
        </section>
      </div>
    </main>
  );
}
