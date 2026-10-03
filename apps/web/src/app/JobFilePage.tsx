/** Page composition: metadata gate, then the workspace. Features never import each other. */
import { Link as RouterLink, useParams } from 'react-router';
import { useQuery } from '@tanstack/react-query';
import { Alert, Button, Container, Stack } from '@mui/material';
import { useCurrentTurn } from '../features/interview/use-current-turn';
import { jobFileQuery } from '../features/job-files/job-file-api';
import { describeReadError } from '../shared/api/http';
import { AppHeader } from './AppHeader';
import { FileBar } from './FileBar';
import { InterviewPane } from './InterviewPane';
import { JdPane } from './JdPane';
import { WorkspaceLayout } from './WorkspaceLayout';

export function JobFilePage() {
  const { jobFileId } = useParams();
  return jobFileId ? <JobFileContent key={jobFileId} jobFileId={jobFileId} /> : null;
}

function JobFileContent({ jobFileId }: { jobFileId: string }) {
  const file = useQuery(jobFileQuery(jobFileId));
  const { turn, isVerified } = useCurrentTurn(jobFileId);
  const retry = (
    <Button
      color="inherit"
      onClick={() => {
        void file.refetch();
      }}
    >
      重新讀取
    </Button>
  );
  if (!file.data) {
    return (
      <>
        <AppHeader />
        <Container component="main" maxWidth="md" sx={{ py: 4 }}>
          <Stack spacing={2}>
            <div>
              <Button component={RouterLink} to="/">
                ← 職務檔案清單
              </Button>
            </div>
            {file.isPending && <p role="status">正在開啟職務檔案…</p>}
            {file.isError && (
              <Alert severity="error" action={retry}>
                {describeReadError(file.error)}
              </Alert>
            )}
          </Stack>
        </Container>
      </>
    );
  }
  return (
    <WorkspaceLayout
      bar={<FileBar file={file.data} turn={turn} />}
      banner={
        file.isError ? (
          <div className="workspace-banner">
            <Alert severity="error" action={retry}>
              {describeReadError(file.error)}
            </Alert>
          </div>
        ) : null
      }
      interview={<InterviewPane jobFileId={jobFileId} />}
      document={<JdPane jobFileId={jobFileId} turn={turn} turnVerified={isVerified} />}
    />
  );
}
