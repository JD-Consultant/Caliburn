/** One active Turn's disposable public display; never submits input or controls execution. */
import { useEffect, useState } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import type { CommentaryUpdate } from '../../shared/api/generated/commentary-update';
import type { ReasoningSummary } from '../../shared/api/generated/reasoning-summary';
import {
  isCommentaryUpdate,
  isReasoningSummary,
  isConsultantTurn,
} from '../../shared/api/validation';
import { ApiError } from '../../shared/api/http';
import { consultantTurnQuery, subscribeInterviewDeletion } from './interview-turn-api';
import { reasoningSummariesQuery, summaryKey } from './reasoning-summary-api';
import { refreshQueries } from '../../shared/api/refresh-queries';
import { reportDiagnostic } from '../../shared/diagnostics';

interface ActivityStream {
  messages: CommentaryUpdate[];
  summaries: ReasoningSummary[];
  disconnected: boolean;
}

export function useConsultantActivityStream(
  jobFileId: string,
  executionId: string,
): ActivityStream {
  const queryClient = useQueryClient();
  const [messages, setMessages] = useState<CommentaryUpdate[]>([]);
  const [summaries, setSummaries] = useState<ReasoningSummary[]>([]);
  const [disconnected, setDisconnected] = useState(false);
  const supported = typeof EventSource !== 'undefined';

  useEffect(() => {
    if (!supported) return;
    let disposed = false;
    let stopped = false;
    let source: EventSource | null = null;
    let timer: ReturnType<typeof setTimeout> | undefined;
    let stableTimer: ReturnType<typeof setTimeout> | undefined;
    let retries = 0;
    const recovery = new AbortController();
    const turnQuery = consultantTurnQuery(jobFileId, executionId);
    const detach = () => {
      if (!source) return;
      source.removeEventListener('open', onOpen);
      source.removeEventListener('error', onError);
      source.removeEventListener('commentary', onCommentary);
      source.removeEventListener('reasoning_summary', onSummary);
      source.close();
      source = null;
    };
    const stop = () => {
      stopped = true;
      clearTimeout(timer);
      clearTimeout(stableTimer);
      recovery.abort();
      detach();
    };
    const finish = () => {
      if (stopped) return;
      stop();
      void refreshQueries(queryClient, [
        { queryKey: reasoningSummariesQuery(jobFileId, executionId).queryKey, exact: true },
      ]).catch(() =>
        reportDiagnostic({ event: 'stream_failure', kind: 'refresh', jobFileId, executionId }),
      );
    };
    const schedule = (action: () => void) => {
      if (disposed || stopped || retries >= 3) return;
      const delay = 1_000 * 2 ** retries++;
      timer = setTimeout(() => {
        timer = undefined;
        if (!disposed && !stopped) action();
      }, delay);
    };
    const recover = async () => {
      try {
        const queryFn = turnQuery.queryFn;
        if (typeof queryFn !== 'function') return;
        const turn = await queryClient.query({
          ...turnQuery,
          // Only a GET started by this owner borrows its abort signal. An existing
          // QueryClient request is deduplicated and remains its caller's responsibility.
          queryFn: (context) =>
            queryFn({
              ...context,
              signal:
                disposed || stopped
                  ? context.signal
                  : AbortSignal.any([context.signal, recovery.signal]),
            }),
        });
        if (disposed || stopped) return;
        if (turn.status !== 'active') {
          finish();
          return;
        }
        schedule(connect);
      } catch (error) {
        if (disposed || stopped) return;
        if (error instanceof ApiError && error.status === 404) {
          finish();
          return;
        }
        // Unknown is not a product state. Spend the same finite recovery budget.
        schedule(() => {
          void recover();
        });
      }
    };
    const reconcile = () => {
      void refreshQueries(queryClient, [
        { queryKey: consultantTurnQuery(jobFileId, executionId).queryKey, exact: true },
        { queryKey: reasoningSummariesQuery(jobFileId, executionId).queryKey, exact: true },
      ]).catch(() =>
        reportDiagnostic({ event: 'stream_failure', kind: 'refresh', jobFileId, executionId }),
      );
    };
    const onOpen = () => {
      if (disposed || stopped) return;
      clearTimeout(stableTimer);
      // Brief OPEN/CLOSED loops must not renew the budget indefinitely.
      stableTimer = setTimeout(() => {
        retries = 0;
      }, 10_000);
      // Reconnection is not a replay guarantee. Saved status supplies durable history;
      // subsequent cumulative updates provide the new live baseline.
      setMessages([]);
      setSummaries([]);
      setDisconnected(false);
      reconcile();
    };
    const onError = () => {
      if (disposed || stopped || !source) return;
      clearTimeout(stableTimer);
      setDisconnected(true);
      reportDiagnostic({
        event: 'stream_failure',
        kind: 'stream_disconnected',
        jobFileId,
        executionId,
      });
      if (source.readyState === EventSource.CLOSED) {
        detach();
        void recover();
      } else {
        // CONNECTING retains the native parser and reconnection owner.
        reconcile();
      }
    };
    const onCommentary = (event: MessageEvent) => {
      if (disposed || stopped || typeof event.data !== 'string') return;
      let value: unknown;
      try {
        value = JSON.parse(event.data);
      } catch {
        reportDiagnostic({ event: 'stream_failure', kind: 'invalid_json', jobFileId, executionId });
        return;
      }
      if (
        !isCommentaryUpdate(value) ||
        value.job_file_id !== jobFileId ||
        value.execution_id !== executionId
      ) {
        reportDiagnostic({
          event: 'stream_failure',
          kind: 'invalid_response',
          jobFileId,
          executionId,
        });
        return;
      }
      setMessages((current) => {
        const index = current.findIndex(
          (item) => item.response_id === value.response_id && item.message_id === value.message_id,
        );
        if (index < 0) return [...current, value];
        if (current[index]?.text === value.text) return current;
        return current.map((item, position) => (position === index ? value : item));
      });
    };
    const onSummary = (event: MessageEvent) => {
      if (disposed || stopped || typeof event.data !== 'string') return;
      let value: unknown;
      try {
        value = JSON.parse(event.data);
      } catch {
        reportDiagnostic({ event: 'stream_failure', kind: 'invalid_json', jobFileId, executionId });
        return;
      }
      // This payload is scoped by the authenticated URL/subscription, not model-supplied IDs.
      if (!isReasoningSummary(value)) {
        reportDiagnostic({
          event: 'stream_failure',
          kind: 'invalid_response',
          jobFileId,
          executionId,
        });
        return;
      }
      const summary = value;
      setSummaries((current) => {
        const key = summaryKey(summary);
        const index = current.findIndex((item) => summaryKey(item) === key);
        if (index < 0) return [...current, summary];
        if (current[index]?.text === summary.text) return current;
        return current.map((item, position) => (position === index ? summary : item));
      });
    };
    function connect() {
      if (disposed || stopped) return;
      source = new EventSource(
        `/api/job-files/${encodeURIComponent(jobFileId)}/consultant-turns/${encodeURIComponent(executionId)}/activity-stream`,
      );
      source.addEventListener('open', onOpen);
      source.addEventListener('error', onError);
      source.addEventListener('commentary', onCommentary);
      source.addEventListener('reasoning_summary', onSummary);
    }
    const unsubscribe = queryClient.getQueryCache().subscribe((event) => {
      if (event.type !== 'updated' || event.action.type !== 'success') return;
      const data: unknown = event.query.state.data;
      const key: unknown = event.query.queryKey;
      if (
        Array.isArray(key) &&
        key[0] === 'consultant-turn' &&
        isConsultantTurn(data) &&
        data.job_file_id === jobFileId &&
        data.execution_id === executionId &&
        data.status !== 'active'
      )
        finish();
    });
    const unsubscribeDeletion = subscribeInterviewDeletion(jobFileId, stop);
    connect();
    return () => {
      disposed = true;
      unsubscribe();
      unsubscribeDeletion();
      stop();
    };
  }, [jobFileId, executionId, queryClient, supported]);

  return { messages, summaries, disconnected: disconnected || !supported };
}
