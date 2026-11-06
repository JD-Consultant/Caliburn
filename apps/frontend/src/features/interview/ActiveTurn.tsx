import { useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Alert, Box, Button, Stack, Typography } from '@mui/material';
import type { AnswerTurnRequest, TurnView } from '../../shared/api/generated/types.gen';
import { ChatMarkdown } from '../../shared/ui/ChatMarkdown';
import { HttpError } from '../../shared/api/http';
import { answerTurn, cancelTurn, interviewError, resumeTurn } from './api';
import { interviewKeys, questionsOptions, stepsOptions, turnOptions } from './queries';
import { clearCancellation, clearSubmission, retainCancellation } from './submission';
import { useTurnStream } from './use-turn-stream';
import { QuestionForm } from './QuestionForm';
import { TurnDetails } from './TurnDetails';

export function ActiveTurn({
  workspaceId,
  turnId,
  cancellationPending,
  controlsDisabled = false,
  onCancellationPending,
  onCancelled,
  onWorkspaceChanged,
}: {
  workspaceId: string;
  turnId: string;
  cancellationPending: boolean;
  controlsDisabled?: boolean;
  onCancellationPending: () => void;
  onCancelled: () => void;
  onWorkspaceChanged: () => void;
}) {
  const client = useQueryClient();
  const turn = useQuery({
    ...turnOptions(workspaceId, turnId),
    enabled: !cancellationPending,
  });
  const steps = useQuery({
    ...stepsOptions(workspaceId, turnId),
    enabled: !cancellationPending,
  });
  const questions = useQuery({
    ...questionsOptions(workspaceId, turnId),
    enabled: !cancellationPending,
  });
  const [error, setError] = useState<string | null>(null);
  const stream = useTurnStream(
    workspaceId,
    turnId,
    turn.data?.status === 'running' && !cancellationPending,
    onWorkspaceChanged,
  );
  const control = useMutation({
    mutationFn: async (action: 'resume' | 'cancel') => {
      if (action === 'resume') return resumeTurn(workspaceId, turnId);
      retainCancellation(workspaceId, turnId);
      onCancellationPending();
      await client.cancelQueries({ queryKey: interviewKeys.all(workspaceId) });
      await cancelTurn(workspaceId, turnId);
      return null;
    },
    onSuccess: async (result) => {
      if (result === null) {
        clearCancellation(workspaceId);
        clearSubmission(workspaceId);
        await client.cancelQueries({ queryKey: interviewKeys.all(workspaceId) });
        client.removeQueries({ queryKey: interviewKeys.turn(workspaceId, turnId) });
        client.setQueryData<TurnView[]>(interviewKeys.turns(workspaceId), (turns) =>
          turns?.filter((item) => item.turn_id !== turnId),
        );
        client.removeQueries({ queryKey: interviewKeys.messages(workspaceId) });
      } else if (client.getQueryState(interviewKeys.turns(workspaceId))) {
        client.setQueryData(interviewKeys.turn(workspaceId, turnId), result);
      }
      onWorkspaceChanged();
    },
  });
  const answers = useMutation({
    mutationFn: (body: AnswerTurnRequest) => answerTurn(workspaceId, turnId, body),
    onSuccess: (result) => {
      if (client.getQueryState(interviewKeys.turns(workspaceId))) {
        client.setQueryData(interviewKeys.turn(workspaceId, turnId), result);
      }
      void client.invalidateQueries({
        queryKey: interviewKeys.turn(workspaceId, turnId),
      });
      onWorkspaceChanged();
    },
    onError: () => {
      // An answer can be saved even when its acknowledgement is lost.
      void client.invalidateQueries({
        queryKey: interviewKeys.turn(workspaceId, turnId),
      });
    },
  });
  async function act(action: 'resume' | 'cancel'): Promise<void> {
    setError(null);
    try {
      const result = await control.mutateAsync(action);
      if (result === null) onCancelled();
    } catch (failure) {
      if (action === 'cancel' && failure instanceof HttpError && failure.status === 409) {
        clearCancellation(workspaceId);
        onCancelled();
        onWorkspaceChanged();
      }
      setError(
        action === 'cancel'
          ? `尚未確認取消完成。${interviewError(failure)}`
          : interviewError(failure),
      );
    }
  }
  const waiting =
    questions.data?.filter((exchange) => exchange.status === 'waiting') ?? [];
  return (
    <Box component="section" aria-label="本輪處理" sx={{ px: 2, py: 1 }}>
      <Typography variant="subtitle2">職務顧問</Typography>
      <p role="status">
        {cancellationPending
          ? '取消尚未確認完成，可接續同一取消請求。'
          : turn.data?.status === 'waiting_for_input'
            ? '請回答下方問題。'
            : turn.data?.status === 'interrupted'
              ? '處理已中斷，可恢復同一輪。'
              : turn.data?.status === 'completed'
                ? '本輪已完成。'
                : '正在處理…'}
      </p>
      {(error || turn.isError || steps.isError || questions.isError) && (
        <Alert severity="warning">
          {error ?? interviewError(turn.error ?? steps.error ?? questions.error)}
        </Alert>
      )}
      {stream.notice && <Alert severity="info">{stream.notice}</Alert>}
      {stream.output && (
        <Box aria-label="即時處理片段">
          <Typography variant="caption">即時片段，保存結果以處理紀錄為準</Typography>
          {stream.output.reasoning && (
            <details>
              <summary>推理摘要</summary>
              <p style={{ whiteSpace: 'pre-wrap' }}>{stream.output.reasoning}</p>
            </details>
          )}
          <ChatMarkdown markdown={stream.output.text} />
          {stream.output.tools.map((tool) => (
            <Box component="details" key={tool.call_id}>
              <summary>{tool.name}</summary>
              <Typography variant="caption">
                即時工具呼叫；保存結果請查處理紀錄。
              </Typography>
              <Box
                component="pre"
                sx={{ whiteSpace: 'pre-wrap', overflowWrap: 'anywhere' }}
              >
                {tool.arguments}
              </Box>
            </Box>
          ))}
        </Box>
      )}
      {!cancellationPending &&
        waiting.map((exchange) => (
          <QuestionForm
            key={`${exchange.model_step}:${exchange.call_id}`}
            exchange={exchange}
            disabled={
              controlsDisabled ||
              control.isPending ||
              answers.isPending ||
              questions.isFetching
            }
            onSubmit={async (body) => {
              await answers.mutateAsync(body);
            }}
          />
        ))}
      {turn.data && <TurnDetails turn={turn.data} steps={steps.data ?? []} />}
      <Stack direction="row" useFlexGap spacing={1} sx={{ flexWrap: 'wrap', my: 1 }}>
        <Button
          disabled={cancellationPending}
          onClick={() => {
            void Promise.all([turn.refetch(), steps.refetch(), questions.refetch()]).then(
              onWorkspaceChanged,
            );
          }}
        >
          重新讀取處理
        </Button>
        {!cancellationPending && turn.data?.status === 'running' && (
          <Button onClick={stream.reconnect}>重新連線</Button>
        )}
        {!cancellationPending &&
          turn.data?.status === 'interrupted' &&
          waiting.length === 0 &&
          !questions.isError && (
            <Button
              disabled={controlsDisabled || control.isPending || questions.isPending}
              onClick={() => {
                void act('resume');
              }}
            >
              恢復本輪
            </Button>
          )}
        {(turn.data?.status !== 'completed' || cancellationPending) && (
          <Button
            color="error"
            disabled={controlsDisabled || control.isPending || answers.isPending}
            onClick={() => {
              void act('cancel');
            }}
          >
            {cancellationPending ? '重新確認取消' : '取消本輪'}
          </Button>
        )}
      </Stack>
    </Box>
  );
}
