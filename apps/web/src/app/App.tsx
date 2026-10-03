/** Route composition only; feature modules own their screens and data queries. */
import type { ReactNode } from 'react';
import { Link as RouterLink, Outlet, Route, Routes } from 'react-router';
import { Container, Link } from '@mui/material';
import { JobFilesPage } from '../features/job-files/JobFilesPage';
import { AppHeader } from './AppHeader';
import { JobFilePage } from './JobFilePage';

function PageContainer({ children }: { children: ReactNode }) {
  return (
    <Container component="main" maxWidth="md" sx={{ py: 6 }}>
      {children}
    </Container>
  );
}

/** Pages under this layout share the global header; the job-file workspace has its own top bar. */
function HeaderLayout() {
  return (
    <>
      <AppHeader />
      <Outlet />
    </>
  );
}

export function App() {
  return (
    <Routes>
      <Route element={<HeaderLayout />}>
        <Route
          path="/"
          element={
            <PageContainer>
              <JobFilesPage />
            </PageContainer>
          }
        />
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
      </Route>
      <Route path="/job-files/:jobFileId" element={<JobFilePage />} />
    </Routes>
  );
}
