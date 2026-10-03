/** Public commentary stays nonformal; only the active Turn may add transient display. */
import { Alert, Box, Typography } from '@mui/material';
import type { PublicCommentary } from '../../shared/api/generated/consultant-turn';
import { useConsultantActivityStream } from './use-consultant-activity-stream';
import { ReasoningSummaries } from './ReasoningSummaries';

/** Mount only for a server-verified active Turn, keyed by its file/execution identity. */
export function StreamingPublicTurnMessages({
  jobFileId,
  executionId,
  messages,
}: {
  jobFileId: string;
  executionId: string;
  messages: PublicCommentary[] | null;
}) {
  const live = useConsultantActivityStream(jobFileId, executionId);
  const pending = live.messages.filter(
    (item) =>
      !messages?.some(
        (saved) => saved.response_id === item.response_id && saved.message_id === item.message_id,
      ),
  );
  return (
    <>
      <ReasoningSummaries
        jobFileId={jobFileId}
        executionId={executionId}
        terminal={false}
        live={live.summaries}
      />
      <PublicTurnMessages messages={messages} terminal={false} />
      {live.disconnected && (
        <Typography variant="body2" color="text.secondary">
          即時顯示中斷；不代表處理已停止，仍以伺服器狀態為準。
        </Typography>
      )}
      <div className="typing" aria-hidden="true">
        <span />
        <span />
        <span />
      </div>
      {pending.length > 0 && (
        <Box className="live-messages">
          <Typography variant="body2" color="text.secondary">
            即時訊息（尚未保存）
          </Typography>
          {pending.map((item) => (
            <Typography
              key={JSON.stringify([item.response_id, item.message_id])}
              sx={{ whiteSpace: 'pre-wrap', overflowWrap: 'anywhere' }}
            >
              {item.text}
            </Typography>
          ))}
        </Box>
      )}
    </>
  );
}

export function PublicTurnMessages({
  messages,
  terminal,
}: {
  messages: PublicCommentary[] | null;
  terminal: boolean;
}) {
  if (messages === null) return <PublicCommentaryContent messages={messages} />;
  if (messages.length === 0) return null;
  return (
    <Box component="details" open={!terminal}>
      <summary>{terminal ? '回看本次處理過程' : '本次處理過程'}</summary>
      <PublicCommentaryContent messages={messages} />
    </Box>
  );
}

export function PublicCommentaryContent({ messages }: { messages: PublicCommentary[] | null }) {
  if (messages === null) return <Alert severity="info">目前無法讀取處理過程。</Alert>;
  if (messages.length === 0)
    return <Typography variant="body2">這次處理沒有已保存的中間訊息。</Typography>;
  return (
    <div className="process-log">
      <ol>
        {messages.map((message) => (
          <li key={`${message.response_id}:${message.message_id}`}>
            <Typography sx={{ whiteSpace: 'pre-wrap', overflowWrap: 'anywhere' }}>
              {message.text}
            </Typography>
          </li>
        ))}
      </ol>
    </div>
  );
}
