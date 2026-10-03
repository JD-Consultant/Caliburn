/** A historical reply opens only its server-provided original Turn's public messages. */
import { useId, useState } from 'react';
import type { ReactNode } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Alert, Box, Button } from '@mui/material';
import { describeReadError } from '../../shared/api/http';
import { consultantTurnQuery } from './interview-turn-api';
import { PublicCommentaryContent } from './PublicTurnMessages';
import { ReasoningSummaries } from './ReasoningSummaries';

interface HistoryTurnProps {
  jobFileId: string;
  executionId: string;
  renderTurnActions?: ((executionId: string) => ReactNode) | undefined;
}

export function HistoricalTurnMessages(props: HistoryTurnProps) {
  return <TurnDisclosure key={`${props.jobFileId}:${props.executionId}`} {...props} />;
}

function TurnDisclosure(props: HistoryTurnProps) {
  const [open, setOpen] = useState(false);
  const contentId = useId();
  return (
    <Box>
      <Button
        size="small"
        color="inherit"
        className="disclosure"
        aria-expanded={open}
        aria-controls={contentId}
        startIcon={<span className="disclosure-chevron" aria-hidden="true" />}
        onClick={() => setOpen(!open)}
      >
        處理紀錄
      </Button>
      <Box id={contentId} hidden={!open} sx={{ pl: 2 }}>
        {open && <HistoryTurnContent {...props} />}
      </Box>
    </Box>
  );
}

function HistoryTurnContent({ jobFileId, executionId, renderTurnActions }: HistoryTurnProps) {
  const turn = useQuery({
    ...consultantTurnQuery(jobFileId, executionId),
    refetchInterval: false,
    refetchOnWindowFocus: false,
  });
  if (turn.isPending) return <p role="status">正在讀取這次回答的處理過程…</p>;
  if (turn.isError)
    return (
      <Alert
        severity="error"
        action={
          <Button
            color="inherit"
            onClick={() => {
              void turn.refetch();
            }}
          >
            重新讀取處理過程
          </Button>
        }
      >
        {describeReadError(turn.error)}
      </Alert>
    );
  if (turn.data.status !== 'completed')
    return <Alert severity="warning">尚無法確認這筆歷史回答已完成，暫不顯示處理過程。</Alert>;
  return (
    <>
      <ReasoningSummaries jobFileId={jobFileId} executionId={executionId} terminal />
      <Box component="details">
        <summary>處理過程</summary>
        <PublicCommentaryContent messages={turn.data.commentary} />
      </Box>
      {renderTurnActions && (
        <Box component="section" aria-label="JD 操作" sx={{ mt: 1 }}>
          {renderTurnActions(executionId)}
        </Box>
      )}
    </>
  );
}
