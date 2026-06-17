"use client";

// Slice 1 smoke surface for the v3 CopilotKit wiring. Separate from the legacy
// profiles/[id] page (built on the removed old backend). The agent is driven via
// <CopilotChat> (which manages the run session) rather than a headless run() call
// (headless run() crashes — no chat session for its abortController). useCoAgent
// seeds job_title/job_summary into the shared state, which pick_profile reads
// (it does not read chat messages). Send any message (e.g. 「開始」) to kick off
// the graph; the select_profile interrupt is rendered by <InterruptHandlers/>.
// Later slices add the remaining interrupts, editable panels, and retire useInterview.
import "@copilotkit/react-ui/styles.css";
import { use } from "react";
import { useCoAgent } from "@copilotkit/react-core";
import { CopilotChat } from "@copilotkit/react-ui";
import { InterruptHandlers } from "@/components/interview/v3/InterruptHandlers";

const AGENT_NAME = "jd_authoring";

type AgentState = {
  job_profile_id: string;
  job_title: string;
  job_summary: string;
  current_step: string;
  profile: { candidates: unknown[]; selected_ocs_code: string | null };
  tasks: unknown[];
  ksa: { knowledge: unknown[]; skills: unknown[]; attitudes: unknown[] };
  document: unknown | null;
};

export default function V3Page({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);

  const { state, setState } = useCoAgent<AgentState>({
    name: AGENT_NAME,
    initialState: {
      job_profile_id: id,
      job_title: "設備維護工程師",
      job_summary: "",
      current_step: "pick_profile",
      profile: { candidates: [], selected_ocs_code: null },
      tasks: [],
      ksa: { knowledge: [], skills: [], attitudes: [] },
      document: null,
    },
  });

  return (
    <div className="mx-auto flex h-screen max-w-3xl flex-col gap-3 p-4">
      <div>
        <h1 className="text-lg font-semibold">v3 訪談（Slice 1 smoke）</h1>
        <p className="text-xs text-muted-foreground">profile {id}</p>
      </div>

      <label className="text-sm">
        職稱（pick_profile 會用它搜尋 OCS）：
        <input
          className="ml-2 rounded-lg border px-2 py-1 text-sm"
          value={state?.job_title ?? ""}
          onChange={(e) => setState({ ...state!, job_title: e.target.value })}
        />
      </label>
      <p className="text-sm text-muted-foreground">
        current_step：<span className="font-mono">{state?.current_step ?? "—"}</span>
      </p>

      {/* select_profile（與後續）interrupt 在此渲染 */}
      <InterruptHandlers />

      {/* 在聊天框輸入任意訊息（例如「開始」）即觸發 agent 跑 pick_profile */}
      <div className="min-h-0 flex-1 rounded-xl border">
        <CopilotChat
          className="h-full"
          labels={{
            title: "JD 訪談",
            initial: "輸入任意訊息（例如「開始」）即用上方職稱搜尋 OCS 候選。",
          }}
        />
      </div>
    </div>
  );
}
