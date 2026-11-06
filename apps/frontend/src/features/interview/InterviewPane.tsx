import { useState, type ReactNode } from 'react';
import { useQuery, type UseQueryResult } from '@tanstack/react-query';
import { Alert, Box, Button, Typography } from '@mui/material';
import type { TurnView } from '../../shared/api/generated/types.gen';
import { ChatMarkdown } from '../../shared/ui/ChatMarkdown';
import { useStickToBottom } from '../../shared/ui/use-stick-to-bottom';
import { interviewError } from './api';
import { messagesOptions, stepsOptions } from './queries';
import { readPendingCancellation } from './submission';
import { InterviewComposer } from './InterviewComposer';
import { InterviewPlan } from './InterviewPlan';
import { ActiveTurn } from './ActiveTurn';
import { TurnDetails } from './TurnDetails';
import './interview.css';

interface InterviewPaneProps {
  workspaceId: string;
  intervieweeName: string;
  turnsQuery: UseQueryResult<TurnView[], Error>;
  onWorkspaceChanged: () => void;
  renderTurnChanges: (turn: TurnView) => ReactNode;
}
export function InterviewPane(props: InterviewPaneProps) {
  return <WorkspaceInterview key={props.workspaceId} {...props} />;
}

function WorkspaceInterview({
  workspaceId,
  intervieweeName,
  turnsQuery,
  onWorkspaceChanged,
  renderTurnChanges,
}: InterviewPaneProps) {
  const { ref: scrollRef, away, scrollToBottom } = useStickToBottom<HTMLDivElement>();
  const [cancellation, setCancellation] = useState(() =>
    readPendingCancellation(workspaceId),
  );
  const cancelling = cancellation.turnId;
  const messages = useQuery({
    ...messagesOptions(workspaceId),
    enabled: cancelling === null,
  });
  const active = turnsQuery.data?.findLast((turn) => turn.status !== 'completed');
  const activeId = cancelling ?? active?.turn_id;
  const unavailable =
    cancellation.error !== null ||
    turnsQuery.isPending ||
    turnsQuery.isError ||
    turnsQuery.isFetching;
  return (
    <Box className="interview-pane" aria-label="訪談工作區">
      <div className="interview-scroll" ref={scrollRef}>
        <div>
          <InterviewPlan workspaceId={workspaceId} />
          <Typography component="h2" className="interview-heading" variant="subtitle2">
            歷史訪談
          </Typography>
          {cancellation.error && <Alert severity="warning">{cancellation.error}</Alert>}
          {messages.isPending && cancelling === null && (
            <p role="status">正在讀取訪談…</p>
          )}
          {messages.isError && (
            <Alert
              severity="error"
              action={
                <Button
                  onClick={() => {
                    void messages.refetch();
                  }}
                >
                  重新讀取訪談
                </Button>
              }
            >
              {interviewError(messages.error)}
            </Alert>
          )}
          {turnsQuery.isError && (
            <Alert
              severity="warning"
              action={
                <Button
                  onClick={() => {
                    void turnsQuery.refetch();
                  }}
                >
                  重新讀取輪次
                </Button>
              }
            >
              {interviewError(turnsQuery.error)}
            </Alert>
          )}
          <ol className="interview-history">
            {messages.data?.map((message) => (
              <li key={message.message_id} className={`msg msg--${message.speaker}`}>
                <h3 className="msg-meta">
                  <span className="msg-name">
                    {message.speaker === 'app'
                      ? '開場引導'
                      : message.speaker === 'employee'
                        ? intervieweeName
                        : '職務顧問'}
                  </span>
                </h3>
                {message.speaker === 'consultant' ? (
                  <ChatMarkdown className="interview-text md" markdown={message.text} />
                ) : (
                  <p className="interview-text">{message.text}</p>
                )}
              </li>
            ))}
          </ol>
          {turnsQuery.data
            ?.filter((turn) => turn.status === 'completed')
            .map((turn) => (
              <CompletedTurn
                key={turn.turn_id}
                workspaceId={workspaceId}
                turn={turn}
                renderTurnChanges={renderTurnChanges}
              />
            ))}
          {activeId && (
            <ActiveTurn
              key={activeId}
              workspaceId={workspaceId}
              turnId={activeId}
              cancellationPending={cancelling !== null}
              controlsDisabled={cancellation.error !== null}
              onCancellationPending={() =>
                setCancellation({ turnId: activeId, error: null })
              }
              onCancelled={() => setCancellation({ turnId: null, error: null })}
              onWorkspaceChanged={onWorkspaceChanged}
            />
          )}
        </div>
      </div>
      {away && (
        <Button size="small" onClick={scrollToBottom}>
          回到最新訊息
        </Button>
      )}
      <InterviewComposer
        workspaceId={workspaceId}
        disabled={unavailable || activeId !== undefined}
        controlsDisabled={cancellation.error !== null}
        onWorkspaceChanged={onWorkspaceChanged}
      />
    </Box>
  );
}

function CompletedTurn({
  workspaceId,
  turn,
  renderTurnChanges,
}: {
  workspaceId: string;
  turn: TurnView;
  renderTurnChanges: (turn: TurnView) => ReactNode;
}) {
  const [open, setOpen] = useState(false);
  const steps = useQuery({ ...stepsOptions(workspaceId, turn.turn_id), enabled: open });
  return (
    <Box
      component="details"
      sx={{ mx: 2, my: 1 }}
      onToggle={(event) => setOpen(event.currentTarget.open)}
    >
      <summary>
        已完成處理紀錄 · {new Date(turn.created_at).toLocaleString('zh-TW')}
      </summary>
      {open && (
        <>
          {steps.isPending && <p role="status">正在讀取處理紀錄…</p>}
          {steps.isError && (
            <Alert
              severity="error"
              action={
                <Button
                  onClick={() => {
                    void steps.refetch();
                  }}
                >
                  重新讀取步驟
                </Button>
              }
            >
              {interviewError(steps.error)}
            </Alert>
          )}
          <TurnDetails turn={turn} steps={steps.data ?? []} />
          {renderTurnChanges(turn)}
        </>
      )}
    </Box>
  );
}
