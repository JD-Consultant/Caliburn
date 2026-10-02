/** Navigate only links supplied by the selected formal citation's fixed chain. */
import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Alert, Box, Button, Stack, Typography } from '@mui/material';
import type { Reference } from '../../shared/api/generated/jd-sources-view';
import type { InterviewContent } from '../../shared/api/generated/jd-source-content-view';
import { describeSourceError, jdSourceContentQuery } from './source-api';
import type { SourceScope } from './source-api';
import { SafeMarkdown } from '../../shared/ui/SafeMarkdown';

const speakerLabels: Record<InterviewContent['speaker'], string> = {
  app: '系統',
  employee: '員工',
  consultant: '顧問',
};

export function SourceDetails({ scope, reference }: { scope: SourceScope; reference: Reference }) {
  const [sourceRef, setSourceRef] = useState<string | null>(null);
  const source = useQuery(jdSourceContentQuery(scope, sourceRef));
  const content = source.data?.content;
  return (
    <Stack spacing={2} className="source-details" sx={{ minWidth: 0 }}>
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
            <SafeMarkdown markdown={content.body} />
            {content.references.map((link) => (
              <Box key={link.source_ref}>
                <Button onClick={() => setSourceRef(link.source_ref)}>{link.label}</Button>
              </Box>
            ))}
          </Stack>
        ))
      )}
    </Stack>
  );
}
