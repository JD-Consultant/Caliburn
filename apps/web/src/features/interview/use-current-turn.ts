/** The Turn this tab tracks, read-only. The composer owns starting, recovering and polling it. */
import { useSyncExternalStore } from 'react';
import { useQuery } from '@tanstack/react-query';
import type { ConsultantTurn } from '../../shared/api/generated/consultant-turn';
import { consultantTurnQuery, readTurnHintSnapshot, subscribeTurnHint } from './interview-turn-api';

export function useCurrentTurn(jobFileId: string): ConsultantTurn | null {
  const hint = useSyncExternalStore(subscribeTurnHint, () => readTurnHintSnapshot(jobFileId));
  const turn = useQuery({
    ...consultantTurnQuery(jobFileId, hint?.execution_id ?? null),
    // The composer polls this same cache entry; a second poller would double the requests.
    refetchInterval: false,
    refetchOnMount: false,
  });
  return turn.isError ? null : (turn.data ?? null);
}
