import { Navigate, Link, Route, Routes } from 'react-router';
import { WorkspaceListPage } from '../features/workspace/WorkspaceListPage';
import { AppShell } from './AppShell';
import { WorkspaceRoute } from './WorkspaceRoute';
import { useQueryClient } from '@tanstack/react-query';
import { clearWorkspaceQueries } from './workspace-queries';

export function App() {
  const cache = useQueryClient();
  return (
    <Routes>
      <Route element={<AppShell />}>
        <Route index element={<Navigate to="/workspaces" replace />} />
        <Route
          path="workspaces"
          element={
            <WorkspaceListPage onDeleted={(id) => clearWorkspaceQueries(cache, id)} />
          }
        />
        <Route
          path="*"
          element={
            <section className="empty-state">
              <h1>找不到這個頁面</h1>
              <Link className="primary-button" to="/workspaces">
                返回工作區
              </Link>
            </section>
          }
        />
      </Route>
      <Route path="workspaces/:workspaceId/jd" element={<WorkspaceRoute />} />
      <Route
        path="workspaces/:workspaceId/jd/history"
        element={<WorkspaceRoute history />}
      />
    </Routes>
  );
}
