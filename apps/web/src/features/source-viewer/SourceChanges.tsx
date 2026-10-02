/** Read-only comparisons share one request but keep their distinct baselines visible. */
import { useQuery } from '@tanstack/react-query';
import { Alert, Box, Stack, Typography } from '@mui/material';
import type { SourceScope } from './source-api';
import { describeSourceError, jdSourceChangesQuery } from './source-api';
import { SafeMarkdown } from '../../shared/ui/SafeMarkdown';

export function SourceChanges({ scope, sourceLabel }: { scope: SourceScope; sourceLabel: string }) {
  const changes = useQuery(jdSourceChangesQuery(scope));
  return (
    <Stack spacing={2} className="source-details" sx={{ minWidth: 0 }}>
      <Typography variant="h6" component="h3">
        差異回查：{sourceLabel}
      </Typography>
      <Typography variant="body2" color="text.secondary">
        JD 比較此項目上次核對時與目前正式稿；來源比較原引用與讀取當時最新已發布的
        Memory。閱讀不會解除待核對。
      </Typography>
      {changes.isFetching ? (
        <p role="status">正在讀取差異…</p>
      ) : changes.isError ? (
        <Alert severity="error">{describeSourceError(changes.error)}</Alert>
      ) : (
        changes.data && (
          <Stack spacing={1}>
            <ChangeSection title="JD 內容變更" markdown={changes.data.jd_markdown} />
            {changes.data.source_markdown !== null && (
              <ChangeSection title="來源變更" markdown={changes.data.source_markdown} />
            )}
          </Stack>
        )
      )}
    </Stack>
  );
}

function ChangeSection({ title, markdown }: { title: string; markdown: string }) {
  return (
    <Box
      component="details"
      sx={{ minWidth: 0, '& > summary': { cursor: 'pointer', py: 1, fontWeight: 600 } }}
    >
      <summary>{title}</summary>
      <SafeMarkdown markdown={markdown} />
    </Box>
  );
}
