/** Routes and confirmed deletion lifecycle; features own their screens and data queries. */
import type { ReactNode } from 'react';
import { Link as RouterLink, Outlet, Route, Routes } from 'react-router';
import { Alert, Container, Link } from '@mui/material';
import { JobFilesPage } from '../features/job-files/JobFilesPage';
import { AppHeader } from './AppHeader';
import { JobFilePage } from './JobFilePage';
import { DeletedJobFilesContext } from './deleted-job-files-context';
import { useDeletedJobFiles } from './use-deleted-job-files';

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
  const deletion = useDeletedJobFiles();
  return (
    <DeletedJobFilesContext.Provider value={deletion.context}>
      {deletion.warning && <Alert severity="warning">{deletion.warning}</Alert>}
      <Routes>
        <Route element={<HeaderLayout />}>
          <Route
            path="/"
            element={
              <PageContainer>
                <JobFilesPage onDeleted={deletion.context.confirmDeleted} />
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
    </DeletedJobFilesContext.Provider>
  );
}
