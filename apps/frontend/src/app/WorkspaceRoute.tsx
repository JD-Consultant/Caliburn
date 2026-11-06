import { useQuery, useQueryClient } from '@tanstack/react-query';
import { lazy, Suspense, useCallback, useState } from 'react';
import { Link as RouterLink, useParams } from 'react-router';
import { Button, Link } from '@mui/material';
import { workspaceOptions } from '../features/workspace/queries';
import { workspaceErrorMessage } from '../features/workspace/errors';
import { InterviewPane } from '../features/interview/InterviewPane';
import { useAgentTurns } from '../features/interview/queries';
import { MemoryViewer } from '../features/memory/MemoryViewer';
import { memoryMapOptions } from '../features/memory/queries';
import { TurnJobDescriptionChanges } from '../features/job-description/TurnJobDescriptionChanges';
import { ErrorNotice, LoadingState } from '../shared/ui/Feedback';
import { WorkspaceLayout } from './WorkspaceLayout';
import { refreshWorkspaceQueries } from './workspace-queries';

const JobDescriptionPage = lazy(async () => ({
  default: (await import('../features/job-description/JobDescriptionPage'))
    .JobDescriptionPage,
}));
const JobDescriptionHistoryPage = lazy(async () => ({
  default: (await import('../features/job-description/history/JobDescriptionHistoryPage'))
    .JobDescriptionHistoryPage,
}));

function WorkspaceContent({
  workspaceId,
  intervieweeName,
  history,
}: {
  workspaceId: string;
  intervieweeName: string;
  history: boolean;
}) {
  const cache = useQueryClient();
  const turns = useAgentTurns(workspaceId);
  const memory = useQuery(memoryMapOptions(workspaceId));
  const [memoryOpen, setMemoryOpen] = useState(false);
  const refresh = useCallback(() => {
    void refreshWorkspaceQueries(cache, workspaceId);
  }, [cache, workspaceId]);
  const readOnly =
    turns.isPending ||
    turns.isError ||
    turns.isFetching ||
    turns.data.some((turn) => turn.status !== 'completed');
  const bar = (
    <header className="file-bar">
      <Link component={RouterLink} to="/workspaces" className="brand" underline="none">
        Caliburn
      </Link>
      <Button component={RouterLink} to="/workspaces" size="small">
        工作區
      </Button>
      <div className="file-bar-title">
        <h1>{intervieweeName}</h1>
      </div>
      <Button size="small" onClick={() => setMemoryOpen(true)}>
        工作記憶
      </Button>
    </header>
  );
  return (
    <>
      {history && (
        <>
          <div>{bar}</div>
          <main className="history-container">
            <Suspense fallback={<LoadingState />}>
              <JobDescriptionHistoryPage
                workspaceId={workspaceId}
                intervieweeName={intervieweeName}
                readOnly={readOnly}
              />
            </Suspense>
          </main>
        </>
      )}
      <div hidden={history}>
        <WorkspaceLayout
          initialPane={history ? 'jd' : 'interview'}
          bar={bar}
          interview={
            <InterviewPane
              workspaceId={workspaceId}
              intervieweeName={intervieweeName}
              turnsQuery={turns}
              onWorkspaceChanged={refresh}
              renderTurnChanges={(turn) => (
                <TurnJobDescriptionChanges
                  workspaceId={workspaceId}
                  turnId={turn.turn_id}
                  readOnly={readOnly}
                  onChanged={refresh}
                />
              )}
            />
          }
          document={
            <Suspense fallback={<LoadingState />}>
              <JobDescriptionPage
                workspaceId={workspaceId}
                intervieweeName={intervieweeName}
                readOnly={readOnly}
                {...(memory.isSuccess && memory.data.published_version !== null
                  ? { comparisonPublishedVersion: memory.data.published_version }
                  : {})}
              />
            </Suspense>
          }
        />
      </div>
      <MemoryViewer
        workspaceId={workspaceId}
        open={memoryOpen}
        onClose={() => setMemoryOpen(false)}
      />
    </>
  );
}

export function WorkspaceRoute({ history = false }: { history?: boolean }) {
  const { workspaceId = '' } = useParams();
  const workspace = useQuery(workspaceOptions(workspaceId));
  if (workspace.isPending) return <LoadingState />;
  if (workspace.isError)
    return (
      <main className="route-error">
        <Link component={RouterLink} to="/workspaces">
          返回工作區
        </Link>
        <ErrorNotice
          message={workspaceErrorMessage(workspace.error)}
          onRetry={() => {
            void workspace.refetch();
          }}
        />
      </main>
    );
  return (
    <WorkspaceContent
      key={workspaceId.toLowerCase()}
      workspaceId={workspace.data.workspace_id}
      intervieweeName={workspace.data.interviewee_name}
      history={history}
    />
  );
}
