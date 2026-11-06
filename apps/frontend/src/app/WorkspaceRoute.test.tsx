import { useState } from 'react';
import { QueryClientProvider } from '@tanstack/react-query';
import { Link, MemoryRouter, Route, Routes } from 'react-router';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { expect, it, vi } from 'vitest';
import { createQueryClient } from './query-client';
import { WorkspaceRoute } from './WorkspaceRoute';

vi.mock('../features/workspace/queries', () => ({
  workspaceOptions: () => ({
    queryKey: ['workspace', 'a'],
    queryFn: () => Promise.resolve({ workspace_id: 'a', interviewee_name: '測試受訪者' }),
  }),
}));
vi.mock('../features/interview/queries', () => ({
  useAgentTurns: () => ({
    isPending: false,
    isError: false,
    isFetching: false,
    data: [],
  }),
}));
vi.mock('./workspace-queries', () => ({ refreshWorkspaceQueries: vi.fn() }));
vi.mock('../features/memory/queries', () => ({
  memoryMapOptions: () => ({
    queryKey: ['memory', 'a', 'map'],
    queryFn: () =>
      Promise.resolve({ workspace_id: 'a', published_version: null, items: [] }),
  }),
}));
vi.mock('../features/interview/InterviewPane', () => ({
  InterviewPane: function Composer() {
    const [draft, setDraft] = useState('');
    return (
      <input
        aria-label="未送訪談"
        value={draft}
        onChange={(event) => setDraft(event.target.value)}
      />
    );
  },
}));
vi.mock('../features/memory/MemoryViewer', () => ({ MemoryViewer: () => null }));
vi.mock('../features/job-description/TurnJobDescriptionChanges', () => ({
  TurnJobDescriptionChanges: () => null,
}));
vi.mock('../features/job-description/JobDescriptionPage', () => ({
  JobDescriptionPage: () => <Link to="/workspaces/a/jd/history">版本歷史</Link>,
}));
vi.mock('../features/job-description/history/JobDescriptionHistoryPage', () => ({
  JobDescriptionHistoryPage: () => <Link to="/workspaces/a/jd">返回職務說明書</Link>,
}));

it('查看歷史再返回保留同一工作區的未送訪談草稿', async () => {
  const user = userEvent.setup();
  const cache = createQueryClient();
  render(
    <QueryClientProvider client={cache}>
      <MemoryRouter initialEntries={['/workspaces/a/jd']}>
        <Routes>
          <Route path="/workspaces/:workspaceId/jd" element={<WorkspaceRoute />} />
          <Route
            path="/workspaces/:workspaceId/jd/history"
            element={<WorkspaceRoute history />}
          />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
  await user.type(
    await screen.findByRole('textbox', { name: '未送訪談' }),
    '返回後仍保留',
  );
  await user.click(await screen.findByRole('link', { name: '版本歷史' }));
  await user.click(await screen.findByRole('link', { name: '返回職務說明書' }));
  expect(await screen.findByRole('textbox', { name: '未送訪談' })).toHaveValue(
    '返回後仍保留',
  );
  cache.clear();
});
