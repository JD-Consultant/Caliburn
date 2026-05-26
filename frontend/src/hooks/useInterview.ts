import { useState, useCallback } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { getHistory, streamChat } from "@/lib/api";
import type { InterviewMessage } from "@/types";

export function useInterview(profileId: string) {
  const qc = useQueryClient();
  const [streaming, setStreaming] = useState(false);
  const [streamMessages, setStreamMessages] = useState<InterviewMessage[]>([]);

  const { data: messages = [], isLoading } = useQuery({
    queryKey: ["history", profileId],
    queryFn: () => getHistory(profileId),
  });

  const send = useCallback(
    async (content: string, phase = "general", silent = false) => {
      if (streaming) return;

      if (!silent) {
        const optimistic: InterviewMessage = { role: "user", content };
        qc.setQueryData<InterviewMessage[]>(["history", profileId], (prev = []) => [
          ...prev,
          optimistic,
        ]);
      }

      setStreaming(true);
      setStreamMessages([]);

      try {
        const aiMessages: InterviewMessage[] = [];
        for await (const event of streamChat(profileId, content, phase)) {
          if (!event.content.trim()) continue;
          aiMessages.push({
            role: "ai",
            content: event.content,
            phase: event.phase,
            extra_data: {
              kind: event.kind,
              stage: event.stage,
              node: event.node,
            },
          });
          setStreamMessages([...aiMessages]);
        }
        // Flush streamed stage messages into history and refresh profile
        setStreamMessages([]);
        qc.setQueryData<InterviewMessage[]>(["history", profileId], (prev = []) => [
          ...prev,
          ...aiMessages,
        ]);
        await qc.invalidateQueries({ queryKey: ["profile", profileId] });
      } catch (err) {
        console.error("stream error", err);
      } finally {
        setStreaming(false);
        setStreamMessages([]);
      }
    },
    [profileId, streaming, qc]
  );

  const sendSilent = useCallback(
    (content: string, phase = "general") => send(content, phase, true),
    [send]
  );

  return { messages, isLoading, streaming, streamMessages, send, sendSilent };
}
