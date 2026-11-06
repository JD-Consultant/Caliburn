import { useEffect, useState } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import type { TurnView } from '../../shared/api/generated/types.gen';
import { streamTurnEvents } from '../../shared/api/sse';
import { requireTurnScope, turnPath } from './api';
import { interviewKeys, questionsOptions, stepsOptions, turnOptions } from './queries';
import { appendDelta, type StreamOutput } from './stream-output';

/** One connection owns its transient deltas. Recovery reads saved projections before reconnecting. */
export function useTurnStream(
  workspaceId: string,
  turnId: string,
  running: boolean,
  onWorkspaceChanged: () => void,
) {
  const client = useQueryClient();
  const [output, setOutput] = useState<StreamOutput | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [connection, reconnect] = useState(0);
  useEffect(() => {
    if (!running) return;
    const controller = new AbortController();
    let cancellation = false;
    async function resync(): Promise<TurnView> {
      const [turn] = await Promise.all([
        client.fetchQuery({ ...turnOptions(workspaceId, turnId), staleTime: 0 }),
        client.fetchQuery({ ...stepsOptions(workspaceId, turnId), staleTime: 0 }),
        client.fetchQuery({ ...questionsOptions(workspaceId, turnId), staleTime: 0 }),
      ]);
      client.setQueryData<TurnView[]>(interviewKeys.turns(workspaceId), (turns) =>
        turns?.map((item) => (item.turn_id === turnId ? turn : item)),
      );
      onWorkspaceChanged();
      return turn;
    }
    async function refreshSaved(): Promise<void> {
      setOutput(null);
      try {
        const saved = await resync();
        setNotice(
          saved.status === 'running'
            ? '連線已結束，已查回保存內容。可重新連線查看後續處理。'
            : null,
        );
      } catch {
        setNotice('連線中斷且尚未查回狀態。請重新讀取；不會自動重跑模型。');
      }
    }
    async function subscribe(): Promise<void> {
      try {
        if (connection > 0) {
          const saved = await resync();
          if (controller.signal.aborted || saved.status !== 'running') return;
        }
        await streamTurnEvents(`${turnPath(workspaceId, turnId)}/events`, {
          signal: controller.signal,
          onEvent: (event) => {
            if (controller.signal.aborted) return;
            if (event.event === 'status') {
              requireTurnScope(event.data, workspaceId, turnId);
              if (event.data.status === 'running')
                client.setQueryData(interviewKeys.turn(workspaceId, turnId), event.data);
              else {
                controller.abort();
                void refreshSaved();
              }
            } else if (event.event === 'cancellation') {
              if (event.data.turn_id !== turnId) return;
              cancellation = true;
              setNotice('取消正在收尾或已處理，請按取消確認結果。');
              setOutput(null);
            } else if (event.event === 'resync_required') {
              controller.abort();
              void refreshSaved();
            } else {
              setOutput((current) => appendDelta(current, event));
            }
          },
        });
      } catch {
        if (controller.signal.aborted) return;
      }
      if (controller.signal.aborted) return;
      if (!cancellation) await refreshSaved();
    }
    void subscribe();
    return () => controller.abort();
  }, [client, workspaceId, turnId, running, connection, onWorkspaceChanged]);
  return {
    output: running ? output : null,
    notice,
    reconnect: () => {
      setOutput(null);
      setNotice(null);
      reconnect((value) => value + 1);
    },
  };
}
