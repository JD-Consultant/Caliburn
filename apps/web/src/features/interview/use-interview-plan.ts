/** Candidate selection is derived at render; only a successful terminal GET confirms refresh. */
import { useEffect, useLayoutEffect, useRef, useState } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { interviewPlanQuery, refreshTerminalInterviewPlan } from './interview-plan-api';
import { isTerminalTurn } from './interview-turn-api';
import { useCurrentTurn } from './use-current-turn';

interface RefreshIdentity {
  jobFileId: string;
  executionId: string;
}

interface RefreshFailure extends RefreshIdentity {
  error: unknown;
}

export interface InterviewPlanState {
  plan: string | null | undefined;
  source: 'candidate' | 'adopted' | 'previous';
  isLoading: boolean;
  error: unknown;
  retry: () => void;
}

export function useInterviewPlan(jobFileId: string): InterviewPlanState {
  const current = useCurrentTurn(jobFileId);
  const turn = current.isVerified && current.turn?.job_file_id === jobFileId ? current.turn : null;
  const terminalId = turn && isTerminalTurn(turn.status) ? turn.execution_id : null;
  const preview =
    turn && (turn.status === 'active' || turn.status === 'paused') ? turn.plan_preview : null;
  const queryClient = useQueryClient();
  const query = useQuery({ ...interviewPlanQuery(jobFileId), enabled: terminalId === null });
  const [confirmed, setConfirmed] = useState<RefreshIdentity | null>(null);
  const [failure, setFailure] = useState<RefreshFailure | null>(null);
  const [retryAttempt, setRetryAttempt] = useState(0);
  const observed = useRef<RefreshIdentity | null>(null);

  useLayoutEffect(() => {
    observed.current = terminalId ? { jobFileId, executionId: terminalId } : null;
    return () => {
      observed.current = null;
    };
  }, [jobFileId, terminalId]);

  useEffect(() => {
    if (!terminalId) return;
    let disposed = false;
    const stillObserved = () =>
      !disposed &&
      observed.current?.jobFileId === jobFileId &&
      observed.current.executionId === terminalId;
    void refreshTerminalInterviewPlan(queryClient, jobFileId, terminalId).then(
      () => {
        if (stillObserved()) {
          setConfirmed({ jobFileId, executionId: terminalId });
          setFailure(null);
        }
      },
      (error: unknown) => {
        if (stillObserved()) setFailure({ jobFileId, executionId: terminalId, error });
      },
    );
    return () => {
      disposed = true;
    };
  }, [jobFileId, terminalId, queryClient, retryAttempt]);

  const awaitingRefresh =
    terminalId !== null &&
    (confirmed?.jobFileId !== jobFileId || confirmed.executionId !== terminalId);
  const refreshError =
    failure?.jobFileId === jobFileId && failure.executionId === terminalId ? failure.error : null;
  return {
    plan: preview ? preview.plan : query.data?.plan,
    source: preview ? 'candidate' : awaitingRefresh ? 'previous' : 'adopted',
    isLoading: preview === null && (awaitingRefresh ? !refreshError : query.isPending),
    error: preview ? null : awaitingRefresh ? refreshError : query.error,
    retry: () => {
      if (terminalId) {
        setFailure(null);
        setRetryAttempt((attempt) => attempt + 1);
      } else {
        void query.refetch();
      }
    },
  };
}
