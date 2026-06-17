"use client";

// v3 HITL via CopilotKit v2 useInterrupt (D22). renderInChat:false → the hook
// returns a ReactElement we place in our own (no-chat) UI. Listens to the agent's
// on_interrupt custom events. Slice 1 wires only `select_profile`; later slices add
// edit_tasks / ask_human / edit_ksa / preview.
import { useInterrupt } from "@copilotkit/react-core/v2";
import { useState } from "react";

const AGENT_NAME = "jd_authoring";

type ProfileCandidate = {
  id?: string;
  ocs_code: string;
  job_title?: string | null;
  task_title?: string | null;
};
type InterruptValue = { kind?: string; candidates?: ProfileCandidate[] };

function ProfilePicker({
  candidates,
  onPick,
}: {
  candidates: ProfileCandidate[];
  onPick: (ocsCode: string) => void;
}) {
  const [picked, setPicked] = useState<string | null>(null);
  if (!candidates.length) {
    return <div className="text-sm text-muted-foreground">indexer 沒有回傳候選 OCS。</div>;
  }
  return (
    <div className="space-y-2 rounded-xl border p-3">
      <p className="text-sm font-medium">選擇職類（OCS）</p>
      {candidates.map((c) => (
        <button
          key={c.ocs_code}
          type="button"
          className={`block w-full rounded-lg border px-3 py-2 text-left text-sm hover:bg-muted ${
            picked === c.ocs_code ? "border-blue-500 bg-blue-50" : ""
          }`}
          disabled={picked !== null}
          onClick={() => {
            setPicked(c.ocs_code);
            onPick(c.ocs_code);
          }}
        >
          <span className="font-mono text-xs text-muted-foreground">{c.ocs_code}</span>
          {c.job_title ? `　${c.job_title}` : ""}
        </button>
      ))}
    </div>
  );
}

export function InterruptHandlers() {
  return useInterrupt({
    agentId: AGENT_NAME,
    renderInChat: false,
    render: ({ event, resolve }) => {
      // event.value is normally the parsed payload; tolerate a JSON string too.
      let raw: unknown = event.value;
      if (typeof raw === "string") {
        try {
          raw = JSON.parse(raw);
        } catch {
          /* leave as-is */
        }
      }
      const value = (raw ?? {}) as InterruptValue;
      if (value.kind === "select_profile") {
        return (
          <ProfilePicker
            candidates={value.candidates ?? []}
            onPick={(ocsCode) => resolve(ocsCode)}
          />
        );
      }
      // 其他 interrupt 種類由後續 slice 接手
      return <></>;
    },
  });
}
