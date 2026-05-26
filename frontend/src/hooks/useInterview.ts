import { useState, useCallback, useRef } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { getHistory, streamChat } from "@/lib/api";
import type { InterviewMessage } from "@/types";

export function useInterview(profileId: string) {
  const qc = useQueryClient();
  const [streaming, setStreaming] = useState(false);
  const [streamBubbles, setStreamBubbles] = useState<string[]>([]);
  const abortRef = useRef<AbortController | null>(null);

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
      setStreamBubbles([]);

      try {
        const aiBubbles: string[] = [];
        for await (const chunk of streamChat(profileId, content, phase)) {
          if (!chunk.trim()) continue;
          aiBubbles.push(chunk);
          setStreamBubbles([...aiBubbles]);
        }
        // Flush streamed stage messages into history and refresh profile
        setStreamBubbles([]);
        qc.setQueryData<InterviewMessage[]>(["history", profileId], (prev = []) => [
          ...prev,
          ...aiBubbles.map((bubble) => ({ role: "ai" as const, content: bubble })),
        ]);
        await qc.invalidateQueries({ queryKey: ["profile", profileId] });
      } catch (err) {
        console.error("stream error", err);
      } finally {
        setStreaming(false);
        setStreamBubbles([]);
      }
    },
    [profileId, streaming, qc]
  );

  const sendSilent = useCallback(
    (content: string, phase = "general") => send(content, phase, true),
    [send]
  );

  return { messages, isLoading, streaming, streamBubbles, send, sendSilent };
}
