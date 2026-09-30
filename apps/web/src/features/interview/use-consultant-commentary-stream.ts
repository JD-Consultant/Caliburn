/** One active Turn's disposable public display; never submits input or controls execution. */
import { useEffect, useState } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import type { CommentaryUpdate } from '../../shared/api/generated/commentary-update';
import { isCommentaryUpdate } from '../../shared/api/validation';
import { consultantTurnQuery } from './interview-turn-api';

export function useConsultantCommentaryStream(jobFileId: string, executionId: string) {
  const queryClient = useQueryClient();
  const [messages, setMessages] = useState<CommentaryUpdate[]>([]);
  const [disconnected, setDisconnected] = useState(false);
  const supported = typeof EventSource !== 'undefined';

  useEffect(() => {
    if (!supported) return;
    let disposed = false;
    const source = new EventSource(
      `/api/job-files/${encodeURIComponent(jobFileId)}/consultant-turns/${encodeURIComponent(executionId)}/commentary-stream`,
    );
    const reconcile = () => {
      void queryClient.invalidateQueries({
        queryKey: consultantTurnQuery(jobFileId, executionId).queryKey,
        exact: true,
      });
    };
    const onOpen = () => {
      if (disposed) return;
      // Reconnection is not a replay guarantee. Saved status supplies durable history;
      // subsequent cumulative updates provide the new live baseline.
      setMessages([]);
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
    source.addEventListener('open', onOpen);
    source.addEventListener('error', onError);
    source.addEventListener('commentary', onCommentary);
    return () => {
      disposed = true;
      source.removeEventListener('open', onOpen);
      source.removeEventListener('error', onError);
      source.removeEventListener('commentary', onCommentary);
      source.close();
    };
  }, [jobFileId, executionId, queryClient, supported]);

  return { messages, disconnected: disconnected || !supported };
}
