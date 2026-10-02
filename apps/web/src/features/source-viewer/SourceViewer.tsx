/** Read-only sources of the formal JD, loaded only on disclosure. */
import { useId, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Alert, Box, Button, Stack, Typography } from '@mui/material';
import type { JdSourcesView } from '../../shared/api/generated/jd-sources-view';
import { describeSourceError, jdSourcesQuery } from './source-api';
import { SourceDetails } from './SourceDetails';
import { SourceChanges } from './SourceChanges';
import { SourceReferenceList } from './SourceReferenceList';
import type { SourceSelection } from './SourceReferenceList';

interface ViewerProps {
  jobFileId: string;
  /** Optional control from the page, e.g. a badge on a JD item opens the sheet for that item. */
  open?: boolean;
  onOpenChange?: (open: boolean) => void;
  onlyCitationIds?: readonly string[] | null;
  onClearFilter?: () => void;
}

export function SourceViewer(props: ViewerProps) {
  return <SourceDisclosure key={props.jobFileId} {...props} />;
}

function SourceDisclosure({
  jobFileId,
  open: controlledOpen,
  onOpenChange,
  onlyCitationIds = null,
  onClearFilter,
}: ViewerProps) {
  const [innerOpen, setInnerOpen] = useState(false);
  const open = controlledOpen ?? innerOpen;
  const setOpen = (next: boolean) => {
    if (onOpenChange) onOpenChange(next);
    else setInnerOpen(next);
  };
  const contentId = useId();
  return (
    <Box component="section" sx={{ minWidth: 0 }}>
      <Button
        size="small"
        variant="outlined"
        aria-expanded={open}
        aria-controls={contentId}
        onClick={() => setOpen(!open)}
      >
        正式 JD 來源（唯讀）
      </Button>
      {/* A side sheet over the JD pane keeps the document in view (Airtable/Attio side panel). */}
      <Box id={contentId} hidden={!open} className="source-sheet">
        {open && (
          <>
            <div className="source-sheet-header">
              <h3 className="pane-title">JD 來源回查</h3>
              <Button size="small" onClick={() => setOpen(false)}>
                關閉來源面板
              </Button>
            </div>
            <div className="source-sheet-body">
              <SourceList
                jobFileId={jobFileId}
                onlyCitationIds={onlyCitationIds}
                onClearFilter={onClearFilter}
              />
            </div>
          </>
        )}
      </Box>
    </Box>
  );
}

function SourceList({
  jobFileId,
  onlyCitationIds,
  onClearFilter,
}: {
  jobFileId: string;
  onlyCitationIds: readonly string[] | null;
  onClearFilter: (() => void) | undefined;
}) {
  const sources = useQuery(jdSourcesQuery(jobFileId));
  return (
    <Stack spacing={2}>
      <Typography variant="body2" color="text.secondary">
        此區只回查正式 JD 的來源。待核對不代表確定錯誤；閱讀來源或差異不會解除待核對。
      </Typography>
      <Button
        size="small"
        variant="outlined"
        disabled={sources.isFetching}
        onClick={() => {
          void sources.refetch();
        }}
        sx={{ alignSelf: 'flex-start' }}
      >
        重新讀取來源列表
      </Button>
      {sources.isFetching ? (
        <p role="status">正在讀取正式來源…</p>
      ) : sources.isError ? (
        <Alert severity="error">{describeSourceError(sources.error)}</Alert>
      ) : (
        sources.data && (
          <SourceReferences
            key={`${sources.data.revision_id}:${sources.dataUpdatedAt}`}
            jobFileId={jobFileId}
            view={sources.data}
            onlyCitationIds={onlyCitationIds}
            onClearFilter={onClearFilter}
          />
        )
      )}
    </Stack>
  );
}

function SourceReferences({
  jobFileId,
  view,
  onlyCitationIds,
  onClearFilter,
}: {
  jobFileId: string;
  view: JdSourcesView;
  onlyCitationIds: readonly string[] | null;
  onClearFilter: (() => void) | undefined;
}) {
  const shown = onlyCitationIds
    ? view.references.filter((reference) => onlyCitationIds.includes(reference.citation_id))
    : view.references;
  // Remounting after every list read drops the entire old navigation/diff state.
  const [selected, setSelected] = useState<SourceSelection | null>(() =>
    onlyCitationIds && shown.length === 1 && shown[0]
      ? { citationId: shown[0].citation_id, view: 'content' }
      : null,
  );
  const reference = shown.find((item) => item.citation_id === selected?.citationId);
  return (
    <Stack spacing={2}>
      {view.references.length === 0 && (
        <Typography>目前正式 JD 沒有附帶引用；這不代表內容錯誤或已完成核對。</Typography>
      )}
      {reference &&
        (selected?.view === 'changes' ? (
          <SourceChanges
            key={reference.citation_id}
            scope={{ jobFileId, revisionId: view.revision_id, citationId: reference.citation_id }}
            sourceLabel={reference.source_label}
          />
        ) : (
          <SourceDetails
            key={reference.citation_id}
            scope={{ jobFileId, revisionId: view.revision_id, citationId: reference.citation_id }}
            reference={reference}
          />
        ))}
      {onlyCitationIds && (
        <Typography variant="body2" color="text.secondary">
          只顯示所選 JD 項目的來源。{' '}
          {onClearFilter && (
            <Button size="small" onClick={onClearFilter}>
              顯示全部來源
            </Button>
          )}
        </Typography>
      )}
      <SourceReferenceList references={shown} selected={selected} onSelect={setSelected} />
    </Stack>
  );
}
