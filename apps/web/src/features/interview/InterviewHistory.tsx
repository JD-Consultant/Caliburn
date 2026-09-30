/** Formal transcript with a separate, non-source disclosure of saved public commentary. */
import { useQuery } from '@tanstack/react-query';
import type { ReactNode } from 'react';
import { Alert, Button } from '@mui/material';
import type { InterviewMessage } from '../../shared/api/generated/interview-history';
import { describeReadError } from '../../shared/api/http';
import { interviewHistoryQuery } from './interview-api';
import { HistoricalTurnMessages } from './HistoricalTurnMessages';

const speakerLabels: Record<InterviewMessage['speaker'], string> = {
  app: 'App 開場引導',
  employee: '受訪員工',
  consultant: '職務顧問',
};

const speakerAvatars: Record<InterviewMessage['speaker'], string> = {
  app: '系',
  employee: '員',
  consultant: '顧',
};

export function InterviewHistory({
  jobFileId,
  renderTurnActions,
}: {
  jobFileId: string;
  renderTurnActions?: (executionId: string) => ReactNode;
}) {
  const history = useQuery(interviewHistoryQuery(jobFileId));
  return (
    <section aria-labelledby="interview-heading">
      <p id="interview-heading" className="interview-heading">
        歷史訪談
      </p>
      {history.isPending && (
        <p role="status" className="interview-heading">
          正在讀取這份檔案的訪談…
        </p>
      )}
      {history.isError && (
        <Alert
          severity="error"
          sx={{ mx: 2, mt: 1 }}
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
        <ol className="interview-history">
          {history.data.messages.map((message) => (
            <li key={message.source_id} className={`msg msg--${message.speaker}`}>
              <h3 className="msg-meta">
                <span className="msg-avatar" aria-hidden="true">
                  {speakerAvatars[message.speaker]}
                </span>
                {speakerLabels[message.speaker]} · 訪談序號 {message.interview_sequence}
              </h3>
              <p className="interview-text">{message.interview_text}</p>
              {message.speaker === 'consultant' && message.execution_id !== null && (
                <HistoricalTurnMessages
                  jobFileId={jobFileId}
                  executionId={message.execution_id}
                  renderTurnActions={renderTurnActions}
                />
              )}
            </li>
          ))}
        </ol>
      )}
    </section>
  );
}
