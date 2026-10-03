/** Readable summaries stay separate from commentary, formal answers and opaque reasoning. */
import { useQuery } from '@tanstack/react-query';
import { Alert, Box, Button, Typography } from '@mui/material';
import type { ReasoningSummary } from '../../shared/api/generated/reasoning-summary';
import { describeReadError } from '../../shared/api/http';
import { ChatMarkdown } from '../../shared/ui/ChatMarkdown';
import { reasoningSummariesQuery, summaryKey } from './reasoning-summary-api';

export function ReasoningSummaries({
  jobFileId,
  executionId,
  terminal,
  live = [],
}: {
  jobFileId: string;
  executionId: string;
  terminal: boolean;
  live?: ReasoningSummary[];
}) {
  const saved = useQuery(reasoningSummariesQuery(jobFileId, executionId));
  const summaries = saved.data ?? [];
  const savedKeys = new Set(summaries.map(summaryKey));
  const pending = live.filter((item) => !savedKeys.has(summaryKey(item)));
  return (
    <Box component="details" open={!terminal}>
      <summary>推理摘要</summary>
      <div className="process-log">
        {saved.isPending && <p role="status">正在讀取已保存的推理摘要…</p>}
        {saved.isError && (
          <Alert
            severity="warning"
            action={
              <Button
                color="inherit"
                onClick={() => {
                  void saved.refetch();
                }}
              >
                重新讀取推理摘要
              </Button>
            }
          >
            {describeReadError(saved.error)}
          </Alert>
        )}
        {saved.isSuccess && summaries.length === 0 && pending.length === 0 && (
          <Typography variant="body2">這次處理沒有已保存的推理摘要。</Typography>
        )}
        {summaries.map((item) => (
          <ChatMarkdown key={summaryKey(item)} className="md" markdown={item.text} />
        ))}
        {pending.length > 0 && (
          <div className="live-messages">
            <Typography variant="body2" color="text.secondary">
              即時摘要（尚未保存）
            </Typography>
            {pending.map((item) => (
              <ChatMarkdown key={summaryKey(item)} className="md" markdown={item.text} />
            ))}
          </div>
        )}
      </div>
    </Box>
  );
}
