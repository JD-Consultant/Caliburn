/** One active Turn's disposable public display; never submits input or controls execution. */
import { useEffect, useState } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import type { CommentaryUpdate } from '../../shared/api/generated/commentary-update';
import type { ReasoningSummary } from '../../shared/api/generated/reasoning-summary';
import { isCommentaryUpdate, isReasoningSummary } from '../../shared/api/validation';
import { consultantTurnQuery } from './interview-turn-api';
import { reasoningSummariesQuery, summaryKey } from './reasoning-summary-api';

export function useConsultantActivityStream(jobFileId: string, executionId: string) {
  const queryClient = useQueryClient();
  const [messages, setMessages] = useState<CommentaryUpdate[]>([]);
  const [summaries, setSummaries] = useState<ReasoningSummary[]>([]);
  const [disconnected, setDisconnected] = useState(false);
  const supported = typeof EventSource !== 'undefined';

  useEffect(() => {
    if (!supported) return;
    let disposed = false;
    const source = new EventSource(
      `/api/job-files/${encodeURIComponent(jobFileId)}/consultant-turns/${encodeURIComponent(executionId)}/activity-stream`,
    );
    const reconcile = () => {
      void queryClient.invalidateQueries({
        queryKey: consultantTurnQuery(jobFileId, executionId).queryKey,
        exact: true,
      });
      const summariesQuery = {
        queryKey: reasoningSummariesQuery(jobFileId, executionId).queryKey,
        exact: true,
      };
      // Invalidation can reuse an initial GET that has no data yet. Cancel it first
      // so a pre-reconnect empty snapshot cannot hide a newly saved summary.
      void queryClient.cancelQueries(summariesQuery).then(() => {
        if (!disposed) return queryClient.invalidateQueries(summariesQuery);
      });
    };
    const onOpen = () => {
      if (disposed) return;
      // Reconnection is not a replay guarantee. Saved status supplies durable history;
      // subsequent cumulative updates provide the new live baseline.
      setMessages([]);
      setSummaries([]);
      setDisconnected(false);
      reconcile();
    };
    const onError = () => {
      if (disposed) return;
      setDisconnected(true);
      reconcile();
      // Native EventSource owns reconnection. CLOSED is not a product terminal status.
    };
    const onCommentary = (event: MessageEvent) => {
      if (disposed || typeof event.data !== 'string') return;
      let value: unknown;
      try {
        value = JSON.parse(event.data);
      } catch {
        return;
      }
      if (
        !isCommentaryUpdate(value) ||
        value.job_file_id !== jobFileId ||
        value.execution_id !== executionId
      )
        return;
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
      if (disposed || typeof event.data !== 'string') return;
      let value: unknown;
      try {
        value = JSON.parse(event.data);
      } catch {
        return;
      }
      // This payload is scoped by the authenticated URL/subscription, not model-supplied IDs.
      if (!isReasoningSummary(value)) return;
      const summary = value;
      setSummaries((current) => {
        const key = summaryKey(summary);
        const index = current.findIndex((item) => summaryKey(item) === key);
        if (index < 0) return [...current, summary];
        if (current[index]?.text === summary.text) return current;
        return current.map((item, position) => (position === index ? summary : item));
      });
    };
    source.addEventListener('open', onOpen);
    source.addEventListener('error', onError);
    source.addEventListener('commentary', onCommentary);
    source.addEventListener('reasoning_summary', onSummary);
    return () => {
      disposed = true;
      source.removeEventListener('open', onOpen);
      source.removeEventListener('error', onError);
      source.removeEventListener('commentary', onCommentary);
      source.removeEventListener('reasoning_summary', onSummary);
      source.close();
    };
  }, [jobFileId, executionId, queryClient, supported]);

  return { messages, summaries, disconnected: disconnected || !supported };
}
