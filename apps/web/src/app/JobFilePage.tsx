/** Page composition joins metadata and interview features; neither imports the other's internals. */
import { Link as RouterLink, useParams } from 'react-router';
import { useQuery } from '@tanstack/react-query';
import { Alert, Button, Stack, Typography } from '@mui/material';
import { InterviewHistory } from '../features/interview/InterviewHistory';
import { JdProfileEditor } from '../features/jd-editor/JdProfileEditor';
import { JdWorkEditor } from '../features/jd-editor/JdWorkEditor';
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
            已可編輯 JD 基本資料、職責、任務及共用知識／技能，並回看開場。協作／條件等其餘欄位及 AI
            訪談仍在開發，這裡不會送出模型請求。
          </Alert>
          <InterviewHistory jobFileId={jobFileId} />
          <JdProfileEditor jobFileId={jobFileId} />
          <JdWorkEditor jobFileId={jobFileId} />
        </>
      )}
    </Stack>
  );
}
