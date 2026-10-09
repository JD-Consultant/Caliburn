/** Read-only sources of the formal JD, loaded only on disclosure. */
import { useEffect, useId, useLayoutEffect, useRef, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Alert, Box, Button, Chip, Tab, Tabs, Typography } from '@mui/material';
import type { Reference } from '../../shared/api/generated/jd-sources-view';
import { IconAction } from '../../shared/ui/IconAction';
import { ArrowBackIcon, CloseIcon, RefreshIcon } from '../../shared/ui/icons';
import { describeSourceError, jdSourcesQuery } from './source-api';
import type { SourceScope } from './source-api';
import { SourceDetails } from './SourceDetails';
import { SourceChanges } from './SourceChanges';
import { SourceReferenceList } from './SourceReferenceList';
import { changeLabel } from './source-labels';
import { useSourceSelection } from './source-selection';
import type { SourceSelection } from './source-selection';

interface ViewerProps {
  jobFileId: string;
  /** Optional control from the page, e.g. a badge on a JD item opens the sheet for that item. */
  open?: boolean;
  onOpenChange?: (open: boolean) => void;
  returnFocusTo?: HTMLButtonElement | null;
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
  returnFocusTo,
  onlyCitationIds = null,
  onClearFilter,
}: ViewerProps) {
  const [innerOpen, setInnerOpen] = useState(false);
  const open = controlledOpen ?? innerOpen;
  const disclosure = useRef<HTMLButtonElement>(null);
  const opener = useRef<HTMLButtonElement | null>(null);
  const wasOpen = useRef(false);
  useLayoutEffect(() => {
    if (open) opener.current = returnFocusTo ?? disclosure.current;
    else if (wasOpen.current) {
      const trigger = opener.current;
      if (trigger && canReturnFocus(trigger)) trigger.focus();
      else disclosure.current?.focus();
      opener.current = null;
    }
    wasOpen.current = open;
  }, [open, returnFocusTo]);
  const setOpen = (next: boolean) => {
    if (onOpenChange) onOpenChange(next);
    else setInnerOpen(next);
  };
  const contentId = useId();
  return (
    <Box component="section" sx={{ minWidth: 0 }}>
      <Button
        ref={disclosure}
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
          <SourceSheet
            jobFileId={jobFileId}
            onClose={() => setOpen(false)}
            onlyCitationIds={onlyCitationIds}
            onClearFilter={onClearFilter}
          />
        )}
      </Box>
    </Box>
  );
}

function canReturnFocus(trigger: HTMLButtonElement): boolean {
  if (!trigger.isConnected || trigger.disabled) return false;
  for (let element: HTMLElement | null = trigger; element; element = element.parentElement) {
    if (element.hidden || element.inert || element.getAttribute('aria-disabled') === 'true')
      return false;
    const style = element.ownerDocument.defaultView?.getComputedStyle(element);
    if (
      style?.display === 'none' ||
      style?.visibility === 'hidden' ||
      style?.visibility === 'collapse'
    )
      return false;
  }
  return true;
}

/**
 * A drawer with one level of drill-in: the list of sources, or one source with Back (Fluent's drawer
 * header holds the title, quick actions such as back and refresh, and the close button).
 */
