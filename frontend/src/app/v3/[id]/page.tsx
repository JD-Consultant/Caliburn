"use client";

// Slice 1 smoke surface for the v3 CopilotKit wiring (button-driven, no chat) — v2 API (D22).
// Separate from the legacy profiles/[id] page (built on the removed old backend).
// useAgent() returns the AG-UI agent; the button seeds shared state (pick_profile reads
// state.job_title, not chat messages) via agent.setState, adds a trigger turn, then
// agent.runAgent(). The select_profile interrupt is rendered by <InterruptHandlers/>
// (v2 useInterrupt, renderInChat:false). Later slices add the remaining interrupts.
import { use, useState } from "react";
import { useAgent } from "@copilotkit/react-core/v2";
import { InterruptHandlers } from "@/components/interview/v3/InterruptHandlers";
import { Button } from "@/components/ui/button";

const AGENT_NAME = "jd_authoring";

export default function V3Page({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const [jobTitle, setJobTitle] = useState("設備維護工程師");
  const [jobSummary, setJobSummary] = useState("");
  const { agent } = useAgent({ agentId: AGENT_NAME });

  const start = () => {
    agent.setState({
      job_profile_id: id,
      job_title: jobTitle,
      job_summary: jobSummary,
      current_step: "pick_profile",
      profile: { candidates: [], selected_ocs_code: null },
      tasks: [],
      ksa: { knowledge: [], skills: [], attitudes: [] },
      document: null,
    });
    agent.addMessage({ id: crypto.randomUUID(), role: "user", content: "開始" });
    void agent.runAgent().catch((e: unknown) => console.error("runAgent failed", e));
  };

  const state = agent.state as { current_step?: string } | undefined;

  return (
    <div className="mx-auto max-w-2xl space-y-4 p-6">
      <div>
        <h1 className="text-lg font-semibold">v3 訪談（Slice 1 smoke）</h1>
        <p className="text-xs text-muted-foreground">profile {id}</p>
      </div>

      <div className="space-y-2">
        <input
          className="w-full rounded-lg border px-3 py-2 text-sm"
          placeholder="職稱（pick_profile 會用它搜尋 OCS）"
          value={jobTitle}
          onChange={(e) => setJobTitle(e.target.value)}
        />
        <textarea
          className="w-full rounded-lg border px-3 py-2 text-sm"
          placeholder="職務簡述（可空）"
          value={jobSummary}
          onChange={(e) => setJobSummary(e.target.value)}
        />
        <Button onClick={start}>開始（搜尋 OCS）</Button>
      </div>

      <p className="text-sm text-muted-foreground">
        current_step：<span className="font-mono">{state?.current_step ?? "—"}</span>
      </p>

      {/* select_profile（與後續）interrupt 在此渲染 */}
      <InterruptHandlers />
    </div>
  );
}
