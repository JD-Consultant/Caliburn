/** Read-only saved planning notes; empty notes never claim interview completion. */
import { Alert, Box, Button, Typography } from '@mui/material';
import { describeReadError } from '../../shared/api/http';
import { SafeMarkdown } from '../../shared/ui/SafeMarkdown';
import { useInterviewPlan } from './use-interview-plan';

export function InterviewPlan({ jobFileId }: { jobFileId: string }) {
  const state = useInterviewPlan(jobFileId);
  return (
    <Box component="section" aria-label="工作計畫" sx={{ mb: 2 }}>
      <Box
        component="details"
        open
        sx={{ border: 1, borderColor: 'divider', borderRadius: 2, p: 2 }}
      >
        <Typography component="summary" variant="subtitle2" sx={{ cursor: 'pointer' }}>
          工作計畫
        </Typography>
        <Typography variant="caption" color="text.secondary">
          {state.source === 'candidate'
            ? '本輪候選'
            : state.source === 'previous'
              ? state.plan === undefined
                ? '採用版尚待確認'
                : '上一採用版，等待更新'
              : '已採用工作計畫'}
        </Typography>
        {state.plan === undefined ? (
          <Typography role="status" variant="body2">
            {state.isLoading
              ? state.source === 'previous'
                ? '工作計畫目前不可用，正在重新讀取。'
                : '正在讀取工作計畫…'
              : '工作計畫目前不可用。'}
          </Typography>
        ) : state.plan === null ? (
          <Typography variant="body2">尚未建立工作計畫。</Typography>
        ) : state.plan === '' ? (
          <Typography variant="body2">工作計畫目前沒有記錄項目。</Typography>
        ) : (
          <SafeMarkdown markdown={state.plan} />
        )}
        {state.error != null && (
          <Alert
            severity="error"
            action={
              <Button color="inherit" onClick={state.retry}>
                重新讀取工作計畫
              </Button>
            }
          >
            {describeReadError(state.error)}
          </Alert>
        )}
      </Box>
    </Box>
  );
}
