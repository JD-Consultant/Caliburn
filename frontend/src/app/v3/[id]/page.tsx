"use client";

// v3 interview surface (button-driven, no chat — D11/D22). Loads the JobProfile
// from the DB and seeds the AG-UI agent state from it; pick_profile reads
// state.job_title (not chat messages) to search OCS. The interrupts (select_profile,
// edit_tasks, ask_human, curate_ks, curate_attitudes, preview) are rendered by
// <InterruptHandlers/> via v2 useInterrupt (renderInChat:false) into our own UI.
import { use } from "react";
import Link from "next/link";
import { useAgent } from "@copilotkit/react-core/v2";
import { useProfile } from "@/hooks/useProfiles";
import { InterruptHandlers } from "@/components/interview/v3/InterruptHandlers";
import { Button } from "@/components/ui/button";
import { ChevronLeft } from "lucide-react";

const AGENT_NAME = "jd_authoring";

export default function V3Page({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const { data: profile, isLoading } = useProfile(id);
  const { agent } = useAgent({ agentId: AGENT_NAME });

  const start = () => {
    if (!profile) return;
    agent.setState({
      job_profile_id: id,
      job_title: profile.job_title,
      job_summary: profile.job_summary ?? "",
      current_step: "pick_profile",
      profile: { candidates: [], selected_ocs_codes: [], selected_ocs_code: null },
      tasks: [],
      // 完整 InterviewState：deep 不能漏，否則 route_deep 讀 state["deep"] → KeyError
      deep: {
        current_task_index: 0,
        slots_by_task: {},
        missing_fields: [],
        completed_task_ids: [],
        retry: {},
      },
      ksa: { pool: { knowledge: [], skills: [], attitudes: [] }, by_task: {}, attitudes: [], ks_index: 0 },
      document: null,
    });
    agent.addMessage({ id: crypto.randomUUID(), role: "user", content: "開始" });
    void agent.runAgent().catch((e: unknown) => console.error("runAgent failed", e));
  };

  const state = agent.state as { current_step?: string } | undefined;

  return (
    <div className="mx-auto max-w-2xl space-y-4 p-6">
      <Link href="/dashboard" className="inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground">
        <ChevronLeft className="h-4 w-4" />
        職務檔案
      </Link>

      <div>
        <h1 className="text-lg font-semibold">{profile?.job_title ?? (isLoading ? "載入中…" : "找不到職務")}</h1>
        {profile?.department ? (
          <p className="text-xs text-muted-foreground">{profile.department}</p>
        ) : null}
        {profile?.job_summary ? (
          <p className="mt-1 text-sm text-muted-foreground">{profile.job_summary}</p>
        ) : null}
      </div>

      <Button onClick={start} disabled={!profile}>
        開始訪談（搜尋職類 OCS）
      </Button>

      <p className="text-sm text-muted-foreground">
        current_step：<span className="font-mono">{state?.current_step ?? "—"}</span>
      </p>

      {/* select_profile / edit_tasks / ask_human / curate_ks / curate_attitudes / preview interrupts */}
      <InterruptHandlers />
    </div>
  );
}