function SourceSheet({
  jobFileId,
  onClose,
  onlyCitationIds,
  onClearFilter,
}: {
  jobFileId: string;
  onClose: () => void;
  onlyCitationIds: readonly string[] | null;
  onClearFilter: (() => void) | undefined;
}) {
  const sources = useQuery(jdSourcesQuery(jobFileId));
  const view = sources.data;
  const shown = view
    ? onlyCitationIds
      ? view.references.filter((reference) => onlyCitationIds.includes(reference.citation_id))
      : view.references
    : [];
  const [only] = shown;
  // A new read of the list starts the sheet over; a filter that leaves one source opens it at once.
  const { selected, returnTo, open, back } = useSourceSelection(
    view ? `${view.revision_id}:${String(sources.dataUpdatedAt)}` : '',
    onlyCitationIds && shown.length === 1 && only
      ? { citationId: only.citation_id, view: 'content' }
      : null,
  );
  const reference = shown.find((item) => item.citation_id === selected?.citationId);
  return (
    <>
      <div className="source-sheet-header">
        {reference && (
          <IconAction label="返回來源列表" onClick={back}>
            <ArrowBackIcon />
          </IconAction>
        )}
        <h3 className="pane-title source-sheet-title">JD 來源回查</h3>
        <IconAction
          label="重新讀取來源列表"
          disabled={sources.isFetching}
          onClick={() => {
            void sources.refetch();
          }}
        >
          <RefreshIcon />
        </IconAction>
        <IconAction label="關閉來源面板" onClick={onClose}>
          <CloseIcon />
        </IconAction>
      </div>
      <div className="source-sheet-body">
        {sources.isFetching ? (
          <p role="status">正在讀取正式來源…</p>
        ) : sources.isError ? (
          <Alert severity="error">{describeSourceError(sources.error)}</Alert>
        ) : (
          view &&
          (reference && selected ? (
            <SourceDetailView
              key={reference.citation_id}
              scope={{ jobFileId, revisionId: view.revision_id, citationId: reference.citation_id }}
              reference={reference}
              view={selected.view}
              onViewChange={(next) => open({ citationId: reference.citation_id, view: next })}
            />
          ) : (
            <div className="source-body">
              <p className="source-note">
                此區只回查正式 JD 的來源。待核對不代表確定錯誤；閱讀來源或差異不會解除待核對。
              </p>
              {onlyCitationIds && (
                <p className="source-note">
                  只顯示所選 JD 項目的來源。{' '}
                  {onClearFilter && (
                    <Button size="small" onClick={onClearFilter}>
                      顯示全部來源
                    </Button>
                  )}
                </p>
              )}
              {view.references.length === 0 && (
                <Typography>目前正式 JD 沒有附帶引用；這不代表內容錯誤或已完成核對。</Typography>
              )}
              <SourceReferenceList references={shown} focusCitationId={returnTo} onOpen={open} />
            </div>
          ))
        )}
      </div>
    </>
  );
}

/** One source: which JD item it supports, its title, and — when it needs recheck — its text or its changes. */
function SourceDetailView({
  scope,
  reference,
  view,
  onViewChange,
}: {
  scope: SourceScope;
  reference: Reference;
  view: SourceSelection['view'];
  onViewChange: (view: SourceSelection['view']) => void;
}) {
  const id = useId();
  const title = useRef<HTMLHeadingElement>(null);
  // Arriving from the list, the reader lands on the title: a screen reader announces where it is.
  useEffect(() => title.current?.focus(), []);
  return (
    <section aria-labelledby={`${id}-title`} className="source-detail">
      <p className="source-detail__context">
        <span>引用於</span> {reference.target_label}
      </p>
      <h4 id={`${id}-title`} ref={title} tabIndex={-1} className="source-detail__title">
        {reference.source_label}
      </h4>
      {reference.needs_recheck && (
        <Chip
          label={changeLabel(reference)}
          size="small"
          color="warning"
          sx={{ alignSelf: 'flex-start' }}
        />
      )}
      {reference.needs_recheck && (
        <Tabs
          value={view}
          onChange={(_event, next: SourceSelection['view']) => onViewChange(next)}
          aria-label="來源檢視"
          className="source-tabs"
        >
          <Tab
            value="content"
            label="來源正文"
            id={`${id}-tab-content`}
            aria-controls={`${id}-panel`}
          />
          <Tab
            value="changes"
            label="差異"
            id={`${id}-tab-changes`}
            aria-controls={`${id}-panel`}
          />
        </Tabs>
      )}
      <div
        id={`${id}-panel`}
        role={reference.needs_recheck ? 'tabpanel' : undefined}
        aria-labelledby={reference.needs_recheck ? `${id}-tab-${view}` : undefined}
      >
        {view === 'changes' ? <SourceChanges scope={scope} /> : <SourceDetails scope={scope} />}
      </div>
    </section>
  );
}
