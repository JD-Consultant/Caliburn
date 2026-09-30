/** The Turn this tab tracks, read-only. The composer owns starting, recovering and polling it. */
import { useSyncExternalStore } from 'react';
import { useQuery } from '@tanstack/react-query';
import type { ConsultantTurn } from '../../shared/api/generated/consultant-turn';
import {
  consultantTurnByCommandQuery,
  consultantTurnQuery,
  currentConsultantTurnQuery,
  readTurnHintSnapshot,
  subscribeTurnHint,
} from './interview-turn-api';

export interface CurrentTurnView {
  turn: ConsultantTurn | null;
  /** False is unknown, not idle. Keep JD read-only until the composer has verified its state. */
  isVerified: boolean;
}

export function useCurrentTurn(jobFileId: string): CurrentTurnView {
  const hint = useSyncExternalStore(subscribeTurnHint, () => readTurnHintSnapshot(jobFileId));
  const discovery = useQuery({ ...currentConsultantTurnQuery(jobFileId), enabled: false });
  const recovery = useQuery({
    ...consultantTurnByCommandQuery(jobFileId, hint && !hint.execution_id ? hint.command_id : null),
    enabled: false,
  });
  const executionId = hint
    ? (hint.execution_id ?? recovery.data?.execution_id ?? null)
    : (discovery.data?.turn?.execution_id ?? null);
  const turn = useQuery({
    ...consultantTurnQuery(jobFileId, executionId),
    // Only the composer fetches; these observers neither start requests nor install another poller.
    enabled: false,
    refetchInterval: false,
  });
  return {
    turn: turn.isError ? null : (turn.data ?? null),
    isVerified: executionId
      ? turn.isSuccess
      : !hint && discovery.isSuccess && !discovery.isFetching && discovery.data.turn === null,
  };
}
