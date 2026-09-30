/** Route composition only; feature modules own their screens and data queries. */
import type { ReactNode } from 'react';
import { Link as RouterLink, Route, Routes } from 'react-router';
import { Chip, Container, Link, Typography } from '@mui/material';
import { JobFilesPage } from '../features/job-files/JobFilesPage';
import { JobFilePage } from './JobFilePage';

function PageContainer({ children }: { children: ReactNode }) {
  return (
    <Container component="main" maxWidth="lg" sx={{ py: 5 }}>
      {children}
    </Container>
  );
}

export function App() {
  return (
    <>
      <header className="app-header">
        <Link component={RouterLink} to="/" underline="none" className="brand">
          Caliburn
        </Link>
        <Typography variant="body2" color="text.secondary" className="app-tagline">
          職務訪談與職務說明書
        </Typography>
        <Chip label="新架構開發中" size="small" variant="outlined" />
      </header>
      <Routes>
        <Route
          path="/"
          element={
            <PageContainer>
              <JobFilesPage />
            </PageContainer>
          }
        />
        <Route path="/job-files/:jobFileId" element={<JobFilePage />} />
        <Route
          path="*"
          element={
            <PageContainer>
              <h1>找不到這個頁面</h1>
              <Link component={RouterLink} to="/">
                返回職務檔案清單
              </Link>
            </PageContainer>
          }
        />
      </Routes>
    </>
  );
}
