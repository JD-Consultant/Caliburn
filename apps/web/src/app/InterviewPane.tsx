/** Message log scrolls; the composer / Turn controls dock stays reachable at the bottom. */
import { useQueryClient } from '@tanstack/react-query';
import type { ConsultantTurn } from '../shared/api/generated/consultant-turn';
import { InterviewComposer } from '../features/interview/InterviewComposer';
import { InterviewHistory } from '../features/interview/InterviewHistory';
import { consultantTurnQuery } from '../features/interview/interview-turn-api';
import { UndoTurnJd } from '../features/jd-editor/UndoTurnJd';
import { useStickToBottom } from '../shared/ui/use-stick-to-bottom';

interface Props {
  jobFileId: string;
  onTurnChange: (turn: ConsultantTurn | null) => void;
}

export function InterviewPane({ jobFileId, onTurnChange }: Props) {
  const queryClient = useQueryClient();
  const scroller = useStickToBottom<HTMLDivElement>();
  return (
    <>
      <div className="pane-header">
        <h2 className="pane-title">與職務顧問訪談</h2>
      </div>
      <div className="pane-scroll" ref={scroller}>
        <div className="interview-content">
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
          <InterviewComposer jobFileId={jobFileId} onTurnChange={onTurnChange} />
        </div>
      </div>
    </>
  );
}
