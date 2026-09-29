/** Page composition joins metadata and interview features; neither imports the other's internals. */
import { Link as RouterLink, useParams } from 'react-router';
import { useQuery } from '@tanstack/react-query';
import { Alert, Button, Stack, Typography } from '@mui/material';
import { InterviewHistory } from '../features/interview/InterviewHistory';
import { jobFileQuery } from '../features/job-files/job-file-api';
import { describeReadError } from '../shared/api/http';

export function JobFilePage() {
  const { jobFileId } = useParams();
  return jobFileId ? <JobFileContent key={jobFileId} jobFileId={jobFileId} /> : null;
}

function JobFileContent({ jobFileId }: { jobFileId: string }) {
  const file = useQuery(jobFileQuery(jobFileId));
  return (
    <Stack spacing={3}>
      <div>
        <Button component={RouterLink} to="/">
          ← 職務檔案清單
        </Button>
      </div>
      {file.isPending && <p role="status">正在開啟職務檔案…</p>}
      {file.isError && (
        <Alert
          severity="error"
          action={
            <Button
              color="inherit"
              onClick={() => {
                void file.refetch();
              }}
            >
              重新讀取
            </Button>
          }
        >
          {describeReadError(file.error)}
        </Alert>
      )}
      {file.data && !file.isError && (
        <>
          <header>
            <Typography variant="h4" component="h1">
              {file.data.display_name}
            </Typography>
            <p>受訪員工：{file.data.employee_name}</p>
          </header>
          <Alert severity="info">
            已可管理檔案與回看開場。AI 訪談與 JD 編輯尚未開放，這裡不會送出模型請求。
          </Alert>
          <InterviewHistory jobFileId={jobFileId} />
        </>
      )}
    </Stack>
  );
}
