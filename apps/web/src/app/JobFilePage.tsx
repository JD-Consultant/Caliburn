/** Page composition joins metadata and interview features; neither imports the other's internals. */
import { Link as RouterLink, useParams } from 'react-router';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { Alert, Button, Stack, Typography } from '@mui/material';
import { InterviewHistory } from '../features/interview/InterviewHistory';
import { InterviewComposer } from '../features/interview/InterviewComposer';
import { consultantTurnQuery } from '../features/interview/interview-turn-api';
import { JdProfileEditor } from '../features/jd-editor/JdProfileEditor';
import { JdWorkEditor } from '../features/jd-editor/JdWorkEditor';
import { JdCandidatePreview } from '../features/jd-editor/JdCandidatePreview';
import { UndoTurnJd } from '../features/jd-editor/UndoTurnJd';
import { jobFileQuery } from '../features/job-files/job-file-api';
import { describeReadError } from '../shared/api/http';

export function JobFilePage() {
  const { jobFileId } = useParams();
  return jobFileId ? <JobFileContent key={jobFileId} jobFileId={jobFileId} /> : null;
}

function JobFileContent({ jobFileId }: { jobFileId: string }) {
  const file = useQuery(jobFileQuery(jobFileId));
  const queryClient = useQueryClient();
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
      {file.data && (
        <>
          <header>
            <Typography variant="h4" component="h1">
              {file.data.display_name}
            </Typography>
            <p>受訪員工：{file.data.employee_name}</p>
            <Button
              component="a"
              href={`/api/job-files/${encodeURIComponent(jobFileId)}/jd/export.pdf`}
              download
              variant="outlined"
              aria-describedby="jd-pdf-export-note"
            >
              匯出目前 JD（PDF）
            </Button>
            <Typography
              id="jd-pdf-export-note"
              variant="body2"
              color="text.secondary"
              sx={{ mt: 1 }}
            >
              匯出目前已正式保存的版本，不包含本輪候選預覽。
            </Typography>
          </header>
          <Alert severity="info">
            訪談原輸入會先保留；顧問完成並保存後，才會列入正式訪談並更新 JD。
          </Alert>
          <InterviewHistory
            jobFileId={jobFileId}
            renderTurnActions={(executionId) => (
              <UndoTurnJd
                jobFileId={jobFileId}
                executionId={executionId}
                onUndone={() =>
                  queryClient.invalidateQueries(
                    { queryKey: consultantTurnQuery(jobFileId, executionId).queryKey, exact: true },
                    { throwOnError: true },
                  )
                }
              />
            )}
          />
          <InterviewComposer
            jobFileId={jobFileId}
            renderCandidate={(candidate) => <JdCandidatePreview candidate={candidate} />}
          />
          <JdProfileEditor jobFileId={jobFileId} />
          <JdWorkEditor jobFileId={jobFileId} />
        </>
      )}
    </Stack>
  );
}
