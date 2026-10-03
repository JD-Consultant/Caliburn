/**
 * The exchange of one consultant turn that is not formal yet, shown as the two messages it will become:
 * the employee's original input, and the consultant's work. The composer renders this only before
 * completion; completed work is read through its formal historical reply.
 */
import type { ConsultantTurn } from '../../shared/api/generated/consultant-turn';
import { isTerminalTurn } from './interview-turn-api';
import { PublicTurnMessages, StreamingPublicTurnMessages } from './PublicTurnMessages';
import { ReasoningSummaries } from './ReasoningSummaries';
import { SpeakerAvatar } from './SpeakerAvatar';

export function TurnLog({ jobFileId, turn }: { jobFileId: string; turn: ConsultantTurn }) {
  const work =
    turn.status === 'active' ? (
      <StreamingPublicTurnMessages
        key={`${jobFileId}:${turn.execution_id}`}
        jobFileId={jobFileId}
        executionId={turn.execution_id}
        messages={turn.commentary}
      />
    ) : (
      <>
        <ReasoningSummaries
          key={`${jobFileId}:${turn.execution_id}:${turn.status}`}
          jobFileId={jobFileId}
          executionId={turn.execution_id}
          terminal={isTerminalTurn(turn.status)}
        />
        <PublicTurnMessages messages={turn.commentary} terminal={isTerminalTurn(turn.status)} />
      </>
    );
  return (
    <>
      <EmployeeInput turn={turn} />
      <div role="group" aria-label="職務顧問" className="msg msg--consultant msg--work">
        <p className="msg-meta">
          <SpeakerAvatar speaker="consultant" />
          <span className="msg-name">職務顧問</span>
        </p>
        {work}
      </div>
    </>
  );
}

function EmployeeInput({ turn }: { turn: ConsultantTurn }) {
  if (turn.status === 'cancelled') {
    return (
      <div className="msg msg--employee msg--pending">
        <details>
          <summary>查看原輸入</summary>
          <p style={{ whiteSpace: 'pre-wrap' }}>{turn.input_text}</p>
        </details>
      </div>
    );
  }
  return (
    <div className="msg msg--employee msg--pending">
      <p className="msg-meta">
        <SpeakerAvatar speaker="employee" />
        本次原輸入（尚非正式訪談）
      </p>
      <p className="interview-text">{turn.input_text}</p>
    </div>
  );
}
