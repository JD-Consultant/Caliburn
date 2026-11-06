import { useQuery, useQueryClient } from '@tanstack/react-query';
import { Alert, Box, Typography } from '@mui/material';
import { RefreshIcon } from '../../shared/ui/icons';
import { HttpError } from '../../shared/api/http';
import { IconAction } from '../../shared/ui/IconAction';
import { ErrorNotice, LoadingState } from '../../shared/ui/Feedback';
import { jobDescriptionOptions, synchronizeJobDescription } from './queries';
import { JobDescriptionEditor } from './editor/JobDescriptionEditor';
import { JobDescriptionEditorProvider } from './editing/JobDescriptionEditorProvider';
import { EditorNavigation } from './editing/EditorNavigation';
import { ExportJobDescription } from './ExportJobDescription';
import { JobDescriptionSourcesProvider } from './sources/JobDescriptionSourcesProvider';
import { JobDescriptionSources } from './sources/JobDescriptionSources';

export function JobDescriptionPage({
  workspaceId,
  intervieweeName,
  readOnly = false,
  comparisonPublishedVersion,
}: {
  workspaceId: string;
  intervieweeName: string;
  readOnly?: boolean;
  comparisonPublishedVersion?: number;
}) {
  const cache = useQueryClient();
  const jd = useQuery(jobDescriptionOptions(workspaceId));
  const heading = (
    <Box
      className="jd-pane-heading"
      sx={{
        display: 'flex',
        alignItems: 'center',
        gap: 1,
        px: 2,
        py: 1,
        borderBottom: 1,
        borderColor: 'divider',
      }}
    >
      <Typography
        component="h2"
        variant="subtitle2"
        sx={{ flex: '1 0 auto', whiteSpace: 'nowrap' }}
      >
        職務說明書
      </Typography>
      <IconAction
        label="重新讀取職務說明書"
        disabled={jd.isFetching}
        onClick={() => {
          void jd.refetch();
        }}
      >
        <RefreshIcon />
      </IconAction>
    </Box>
  );
  if (jd.isPending)
    return (
      <>
        {heading}
        <LoadingState />
      </>
    );
  if (jd.isError)
    return (
      <>
        {heading}
        <ErrorNotice
          message={
            jd.error instanceof HttpError && jd.error.status === 404
              ? '找不到這份工作區，可能已經被刪除。請返回清單。'
              : '無法讀取職務說明書，請檢查連線後重試。'
          }
          onRetry={() => {
            void jd.refetch();
          }}
        />
      </>
    );
  if (!jd.data)
    return (
      <>
        {heading}
        <Alert severity="error">
          工作區的職務說明書尚未正確初始化。請重新讀取，或返回清單確認工作區。
        </Alert>
      </>
    );
  return (
    <JobDescriptionEditorProvider
      key={jd.data.job_description_id}
      jobDescription={jd.data}
      readOnly={readOnly}
      onSaved={(result) => synchronizeJobDescription(cache, result)}
    >
      <JobDescriptionSourcesProvider
        jobDescription={jd.data}
        comparisonPublishedVersion={comparisonPublishedVersion}
      >
        <Box
          className="jd-pane-heading"
          sx={{
            display: 'flex',
            alignItems: 'center',
            flexWrap: 'wrap',
            gap: 1,
            px: 2,
            py: 1,
            borderBottom: 1,
            borderColor: 'divider',
          }}
        >
          <Typography
            component="h2"
            variant="subtitle2"
            sx={{ flex: '1 0 auto', whiteSpace: 'nowrap' }}
          >
            職務說明書
          </Typography>
          <Typography variant="caption" color="text.secondary">
            {intervieweeName}
          </Typography>
          <EditorNavigation />
          <JobDescriptionSources />
          <ExportJobDescription />
          <IconAction
            label="重新讀取職務說明書"
            disabled={jd.isFetching}
            onClick={() => {
              void jd.refetch();
            }}
          >
            <RefreshIcon />
          </IconAction>
        </Box>
        {readOnly && <Alert severity="info">訪談處理尚未結束，目前僅供查閱。</Alert>}
        <div className="pane-scroll">
          <JobDescriptionEditor />
        </div>
      </JobDescriptionSourcesProvider>
    </JobDescriptionEditorProvider>
  );
}
