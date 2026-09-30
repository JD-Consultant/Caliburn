/** A historical reply opens only its server-provided original Turn's public messages. */
import { useId, useState } from 'react';
import type { ReactNode } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Alert, Box, Button } from '@mui/material';
import { describeReadError } from '../../shared/api/http';
import { consultantTurnQuery } from './interview-turn-api';
import { PublicCommentaryContent } from './PublicTurnMessages';

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
        aria-expanded={open}
        aria-controls={contentId}
        onClick={() => setOpen(!open)}
      >
        {props.renderTurnActions ? '回看本次公開處理訊息／JD 操作' : '回看本次公開處理訊息'}
      </Button>
      <Box id={contentId} hidden={!open}>
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
  if (turn.isPending) return <p role="status">正在讀取這次回答的公開處理訊息…</p>;
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
            重新讀取公開訊息
          </Button>
        }
      >
        {describeReadError(turn.error)}
      </Alert>
    );
  if (turn.data.status !== 'completed')
    return <Alert severity="warning">這筆歷史回答的處理狀態尚無法核對；未採用其公開訊息。</Alert>;
  return (
    <>
      <PublicCommentaryContent messages={turn.data.commentary} />
      {renderTurnActions?.(executionId)}
    </>
  );
}
