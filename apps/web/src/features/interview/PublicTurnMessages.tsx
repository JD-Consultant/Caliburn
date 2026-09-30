/** Public commentary stays nonformal; only the active Turn may add transient display. */
import { Alert, Box, Typography } from '@mui/material';
import type { PublicCommentary } from '../../shared/api/generated/consultant-turn';
import { useConsultantCommentaryStream } from './use-consultant-commentary-stream';

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
  const live = useConsultantCommentaryStream(jobFileId, executionId);
  const pending = live.messages.filter(
    (item) =>
      !messages?.some(
        (saved) => saved.response_id === item.response_id && saved.message_id === item.message_id,
      ),
  );
  return (
    <>
      <PublicTurnMessages messages={messages} terminal={false} />
      {live.disconnected && (
        <Typography variant="body2" color="text.secondary">
          即時顯示中斷；不代表處理已停止，仍以伺服器狀態為準。
        </Typography>
      )}
      {pending.length > 0 && (
        <Box>
          <Typography variant="body2" color="text.secondary">
            即時公開訊息（尚未保存、非正式訪談、不可引用）
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
      <summary>{terminal ? '回看本次公開處理訊息' : '本次公開處理訊息'}</summary>
      <PublicCommentaryContent messages={messages} />
    </Box>
  );
}

export function PublicCommentaryContent({ messages }: { messages: PublicCommentary[] | null }) {
  if (messages === null)
    return <Alert severity="info">公開處理訊息目前無法讀取；不影響正式訪談記錄。</Alert>;
  if (messages.length === 0)
    return <Typography variant="body2">這次處理沒有已保存的公開中間訊息。</Typography>;
  return (
    <>
      <Typography variant="body2" color="text.secondary">
        公開處理訊息（非正式訪談、不可引用）
      </Typography>
      <Box component="ol" sx={{ pl: 3 }}>
        {messages.map((message) => (
          <li key={`${message.response_id}:${message.message_id}`}>
            <Typography sx={{ whiteSpace: 'pre-wrap', overflowWrap: 'anywhere' }}>
              {message.text}
            </Typography>
          </li>
        ))}
      </Box>
    </>
  );
}
