import { Alert, Box, Button, Chip, Typography } from '@mui/material';
import { useQuery } from '@tanstack/react-query';
import { useEffect, useRef } from 'react';
import type { MemoryCitationContentResponse } from '../../../shared/api/generated/types.gen';
import { HttpError } from '../../../shared/api/http';
import { jobDescriptionOptions } from '../queries';
import { getCitation, type CitationScope } from './source-api';

export function CitationDetails({
  scope,
  currentVersion,
}: {
  scope: CitationScope;
  currentVersion?: number | undefined;
}) {
  const heading = useRef<HTMLHeadingElement>(null);
  const detail = useQuery({
    queryKey: [
      ...jobDescriptionOptions(scope.workspaceId).queryKey,
      scope.jobDescriptionId,
      'citations',
      scope.version ?? 'current',
      scope.version === undefined ? currentVersion : undefined,
      scope.citation,
      scope.comparisonPublishedVersion,
    ],
    queryFn: ({ signal }) => getCitation(scope, signal),
  });
  useEffect(() => {
    heading.current?.focus();
  }, [scope.citation.id, detail.isSuccess]);
  if (detail.isPending) return <p role="status">正在讀取來源…</p>;
  if (detail.isError)
    return (
      <Alert
        severity="error"
        action={
          <Button
            color="inherit"
            onClick={() => {
              void detail.refetch();
            }}
          >
            重試
          </Button>
        }
      >
        {detail.error instanceof HttpError && detail.error.status === 404
          ? '此引用已不存在或無法查閱。請重新讀取 JD 後核對。'
          : '無法讀取來源，核對狀態仍未知。請檢查連線後重試。'}
      </Alert>
    );
  const { source, needs_recheck: needsRecheck, comparison } = detail.data;
  return (
    <Box className="jd-source-details">
      <Typography component="h4" variant="subtitle1" tabIndex={-1} ref={heading}>
        {source.title ??
          (source.source.kind === 'interview' ? '訪談原文' : 'Memory 原件')}
      </Typography>
      <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap', my: 1 }}>
        <Chip
          size="small"
          color={needsRecheck === true ? 'warning' : 'default'}
          label={
            needsRecheck === null
              ? '核對狀態未知'
              : needsRecheck
                ? '待核對'
                : '未標示待核對'
          }
        />
        {source.source.kind === 'memory' && (
          <Chip
            size="small"
            label={`固定發布版 ${String(source.source.published_version)}`}
          />
        )}
        {detail.data.citation.jd_changed && <Chip size="small" label="JD 內容已變更" />}
      </Box>
      <Typography variant="body2" color="text.secondary">
        查閱不會解除待核對標記；未知不代表已確認。
      </Typography>
      {source.availability === 'unavailable' ? (
        <Alert severity="warning" sx={{ my: 2 }}>
          來源目前不可用，保留引用定位供核對。
        </Alert>
      ) : (
        <Typography component="div" className="jd-source-text">
          {source.text ?? '來源沒有可顯示的文字。'}
        </Typography>
      )}
      {comparison && (
        <Box component="section" sx={{ mt: 2 }} aria-label="Memory 來源比較">
          <Typography component="h5" variant="subtitle2">
            固定原件與發布版 {scope.comparisonPublishedVersion} 比較
          </Typography>
          <Typography variant="body2">
            {comparison.source_changed ? '來源有變更，請核對。' : '這兩份來源內容相同。'}
          </Typography>
          <details>
            <summary>查看來源比較內容</summary>
            <MemoryContent content={comparison.before} label="引用時原件" />
            {comparison.after ? (
              <MemoryContent content={comparison.after} label="比較發布版" />
            ) : (
              <Alert severity="warning">這個項目在比較發布版中已不存在。</Alert>
            )}
          </details>
        </Box>
      )}
      <Button
        size="small"
        disabled={detail.isFetching}
        onClick={() => {
          void detail.refetch();
        }}
      >
        重新讀取來源
      </Button>
    </Box>
  );
}

function MemoryContent({
  content,
  label,
}: {
  content: MemoryCitationContentResponse;
  label: string;
}) {
  return (
    <Box component="section" sx={{ py: 1 }}>
      <Typography component="h6" variant="subtitle2">
        {label}
      </Typography>
      {[content.item, ...content.situations].map((item) => (
        <Box key={item.id} sx={{ py: 1 }}>
          <Typography sx={{ fontWeight: 600 }}>{item.content.title}</Typography>
          <Typography className="jd-source-text">{item.content.description}</Typography>
          <Typography className="jd-source-text">{item.content.body}</Typography>
        </Box>
      ))}
    </Box>
  );
}
