/** Two panes that stay mounted; narrow screens switch with tabs so polling, SSE and drafts survive. */
import { useState } from 'react';
import type { ReactNode } from 'react';
import { Tab, Tabs } from '@mui/material';

type PaneId = 'interview' | 'jd';

interface Props {
  bar: ReactNode;
  banner?: ReactNode;
  interview: ReactNode;
  document: ReactNode;
}

export function WorkspaceLayout({ bar, banner, interview, document }: Props) {
  const [active, setActive] = useState<PaneId>('interview');
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
        <section id="pane-interview" className="pane pane--interview" aria-label="訪談區">
          {interview}
        </section>
        <section id="pane-jd" className="pane pane--jd" aria-label="職務說明書區">
          {document}
        </section>
      </div>
    </main>
  );
}
