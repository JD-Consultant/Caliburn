import type { SourceRef } from "@/types";

// 選單來源行（版面 A：Material 3 supporting text）：首個來源 + 多來源「+N」hover 全部。
// 來源含任務範圍（task_code/task_name）時一併顯示，方便追溯到官方哪個任務。
function fmt(r: SourceRef): string {
  const head = `${r.occupation_name} ${r.ocs_code}`.trim();
  const task = r.task_code ? ` · ${r.task_code}${r.task_name ? " " + r.task_name : ""}` : "";
  return head + task;
}

export function SourceLine({ srcs }: { srcs?: SourceRef[] }) {
  if (!srcs || srcs.length === 0) return null;
  const more = srcs.length - 1;
  return (
    <div className="mt-0.5 text-[10px] text-muted-foreground" title={more > 0 ? srcs.map(fmt).join("\n") : undefined}>
      來源:{fmt(srcs[0])}
      {more > 0 ? <span className="ml-1 rounded bg-muted px-1">+{more}</span> : null}
    </div>
  );
}
