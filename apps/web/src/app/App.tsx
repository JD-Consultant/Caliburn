/** Route composition only; feature modules own their screens and data queries. */
import { Link as RouterLink, Route, Routes } from 'react-router';
import { Chip, Container, Link, Stack, Typography } from '@mui/material';
import { JobFilesPage } from '../features/job-files/JobFilesPage';
import { JobFilePage } from './JobFilePage';

export function App() {
  return (
    <>
      <header className="app-header">
        <Container maxWidth="lg">
          <Stack direction="row" spacing={2} sx={{ alignItems: 'center' }}>
            <Link component={RouterLink} to="/" underline="none" className="brand">
              Caliburn
            </Link>
            <Typography variant="body2" color="text.secondary">
              職務訪談與職務說明書
            </Typography>
            <Chip label="新架構開發中" size="small" variant="outlined" />
          </Stack>
        </Container>
      </header>
      <Container component="main" maxWidth="lg" sx={{ py: 5 }}>
        <Routes>
          <Route path="/" element={<JobFilesPage />} />
          <Route path="/job-files/:jobFileId" element={<JobFilePage />} />
          <Route
            path="*"
            element={
              <>
                <h1>找不到這個頁面</h1>
                <Link component={RouterLink} to="/">
                  返回職務檔案清單
                </Link>
              </>
            }
          />
        </Routes>
      </Container>
    </>
  );
}
