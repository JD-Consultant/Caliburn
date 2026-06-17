"use client";

// Slice 1 smoke surface for the v3 CopilotKit wiring (button-driven, no chat).
// Separate from the legacy profiles/[id] page (built on the removed old backend).
// useCoAgent holds the shared agent state (pick_profile reads state.job_title, not
// chat messages); the button seeds job_title via setState then run() triggers the
// graph. The select_profile interrupt is rendered by <InterruptHandlers/>.
// Later slices add the remaining interrupts, editable panels, and retire useInterview.
import { use, useState } from "react";
import { useCoAgent } from "@copilotkit/react-core";
import { InterruptHandlers } from "@/components/interview/v3/InterruptHandlers";
import { Button } from "@/components/ui/button";

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
  const [jobTitle, setJobTitle] = useState("設備維護工程師");
  const [jobSummary, setJobSummary] = useState("");

  const { state, setState, run, running } = useCoAgent<AgentState>({
    name: AGENT_NAME,
    initialState: {
      job_profile_id: id,
      job_title: jobTitle,
      job_summary: jobSummary,
      current_step: "pick_profile",
      profile: { candidates: [], selected_ocs_code: null },
      tasks: [],
      ksa: { knowledge: [], skills: [], attitudes: [] },
      document: null,
    },
  });

  const start = () => {
    setState({
      ...state!,
      job_profile_id: id,
      job_title: jobTitle,
      job_summary: jobSummary,
      current_step: "pick_profile",
    });
    void Promise.resolve(run()).catch((e: unknown) => console.error("run failed", e));
  };

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
        <Button disabled={running} onClick={start}>
          {running ? "執行中…" : "開始（搜尋 OCS）"}
        </Button>
      </div>

      <p className="text-sm text-muted-foreground">
        current_step：<span className="font-mono">{state?.current_step ?? "—"}</span>
      </p>

      {/* select_profile（與後續）interrupt 在此渲染 */}
      <InterruptHandlers />
    </div>
  );
}
