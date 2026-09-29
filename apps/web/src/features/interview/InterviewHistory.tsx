/** Only formal source history; private reasoning and execution progress do not enter here. */
import { useQuery } from '@tanstack/react-query';
import { Alert, Button, Paper, Stack, Typography } from '@mui/material';
import type { InterviewMessage } from '../../shared/api/generated/interview-history';
import { describeReadError } from '../../shared/api/http';
import { interviewHistoryQuery } from './interview-api';

const speakerLabels: Record<InterviewMessage['speaker'], string> = {
  app: 'App 開場引導',
  employee: '受訪員工',
  consultant: '職務顧問',
};

export function InterviewHistory({ jobFileId }: { jobFileId: string }) {
  const history = useQuery(interviewHistoryQuery(jobFileId));
  return (
    <section aria-labelledby="interview-heading">
      <Typography id="interview-heading" variant="h6" component="h2" sx={{ mb: 2 }}>
        歷史訪談
      </Typography>
      {history.isPending && <p role="status">正在讀取這份檔案的訪談…</p>}
      {history.isError && (
        <Alert
          severity="error"
          action={
            <Button
              color="inherit"
              onClick={() => {
                void history.refetch();
              }}
            >
              重新讀取
            </Button>
          }
        >
          {describeReadError(history.error)}
        </Alert>
      )}
      {history.data && !history.isError && (
        <Stack component="ol" spacing={2} className="interview-history">
          {history.data.messages.map((message) => (
            <Paper
              component="li"
              variant="outlined"
              key={message.source_id}
              className="interview-message"
            >
              <Typography component="h3" variant="subtitle2">
                {speakerLabels[message.speaker]} · 訪談序號 {message.interview_sequence}
              </Typography>
              <p className="interview-text">{message.interview_text}</p>
            </Paper>
          ))}
        </Stack>
      )}
    </section>
  );
}
