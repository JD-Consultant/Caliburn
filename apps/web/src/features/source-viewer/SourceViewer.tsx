/** Read-only sources of the formal JD, loaded only on disclosure. */
import { useId, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Alert, Box, Button, Chip, Stack, Typography } from '@mui/material';
import type { JdSourcesView, Reference } from '../../shared/api/generated/jd-sources-view';
import { describeSourceError, jdSourcesQuery } from './source-api';
import { SourceDetails } from './SourceDetails';

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
        disabled={sources.isFetching}
        onClick={() => {
          void sources.refetch();
        }}
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
  const [selected, setSelected] = useState<Reference | null>(() =>
    onlyCitationIds && shown.length === 1 ? (shown[0] ?? null) : null,
  );
  return (
    <Stack spacing={2}>
      {view.references.length === 0 && (
        <Typography>目前正式 JD 沒有附帶引用；這不代表內容錯誤或已完成核對。</Typography>
      )}
      {selected && (
        <SourceDetails
          key={selected.citation_id}
          scope={{ jobFileId, revisionId: view.revision_id, citationId: selected.citation_id }}
          reference={selected}
        />
      )}
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
      {shown.map((reference) => (
        <Box key={reference.citation_id} sx={{ pb: 1.5, borderBottom: 1, borderColor: 'divider' }}>
          <Typography
            component="h3"
            variant="subtitle2"
            sx={{
              display: '-webkit-box',
              WebkitLineClamp: 2,
              WebkitBoxOrient: 'vertical',
              overflow: 'hidden',
              overflowWrap: 'anywhere',
            }}
          >
            {reference.target_label}
          </Typography>
          <Stack direction="row" spacing={1} sx={{ alignItems: 'center', flexWrap: 'wrap' }}>
            <Button
              size="small"
              aria-pressed={selected?.citation_id === reference.citation_id}
              onClick={() => setSelected(reference)}
            >
              {reference.source_label}
            </Button>
            {reference.needs_recheck && <Chip label="待核對" size="small" color="warning" />}
          </Stack>
        </Box>
      ))}
    </Stack>
  );
}
