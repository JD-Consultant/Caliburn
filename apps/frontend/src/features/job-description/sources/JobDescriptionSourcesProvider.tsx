import { Box, Button, Chip, Typography } from '@mui/material';
import { useEffect, useId, useRef, useState, type ReactNode } from 'react';
import type { JobDescriptionContentResponse } from '../../../shared/api/generated/types.gen';
import { CitationDetails } from './CitationDetails';
import { citationTargetLabel } from './source-labels';
import { SourcesContext, type SourceTarget } from './sources-context';
import './sources.css';

type Props = {
  jobDescription: JobDescriptionContentResponse & { version?: number };
  version?: number | undefined;
  comparisonPublishedVersion?: number | undefined;
  children: ReactNode;
};

export function JobDescriptionSourcesProvider(props: Props) {
  return (
    <SourcesDisclosure
      key={`${props.jobDescription.workspace_id}/${props.jobDescription.job_description_id}/${String(props.version ?? 'current')}`}
      {...props}
    />
  );
}

function SourcesDisclosure({
  jobDescription: jd,
  version,
  comparisonPublishedVersion,
  children,
}: Props) {
  const [open, setOpen] = useState(false);
  const [filter, setFilter] = useState<SourceTarget>();
  const [selection, setSelection] = useState<string>();
  const opener = useRef<HTMLButtonElement | null>(null);
  const heading = useRef<HTMLHeadingElement>(null);
  const id = useId();
  const citations = jd.citations ?? [];
  const shown = citations.filter(
    (citation) =>
      !filter ||
      (citation.target_kind === filter.kind && citation.target_id === filter.id),
  );
  const selected = shown.find((citation) => citation.id === selection);
  const close = () => {
    setOpen(false);
    if (opener.current?.isConnected && !opener.current.disabled) opener.current.focus();
  };
  useEffect(() => {
    if (open && !selected) heading.current?.focus();
  }, [open, selected]);
  return (
    <SourcesContext.Provider
      value={{
        jobDescription: jd,
        open,
        show: (trigger, target) => {
          opener.current = trigger;
          setFilter(target);
          setSelection(undefined);
          setOpen(true);
        },
      }}
    >
      {children}
      {open && (
        <Box
          component="aside"
          className="jd-source-sheet"
          aria-labelledby={id}
          onKeyDown={(event) => {
            if (event.key === 'Escape') {
              event.stopPropagation();
              close();
            }
          }}
        >
          <Box className="jd-source-sheet-header">
            {selected && (
              <Button size="small" onClick={() => setSelection(undefined)}>
                返回來源列表
              </Button>
            )}
            <Typography
              id={id}
              component="h3"
              variant="subtitle1"
              tabIndex={-1}
              ref={heading}
            >
              JD 來源回查{version === undefined ? '' : ` · 版本 ${String(version)}`}
            </Typography>
            <Button size="small" aria-label="關閉來源面板" onClick={close}>
              關閉
            </Button>
          </Box>
          <Box className="jd-source-sheet-body">
            {selected ? (
              <>
                <Typography variant="body2" color="text.secondary">
                  引用於 {citationTargetLabel(selected, jd)}
                </Typography>
                <CitationDetails
                  key={selected.id}
                  currentVersion={jd.version}
                  scope={{
                    workspaceId: jd.workspace_id,
                    jobDescriptionId: jd.job_description_id,
                    citation: selected,
                    version,
                    comparisonPublishedVersion,
                  }}
                />
              </>
            ) : (
              <>
                <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
                  來源僅供查讀。待核對不代表確定錯誤；查閱不會解除標記。
                </Typography>
                {filter && (
                  <Button size="small" onClick={() => setFilter(undefined)}>
                    顯示全部來源
                  </Button>
                )}
                {shown.length === 0 && (
                  <Typography>
                    目前沒有附帶引用；這不代表內容錯誤或已完成核對。
                  </Typography>
                )}
                <Box component="ul" className="jd-source-list">
                  {shown.map((citation) => (
                    <li key={citation.id}>
                      <Button
                        className="jd-source-list-button"
                        aria-label={`${citationTargetLabel(citation, jd)} ${citation.source.kind === 'interview' ? '訪談原文' : `Memory 發布版 ${String(citation.source.published_version)}`}`}
                        onClick={() => setSelection(citation.id)}
                      >
                        <span>{citationTargetLabel(citation, jd)}</span>
                        <span>
                          {citation.source.kind === 'interview'
                            ? '訪談原文'
                            : `Memory · 發布版 ${String(citation.source.published_version)}`}
                        </span>
                        <Chip
                          size="small"
                          component="span"
                          label={
                            citation.jd_changed
                              ? 'JD 已變更 · 待核對'
                              : '查閱來源及核對狀態'
                          }
                        />
                      </Button>
                    </li>
                  ))}
                </Box>
              </>
            )}
          </Box>
        </Box>
      )}
    </SourcesContext.Provider>
  );
}
