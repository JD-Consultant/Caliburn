"use client";

import type { ConsultantSnapshotView } from "@caliburn/job-analysis-contract";
import {
  CircleDot,
  FileClock,
  Link2Off,
  Map as MapIcon,
  Rows3,
} from "lucide-react";

import { Badge } from "@/shared/ui/badge";
import { Card } from "@/shared/ui/card";
import { ConsultantInsightPanel } from "./ConsultantInsightPanel";

export function InterviewWorkMap({
  documentId,
  snapshot,
  mutationLocked,
}: {
  documentId: string;
  snapshot: ConsultantSnapshotView;
  mutationLocked: boolean;
}) {
  const document = snapshot.current_document;
  const unassignedTasks = document.tasks.filter(
    (task) => task.duty_id === null,
  );
  const unlinkedKnowledgeSkills = document.opks.filter(
    (item) =>
      (item.kind === "knowledge" || item.kind === "skill") &&
      item.task_ids.length === 0,
  );
  const tasksByDuty = new Map<string, typeof document.tasks>();
  for (const task of document.tasks) {
    if (!task.duty_id) continue;
    const tasks = tasksByDuty.get(task.duty_id) ?? [];
    tasks.push(task);
    tasksByDuty.set(task.duty_id, tasks);
  }

  return (
    <div className="space-y-4">
      <div className="flex items-start gap-3 px-1">
        <div className="rounded-xl bg-blue-50 p-2 text-blue-700">
          <MapIcon className="size-5" />
        </div>
        <div>
          <p className="text-xs font-semibold tracking-[0.14em] text-stone-500 uppercase">
            訪談工作地圖
          </p>
          <h2 className="mt-1 font-semibold">知道目前談到哪裡，也保留新線索</h2>
        </div>
      </div>

      <div className="grid grid-cols-2 gap-2 text-xs">
        <div className="rounded-xl border border-stone-200 bg-white p-3">
          <Rows3 className="mb-2 size-4 text-blue-600" />
          <p className="font-semibold">
            {snapshot.visible_work.length} 項可見工作
          </p>
          <p className="mt-1 text-stone-500">已辨識線索與訪談項目</p>
        </div>
        <div className="rounded-xl border border-stone-200 bg-white p-3">
          <FileClock className="mb-2 size-4 text-blue-600" />
          <p className="font-semibold">
            待確認 {snapshot.semantic_progress.employee_decisions.pending} 項
          </p>
          <p className="mt-1 text-stone-500">AI 文件變更</p>
        </div>
        <div className="rounded-xl border border-stone-200 bg-white p-3">
          <CircleDot className="mb-2 size-4 text-blue-600" />
          <p className="font-semibold">尚未分組 {unassignedTasks.length} 項</p>
          <p className="mt-1 text-stone-500">已有內容但未連到職責</p>
        </div>
        <div className="rounded-xl border border-stone-200 bg-white p-3">
          <Link2Off className="mb-2 size-4 text-blue-600" />
          <p className="font-semibold">
            K／S 待連結 {unlinkedKnowledgeSkills.length} 項
          </p>
          <p className="mt-1 text-stone-500">可先保留，之後再整理</p>
        </div>
      </div>

      <Card className="border-stone-200 bg-white p-4 shadow-sm">
        <div className="flex items-center justify-between gap-3">
          <h2 className="text-sm font-semibold">目前 JD 導覽</h2>
          <Badge variant="outline">
            {document.duties.length} 職責 · {document.tasks.length} 工作
          </Badge>
        </div>
        {document.duties.length === 0 && unassignedTasks.length === 0 ? (
          <p className="mt-3 text-sm leading-6 text-stone-500">
            JD 結構仍在形成；訪談線索不必先綁定到特定欄位。
          </p>
        ) : (
          <div className="mt-3 space-y-3">
            {document.duties.map((duty) => (
              <div key={duty.duty_id}>
                <a
                  href={`#duty-${duty.duty_id}`}
                  className="block truncate text-sm font-medium text-stone-900 hover:text-blue-700"
                >
                  {duty.statement}
                </a>
                <div className="mt-1 space-y-1 border-l border-stone-200 pl-3">
                  {(tasksByDuty.get(duty.duty_id) ?? []).map((task) => (
                    <a
                      key={task.task_id}
                      href={`#task-${task.task_id}`}
                      className="block truncate text-xs text-stone-600 hover:text-blue-700"
                    >
                      {task.statement}
                    </a>
                  ))}
                </div>
              </div>
            ))}
            {unassignedTasks.length ? (
              <div>
                <p className="text-xs font-semibold text-stone-500">尚未歸屬</p>
                <div className="mt-1 space-y-1 border-l border-stone-200 pl-3">
                  {unassignedTasks.map((task) => (
                    <a
                      key={task.task_id}
                      href={`#task-${task.task_id}`}
                      className="block truncate text-xs text-stone-600 hover:text-blue-700"
                    >
                      {task.statement}
                    </a>
                  ))}
                </div>
              </div>
            ) : null}
          </div>
        )}
      </Card>

      <ConsultantInsightPanel
        documentId={documentId}
        snapshot={snapshot}
        mutationLocked={mutationLocked}
      />
    </div>
  );
}
