import { queryOptions, useQuery } from '@tanstack/react-query';
import {
  getPlan,
  getTurn,
  listMessages,
  listQuestions,
  listSteps,
  listTurns,
} from './api';
import {
  readPendingCancellation,
  readPendingSubmission,
  UnconfirmedSubmission,
} from './submission';

export const interviewKeys = {
  all: (workspaceId: string) =>
    ['workspace', workspaceId.toLowerCase(), 'interview'] as const,
  turns: (workspaceId: string) => [...interviewKeys.all(workspaceId), 'turns'] as const,
  turn: (workspaceId: string, turnId: string) =>
    [...interviewKeys.all(workspaceId), 'turn', turnId.toLowerCase()] as const,
  messages: (workspaceId: string) =>
    [...interviewKeys.all(workspaceId), 'messages'] as const,
  plan: (workspaceId: string) => [...interviewKeys.all(workspaceId), 'plan'] as const,
};
export function turnsOptions(workspaceId: string) {
  return queryOptions({
    queryKey: interviewKeys.turns(workspaceId),
    queryFn: async ({ signal }) => {
      const turns = await listTurns(workspaceId, signal);
      const pending = readPendingSubmission(workspaceId);
      // A must keep the JD read-only while an original submission is unconfirmed.
      if (pending && !turns.some((turn) => turn.turn_id === pending.turn_id))
        throw new UnconfirmedSubmission();
      const cancellation = readPendingCancellation(workspaceId);
      if (cancellation.error) throw new Error(cancellation.error);
      if (cancellation.turnId) throw new Error('取消尚未確認完成。');
      return turns;
    },
    retry: false,
  });
}
export function useAgentTurns(workspaceId: string) {
  return useQuery(turnsOptions(workspaceId));
}
export function turnOptions(workspaceId: string, turnId: string) {
  return queryOptions({
    queryKey: interviewKeys.turn(workspaceId, turnId),
    queryFn: ({ signal }) => getTurn(workspaceId, turnId, signal),
    retry: false,
  });
}
export function messagesOptions(workspaceId: string) {
  return queryOptions({
    queryKey: interviewKeys.messages(workspaceId),
    queryFn: ({ signal }) => listMessages(workspaceId, signal),
  });
}
export function planOptions(workspaceId: string) {
  return queryOptions({
    queryKey: interviewKeys.plan(workspaceId),
    queryFn: ({ signal }) => getPlan(workspaceId, signal),
  });
}
export function stepsOptions(workspaceId: string, turnId: string) {
  return queryOptions({
    queryKey: [...interviewKeys.turn(workspaceId, turnId), 'steps'],
    queryFn: ({ signal }) => listSteps(workspaceId, turnId, signal),
    retry: false,
  });
}
export function questionsOptions(workspaceId: string, turnId: string) {
  return queryOptions({
    queryKey: [...interviewKeys.turn(workspaceId, turnId), 'questions'],
    queryFn: ({ signal }) => listQuestions(workspaceId, turnId, signal),
    retry: false,
  });
}
