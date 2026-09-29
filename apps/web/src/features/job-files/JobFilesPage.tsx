/** Job-file selection uses persistent identity; duplicate display names remain distinct. */
import { useState } from 'react';
import { Link as RouterLink, useNavigate } from 'react-router';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import {
  Alert,
  Button,
  Paper,
  Stack,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Typography,
} from '@mui/material';
import { describeReadError } from '../../shared/api/http';
import { CreateJobFileDialog } from './CreateJobFileDialog';
import { jobFilesQuery } from './job-file-api';

export function JobFilesPage() {
  const files = useQuery(jobFilesQuery);
  const cache = useQueryClient();
  const navigate = useNavigate();
  const [isCreating, setIsCreating] = useState(false);

  function created(jobFileId: string): void {
    setIsCreating(false);
    // Do not cache creation-time metadata as the latest metadata on a replay.
    void cache.invalidateQueries({ queryKey: jobFilesQuery.queryKey });
    void navigate(`/job-files/${jobFileId}`);
  }

  return (
    <Stack spacing={3}>
      <div className="page-heading">
        <div>
          <Typography variant="h4" component="h1">
            職務檔案
          </Typography>
          <p>以訪談理解工作，逐步形成有依據的職務說明書。</p>
        </div>
        <Button variant="contained" onClick={() => setIsCreating(true)}>
          建立職務檔案
        </Button>
      </div>
      {files.isPending && <p role="status">正在讀取職務檔案…</p>}
      {files.isError && (
        <Alert
          severity="error"
          action={
            <Button
              color="inherit"
              onClick={() => {
                void files.refetch();
              }}
            >
              重新讀取
            </Button>
          }
        >
          {describeReadError(files.error)}
        </Alert>
      )}
      {files.data &&
        !files.isError &&
        (files.data.job_files.length === 0 ? (
          <Paper variant="outlined" className="empty-state">
            <Typography variant="h6" component="h2">
              尚無職務檔案
            </Typography>
            <p>先建立一份職務檔案，記錄受訪者與工作。</p>
          </Paper>
        ) : (
          <TableContainer component={Paper} variant="outlined">
            <Table aria-label="職務檔案清單">
              <TableHead>
                <TableRow>
                  <TableCell>職務檔案</TableCell>
                  <TableCell>受訪員工</TableCell>
                  <TableCell>建立時間</TableCell>
                  <TableCell align="right">操作</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {files.data.job_files.map((file) => (
                  <TableRow key={file.job_file_id}>
                    <TableCell>
                      <strong>{file.display_name}</strong>
                      <small className="file-identity" title={file.job_file_id}>
                        識別 {file.job_file_id.slice(0, 8)}
                      </small>
                    </TableCell>
                    <TableCell>{file.employee_name}</TableCell>
                    <TableCell>
                      <time dateTime={file.created_at}>
                        {new Date(file.created_at).toLocaleString('zh-TW')}
                      </time>
                    </TableCell>
                    <TableCell align="right">
                      <Button
                        component={RouterLink}
                        to={`/job-files/${file.job_file_id}`}
                        aria-label={`開啟 ${file.display_name}（${file.employee_name}，${file.job_file_id.slice(0, 8)}）`}
                      >
                        開啟
                      </Button>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </TableContainer>
        ))}
      {isCreating && (
        <CreateJobFileDialog onClose={() => setIsCreating(false)} onCreated={created} />
      )}
    </Stack>
  );
}
