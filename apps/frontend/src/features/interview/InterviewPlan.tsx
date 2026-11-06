import { useQuery } from '@tanstack/react-query';
import { Alert, Box, Button, Typography } from '@mui/material';
import { SafeMarkdown } from '../../shared/ui/SafeMarkdown';
import { planOptions } from './queries';
import { interviewError } from './api';

export function InterviewPlan({ workspaceId }: { workspaceId: string }) {
  const plan = useQuery(planOptions(workspaceId));
  return (
    <Box
      component="details"
      sx={{ m: 2, p: 2, border: 1, borderColor: 'divider', borderRadius: 2 }}
    >
      <Typography component="summary" variant="subtitle2" sx={{ cursor: 'pointer' }}>
        工作計畫
      </Typography>
      {plan.isPending && <p role="status">正在讀取工作計畫…</p>}
      {plan.isError ? (
        <Alert
          severity="error"
          action={
            <Button
              onClick={() => {
                void plan.refetch();
              }}
            >
              重新讀取工作計畫
            </Button>
          }
        >
          {interviewError(plan.error)}
        </Alert>
      ) : (
        plan.data && (
          <>
            <Typography variant="caption" color="text.secondary">
              最新保存版本{plan.data.version === null ? '' : ` ${plan.data.version}`}
            </Typography>
            {plan.data.body === null ? (
              <p>尚未建立工作計畫。</p>
            ) : plan.data.body === '' ? (
              <p>工作計畫目前沒有記錄項目。</p>
            ) : (
              <SafeMarkdown markdown={plan.data.body} />
            )}
          </>
        )
      )}
    </Box>
  );
}
