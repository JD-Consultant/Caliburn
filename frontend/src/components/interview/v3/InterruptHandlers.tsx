"use client";

// v3 HITL: render graph_v3 interrupts via CopilotKit's useLangGraphInterrupt.
// Slice 1 wires only `select_profile`; the other kinds (edit_tasks / ask_human /
// edit_ksa / preview) are added in later slices.
import { useLangGraphInterrupt } from "@copilotkit/react-core";
import { useState } from "react";

type ProfileCandidate = {
  id?: string;
  ocs_code: string;
  job_title?: string | null;
  task_title?: string | null;
};

type InterruptValue = {
  kind?: string;
  candidates?: ProfileCandidate[];
};

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
  useLangGraphInterrupt<InterruptValue>({
    render: ({ event, resolve }) => {
      const value = event.value;
      if (value?.kind === "select_profile") {
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
  return null;
}
