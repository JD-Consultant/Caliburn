/**
 * JD pane. While a Turn is active or paused the JD is read-only and its candidate is offered as a
 * separate "AI layer" view; the formal draft (what PDF exports) stays one click away.
 */
import { useCallback, useMemo, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Alert, IconButton, ToggleButton, ToggleButtonGroup } from '@mui/material';
import type { Target } from '../shared/api/generated/jd-sources-view';
import { DownloadIcon } from '../shared/ui/icons';
import type { ConsultantTurn } from '../shared/api/generated/consultant-turn';
import { isJdReadOnlyDuring } from '../features/interview/turn-summary';
import { JdCandidatePreview } from '../features/jd-editor/JdCandidatePreview';
import { JdProfileEditor } from '../features/jd-editor/JdProfileEditor';
import { JdWorkEditor } from '../features/jd-editor/JdWorkEditor';
import { SourceBadgeContext } from '../features/jd-editor/source-badge-context';
import { SourceBadge } from '../features/source-viewer/SourceBadge';
import { jdSourcesQuery } from '../features/source-viewer/source-api';
import { buildSourceIndex, targetKey } from '../features/source-viewer/source-index';
import { SourceViewer } from '../features/source-viewer/SourceViewer';

type JdView = 'candidate' | 'formal';

export function JdPane({ jobFileId, turn }: { jobFileId: string; turn: ConsultantTurn | null }) {
  const readOnly = isJdReadOnlyDuring(turn);
  const candidate = readOnly ? (turn?.candidate ?? null) : null;
  const [view, setView] = useState<JdView>('candidate');
  const [sourcesOpen, setSourcesOpen] = useState(false);
  const [sourceFilter, setSourceFilter] = useState<readonly string[] | null>(null);
  const sources = useQuery(jdSourcesQuery(jobFileId));
  const sourceIndex = useMemo(() => buildSourceIndex(sources.data?.references), [sources.data]);
  const renderBadge = useCallback(
    (target: Target) => {
      const summary = sourceIndex.get(targetKey(target));
      return summary ? (
        <SourceBadge
          summary={summary}
          onOpen={(citationIds) => {
            setSourceFilter(citationIds);
            setSourcesOpen(true);
          }}
        />
      ) : null;
    },
    [sourceIndex],
  );
  return (
    <>
      <div className="pane-header">
        <h2 className="pane-title">職務說明書（JD）</h2>
        <div className="pane-actions">
          <SourceViewer
            jobFileId={jobFileId}
            open={sourcesOpen}
            onOpenChange={(next) => {
              setSourcesOpen(next);
              if (!next) setSourceFilter(null);
            }}
            onlyCitationIds={sourceFilter}
            onClearFilter={() => setSourceFilter(null)}
          />
          <IconButton
            component="a"
            href={`/api/job-files/${encodeURIComponent(jobFileId)}/jd/export.pdf`}
            download
            aria-label="匯出目前 JD（PDF）"
            title="匯出目前 JD（PDF）"
            aria-describedby="jd-pdf-export-note"
          >
            <DownloadIcon />
          </IconButton>
        </div>
      </div>
      <div className="pane-scroll jd-scroll">
        <div className="jd-doc">
          <p id="jd-pdf-export-note" className="jd-note">
            匯出目前已正式保存的版本，不包含本輪候選預覽。
          </p>
          {readOnly && (
            <Alert
              severity="info"
              action={
                candidate && (
                  <ToggleButtonGroup
                    exclusive
                    size="small"
                    value={view}
                    aria-label="JD 檢視"
                    onChange={(_event, next: JdView | null) => {
                      if (next) setView(next);
                    }}
                  >
                    <ToggleButton value="candidate">候選預覽</ToggleButton>
                    <ToggleButton value="formal">正式稿</ToggleButton>
                  </ToggleButtonGroup>
                )
              }
            >
              {turn?.status === 'paused'
                ? '這輪處理已暫停，JD 仍為唯讀；繼續完成或取消後才能人工修改。'
                : '顧問處理中，JD 暫時唯讀；完成或取消後才能人工修改。'}
            </Alert>
          )}
          {candidate && view === 'candidate' ? (
            <JdCandidatePreview candidate={candidate} />
          ) : (
            <SourceBadgeContext.Provider value={renderBadge}>
              <JdProfileEditor jobFileId={jobFileId} readOnly={readOnly} />
              <JdWorkEditor jobFileId={jobFileId} readOnly={readOnly} />
            </SourceBadgeContext.Provider>
          )}
        </div>
      </div>
    </>
  );
}
