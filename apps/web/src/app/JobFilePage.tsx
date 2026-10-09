/** Page composition: metadata gate, then the workspace. Features never import each other. */
import type { ReactNode } from 'react';
import type { UseQueryResult } from '@tanstack/react-query';
import type { JobFile } from '../shared/api/generated/job-file-list';
import { useContext, useEffect } from 'react';
import { DeletedJobFilesContext } from './deleted-job-files-context';
import { canonicalUuid } from '../shared/api/uuid';
import { Link as RouterLink, useParams } from 'react-router';
import { useQuery } from '@tanstack/react-query';
import { Alert, Button, Container, Stack } from '@mui/material';
import { useCurrentTurn } from '../features/interview/use-current-turn';
import { jobFileQuery } from '../features/job-files/job-file-api';
import { ApiError, describeReadError } from '../shared/api/http';
import { AppHeader } from './AppHeader';
import { FileBar } from './FileBar';
import { InterviewPane } from './InterviewPane';
import { JdPane } from './JdPane';
import { WorkspaceLayout } from './WorkspaceLayout';

/** The route is the only place a user-typed spelling enters; below it one canonical id is the scope. */
export function JobFilePage() {
  const jobFileId = canonicalUuid(useParams().jobFileId);
  const deletion = useContext(DeletedJobFilesContext);
  if (jobFileId === null) return <UnavailableFile deleted={false} />;
  const deleted = deletion.deleted.has(jobFileId);
  return deleted ? (
    <UnavailableFile deleted />
  ) : (
    <JobFileContent key={jobFileId} jobFileId={jobFileId} />
  );
}

function JobFileContent({ jobFileId }: { jobFileId: string }) {
  const file = useQuery(jobFileQuery(jobFileId));
  const deletion = useContext(DeletedJobFilesContext);
  const missing =
    file.error instanceof ApiError &&
    file.error.status === 404 &&
    file.error.code === 'job_file_not_found';
  useEffect(() => {
    if (missing) void deletion.confirmDeleted(jobFileId).catch(() => {});
  }, [missing, deletion, jobFileId]);
  if (missing) return <UnavailableFile deleted />;
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
  return <JobFileWorkspace jobFileId={jobFileId} file={file} retry={retry} />;
}

function JobFileWorkspace({
  jobFileId,
  file,
  retry,
}: {
  jobFileId: string;
  file: UseQueryResult<JobFile>;
  retry: ReactNode;
}) {
  const { turn, isVerified } = useCurrentTurn(jobFileId);
  if (!file.data) return null;
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

function UnavailableFile({ deleted }: { deleted: boolean }) {
  return (
    <>
      <AppHeader />
      <Container component="main" maxWidth="md" sx={{ py: 4 }}>
        <h1>{deleted ? '這份職務檔案已刪除' : '找不到這份職務檔案'}</h1>
        <Button component={RouterLink} to="/">
          返回職務檔案清單
        </Button>
      </Container>
    </>
  );
}
