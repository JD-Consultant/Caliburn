"use client";

// D27 工作台主表（T6）：把一份 OCS 文件 render 成可互動表格（照官方版型：
// 單元 → 任務（級別）→ 產出O / 指標P / K / S）。純呈現元件，不抓資料、不碰
// CopilotKit；點空/已填格 → onCell(target)，由上層（T8 shell）開 filler 面板。
import type { CompetencyBlock, OcsDocument, OcsTask } from "@/types";
import { Badge } from "@/components/ui/badge";
import { Check, Pencil } from "lucide-react";

export type CellKind = "op" | "k" | "s";
export type CellTarget =
  | { kind: CellKind; unitIdx: number; taskIdx: number }
  | { kind: "a" };

export function firstBlock(task: OcsTask): CompetencyBlock | undefined {
  return task.competency_blocks?.[0];
}

function count(arr: unknown[] | undefined): number {
  return Array.isArray(arr) ? arr.length : 0;
}

function Cell({
  label,
  filled,
  n,
  onClick,
}: {
  label: string;
  filled: boolean;
  n: number;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={
        "flex items-center gap-1.5 rounded-md border px-2 py-1 text-xs transition-colors " +
        (filled
          ? "border-emerald-200 bg-emerald-50 text-emerald-700 hover:bg-emerald-100"
          : "border-dashed border-muted-foreground/30 text-muted-foreground hover:border-foreground/40 hover:text-foreground")
      }
    >
      {filled ? <Check className="h-3 w-3" /> : <Pencil className="h-3 w-3" />}
      <span className="font-medium">{label}</span>
      {filled ? <span className="tabular-nums opacity-70">{n}</span> : <span>點此填</span>}
    </button>
  );
}

export function JobDocTable({
  document,
  onCell,
}: {
  document: OcsDocument;
  onCell: (target: CellTarget) => void;
}) {
  const profile = document.ocs_profile;
  const units = document.ocs_content?.ocu_units ?? [];
  const attitudes = document.ocs_attitude?.attitudes ?? [];
  const notes = document.notes;

  return (
    <div className="space-y-5">
      {/* 表頭 */}
      <div className="rounded-lg border bg-background p-4">
        <div className="flex flex-wrap items-center gap-2">
          <h2 className="text-base font-semibold">
            {profile?.ocs_name?.occupation_name || "（未命名職務）"}
          </h2>
          {profile?.ocs_code ? (
            <Badge variant="outline" className="font-mono text-xs">
              {profile.ocs_code}
            </Badge>
          ) : null}
          {profile?.ocs_level != null ? (
            <Badge variant="secondary" className="text-xs">
              基準級別 {profile.ocs_level}
            </Badge>
          ) : null}
        </div>
        {profile?.job_description ? (
          <p className="mt-2 text-sm text-muted-foreground">{profile.job_description}</p>
        ) : null}
      </div>

      {/* 單元 → 任務 */}
      {units.length === 0 ? (
        <div className="rounded-lg border border-dashed p-8 text-center text-sm text-muted-foreground">
          尚無任務。請先選職類（seed）以帶入任務骨架。
        </div>
      ) : (
        units.map((unit, unitIdx) => (
          <div key={`${unit.ocu_code}-${unitIdx}`} className="rounded-lg border bg-background">
            <div className="flex items-center gap-2 border-b bg-muted/40 px-4 py-2">
              <Badge variant="outline" className="font-mono text-xs">
                {unit.ocu_code}
              </Badge>
              <span className="text-sm font-medium">{unit.ocu_name}</span>
            </div>
            <div className="divide-y">
              {(unit.tasks ?? []).map((task, taskIdx) => {
                const block = firstBlock(task);
                const level = block?.competency_level;
                const tc = task.task_codes?.[0];
                return (
                  <div key={`${unitIdx}-${taskIdx}`} className="px-4 py-3">
                    <div className="mb-2 flex items-center gap-2">
                      {tc?.code ? (
                        <span className="font-mono text-xs text-muted-foreground">{tc.code}</span>
                      ) : null}
                      <span className="text-sm font-medium">{tc?.name || "（未命名任務）"}</span>
                      <span className="ml-auto text-xs text-muted-foreground">
                        級別 {level != null ? level : "—"}
                      </span>
                    </div>
                    <div className="flex flex-wrap gap-2">
                      <Cell
                        label="產出 O"
                        filled={count(block?.outputs) > 0}
                        n={count(block?.outputs)}
                        onClick={() => onCell({ kind: "op", unitIdx, taskIdx })}
                      />
                      <Cell
                        label="指標 P"
                        filled={count(block?.indicators) > 0}
                        n={count(block?.indicators)}
                        onClick={() => onCell({ kind: "op", unitIdx, taskIdx })}
                      />
                      <Cell
                        label="知識 K"
                        filled={count(block?.knowledge) > 0}
                        n={count(block?.knowledge)}
                        onClick={() => onCell({ kind: "k", unitIdx, taskIdx })}
                      />
                      <Cell
                        label="技能 S"
                        filled={count(block?.skills) > 0}
                        n={count(block?.skills)}
                        onClick={() => onCell({ kind: "s", unitIdx, taskIdx })}
                      />
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        ))
      )}

      {/* 全域態度 A */}
      <div className="rounded-lg border bg-background p-4">
        <div className="flex items-center gap-3">
          <span className="text-sm font-medium">全域態度 A</span>
          <Cell
            label="態度 A"
            filled={attitudes.length > 0}
            n={attitudes.length}
            onClick={() => onCell({ kind: "a" })}
          />
        </div>
      </div>

      {/* 說明（唯讀） */}
      {notes && (notes.prerequisites?.length || notes.supplements?.length) ? (
        <div className="rounded-lg border bg-background p-4 text-xs text-muted-foreground">
          {notes.prerequisites?.length ? (
            <div className="mb-2">
              <p className="mb-1 font-medium text-foreground">學經歷/能力建議</p>
              <ul className="list-disc space-y-0.5 pl-4">
                {notes.prerequisites.map((p, i) => (
                  <li key={i}>{p}</li>
                ))}
              </ul>
            </div>
          ) : null}
          {notes.supplements?.length ? (
            <div>
              <p className="mb-1 font-medium text-foreground">補充說明</p>
              <ul className="list-disc space-y-0.5 pl-4">
                {notes.supplements.map((s, i) => (
                  <li key={i}>{s}</li>
                ))}
              </ul>
            </div>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}
