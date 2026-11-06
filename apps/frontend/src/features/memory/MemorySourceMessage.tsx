/** Read the full saved Interview original for a published situation's selected source. */
import { useQuery } from '@tanstack/react-query';
import { Alert, Box, Button, Typography } from '@mui/material';
import type { MessageView } from '../../shared/api/generated/types.gen';
import { describeMemoryError } from './errors';
import { memorySourceOptions } from './queries';

const speakers: Record<MessageView['speaker'], string> = {
  app: 'App 開場引導',
  employee: '受訪員工',
  consultant: '職務顧問',
};

export function MemorySourceMessage({
  workspaceId,
  messageId,
}: {
  workspaceId: string;
  messageId: string;
}) {
  const query = useQuery(memorySourceOptions(workspaceId, messageId));
  return (
    <Box
      component="section"
      aria-label="訪談原件"
      sx={{ border: 1, borderColor: 'divider', borderRadius: 2, p: 2 }}
    >
      <Button
        size="small"
        aria-disabled={query.isFetching}
        onClick={() => {
          if (!query.isFetching) void query.refetch();
        }}
      >
        重新讀取來源
      </Button>
      {query.isPending ? (
        <p role="status">正在讀取訪談來源…</p>
      ) : query.isError ? (
        <Alert severity="error">{describeMemoryError(query.error)}</Alert>
      ) : (
        <>
          <Typography component="h5" variant="subtitle2">
            {speakers[query.data.speaker]}
          </Typography>
          <OriginalContent content={query.data.content} />
        </>
      )}
    </Box>
  );
}

function OriginalContent({ content }: { content: MessageView['content'] }) {
  const textStyle = { whiteSpace: 'pre-wrap', overflowWrap: 'anywhere' };
  if ('text' in content) return <Typography sx={textStyle}>{content.text}</Typography>;
  if ('question' in content)
    return (
      <>
        <Typography sx={textStyle}>{content.question}</Typography>
        {(content.options ?? []).map((option) => (
          <Typography key={option.label} sx={textStyle}>
            {option.label}
            {option.description == null ? '' : `：${option.description}`}
          </Typography>
        ))}
      </>
    );
  const selected = content.selected ?? [];
  return (
    <>
      {selected.length > 0 && (
        <Typography sx={textStyle}>選擇：{selected.join('、')}</Typography>
      )}
      {content.custom != null && (
        <Typography sx={textStyle}>自填：{content.custom}</Typography>
      )}
      {selected.length === 0 && content.custom == null && <Typography>略過</Typography>}
    </>
  );
}
