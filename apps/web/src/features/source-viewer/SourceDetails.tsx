/** Navigate only links supplied by the selected formal citation's fixed chain. */
import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Alert, Box, Button, Divider, Stack, Typography } from '@mui/material';
import type { Reference } from '../../shared/api/generated/jd-sources-view';
import type { InterviewContent } from '../../shared/api/generated/jd-source-content-view';
import { describeSourceError, jdSourceContentQuery, jdSourceChangesQuery } from './source-api';
import type { SourceScope } from './source-api';
import { SafeSourceMarkdown } from './SafeSourceMarkdown';

const speakerLabels: Record<InterviewContent['speaker'], string> = {
  app: '系統',
  employee: '員工',
  consultant: '顧問',
};

export function SourceDetails({ scope, reference }: { scope: SourceScope; reference: Reference }) {
  const [sourceRef, setSourceRef] = useState<string | null>(null);
  const [showChanges, setShowChanges] = useState(false);
  const source = useQuery(jdSourceContentQuery(scope, sourceRef));
  const content = source.data?.content;
  return (
    <Stack
      spacing={2}
      sx={{ border: 1, borderColor: 'divider', borderRadius: 1, p: 2, minWidth: 0 }}
    >
      <Typography variant="h6" component="h3">
        來源回查：{reference.source_label}
      </Typography>
      <Typography variant="body2" color="text.secondary">
        以下正文為原引用當時的固定版本。
      </Typography>
      {sourceRef !== null && <Button onClick={() => setSourceRef(null)}>回到直接來源</Button>}
      {source.isFetching ? (
        <p role="status">正在讀取來源正文…</p>
      ) : source.isError ? (
        <Alert severity="error">{describeSourceError(source.error)}</Alert>
      ) : (
        content &&
        (content.kind === 'interview' ? (
          <Box>
            <Typography component="h4" variant="subtitle1">
              訪談 #{content.interview_sequence} · {speakerLabels[content.speaker]}
            </Typography>
            <Typography sx={{ whiteSpace: 'pre-wrap', overflowWrap: 'anywhere' }}>
              {content.interview_text}
            </Typography>
          </Box>
        ) : (
          <Stack spacing={1}>
            <Typography component="h4" variant="subtitle1">
              {content.title}
            </Typography>
            <Typography sx={{ whiteSpace: 'pre-wrap', overflowWrap: 'anywhere' }}>
              {content.description}
            </Typography>
            <SafeSourceMarkdown markdown={content.body} />
            {content.references.map((link) => (
              <Box key={link.source_ref}>
                <Button onClick={() => setSourceRef(link.source_ref)}>{link.label}</Button>
              </Box>
            ))}
          </Stack>
        ))
      )}
      {reference.source_kind !== 'interview' && (
        <>
          <Divider />
          <Button aria-expanded={showChanges} onClick={() => setShowChanges(!showChanges)}>
            查看此引用鏈差異
          </Button>
          {showChanges && <SourceChanges scope={scope} />}
        </>
      )}
    </Stack>
  );
}

function SourceChanges({ scope }: { scope: SourceScope }) {
  const changes = useQuery(jdSourceChangesQuery(scope));
  return (
    <Stack spacing={1}>
      <Typography variant="body2" color="text.secondary">
        比較原引用固定版本與讀取當時最新已發布的 Memory 版本；不是本輪候選。只供閱讀，不會完成核對。
      </Typography>
      {changes.isFetching ? (
        <p role="status">正在讀取來源差異…</p>
      ) : changes.isError ? (
        <Alert severity="error">{describeSourceError(changes.error)}</Alert>
      ) : (
        changes.data && <SafeSourceMarkdown markdown={changes.data.markdown} />
      )}
    </Stack>
  );
}
