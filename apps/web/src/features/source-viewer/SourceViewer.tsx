/** Read-only sources of the formal JD, loaded only on disclosure. */
import { useId, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Alert, Box, Button, Chip, Stack, Typography } from '@mui/material';
import type { JdSourcesView, Reference } from '../../shared/api/generated/jd-sources-view';
import { describeSourceError, jdSourcesQuery } from './source-api';
import { SourceDetails } from './SourceDetails';

export function SourceViewer({ jobFileId }: { jobFileId: string }) {
  return <SourceDisclosure key={jobFileId} jobFileId={jobFileId} />;
}

function SourceDisclosure({ jobFileId }: { jobFileId: string }) {
  const [open, setOpen] = useState(false);
  const contentId = useId();
  return (
    <Box component="section" sx={{ minWidth: 0 }}>
      <Button aria-expanded={open} aria-controls={contentId} onClick={() => setOpen(!open)}>
        正式 JD 來源（唯讀）
      </Button>
      <Box id={contentId} hidden={!open}>
        {open && <SourceList jobFileId={jobFileId} />}
      </Box>
    </Box>
  );
}

function SourceList({ jobFileId }: { jobFileId: string }) {
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
          />
        )
      )}
    </Stack>
  );
}

function SourceReferences({ jobFileId, view }: { jobFileId: string; view: JdSourcesView }) {
  // Remounting after every list read drops the entire old navigation/diff state.
  const [selected, setSelected] = useState<Reference | null>(null);
  return (
    <Stack spacing={2}>
      {view.references.length === 0 && (
        <Typography>目前正式 JD 沒有附帶引用；這不代表內容錯誤或已完成核對。</Typography>
      )}
      {view.references.map((reference) => (
        <Box key={reference.citation_id}>
          <Typography component="h3" variant="subtitle1">
            {reference.target_label}
          </Typography>
          <Button
            aria-pressed={selected?.citation_id === reference.citation_id}
            onClick={() => setSelected(reference)}
          >
            {reference.source_label}
          </Button>
          {reference.needs_recheck && <Chip label="待核對" size="small" color="warning" />}
        </Box>
      ))}
      {selected && (
        <SourceDetails
          key={selected.citation_id}
          scope={{ jobFileId, revisionId: view.revision_id, citationId: selected.citation_id }}
          reference={selected}
        />
      )}
    </Stack>
  );
}
