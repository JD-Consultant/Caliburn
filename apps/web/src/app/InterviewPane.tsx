/** Message log scrolls; the composer / Turn controls dock stays reachable at the bottom. */
import { useQueryClient } from '@tanstack/react-query';
import { useCallback } from 'react';
import { InterviewComposer } from '../features/interview/InterviewComposer';
import { InterviewHistory } from '../features/interview/InterviewHistory';
import { InterviewPlan } from '../features/interview/InterviewPlan';
import { SpeakerAvatar } from '../features/interview/SpeakerAvatar';
import { UndoTurnJd } from '../features/jd-editor/UndoTurnJd';
import { JumpToLatest } from '../shared/ui/JumpToLatest';
import { useStickToBottom } from '../shared/ui/use-stick-to-bottom';
import { refreshCompletedInterview, refreshUndoneJd } from './workspace-refresh';

export function InterviewPane({ jobFileId }: { jobFileId: string }) {
  const queryClient = useQueryClient();
  const refreshCompletedTurn = useCallback(
    () => refreshCompletedInterview(queryClient, jobFileId),
    [queryClient, jobFileId],
  );
  const { ref: scroller, away, scrollToBottom } = useStickToBottom<HTMLDivElement>();
  return (
    <>
      <div className="pane-header">
        <div className="pane-heading">
          <SpeakerAvatar speaker="consultant" />
          <h2 className="pane-title">與職務顧問訪談</h2>
        </div>
      </div>
      <div className="pane-scroll" ref={scroller}>
        <div className="interview-content">
          <InterviewPlan key={jobFileId} jobFileId={jobFileId} />
          <InterviewHistory
            jobFileId={jobFileId}
            renderTurnActions={(executionId) => (
              <UndoTurnJd
                jobFileId={jobFileId}
                executionId={executionId}
                refresh={() => refreshUndoneJd(queryClient, jobFileId, executionId)}
              />
            )}
          />
          <InterviewComposer
            jobFileId={jobFileId}
            refreshCompletedTurn={refreshCompletedTurn}
            aboveDock={away ? <JumpToLatest onClick={scrollToBottom} /> : null}
          />
        </div>
      </div>
    </>
  );
}
