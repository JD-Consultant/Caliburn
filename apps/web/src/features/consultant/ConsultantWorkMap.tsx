"use client";

import type { ConsultantSnapshotView } from "@caliburn/job-analysis-contract";
import { Map, PanelLeft, PanelLeftClose } from "lucide-react";
import { useState } from "react";

import { interviewWorkStatusLabel } from "./consultantWorkspaceModel";
import { Badge } from "@/shared/ui/badge";
import { Button } from "@/shared/ui/button";
import { Card } from "@/shared/ui/card";

export function ConsultantWorkMap({
  snapshot,
  collapsed,
  onToggle,
}: {
  snapshot: ConsultantSnapshotView;
  collapsed?: boolean;
  onToggle?: () => void;
}) {
  const [internalCollapsed, setInternalCollapsed] = useState(collapsed ?? false);
  const isCollapsed = collapsed ?? internalCollapsed;
  const toggle = onToggle ?? (() => setInternalCollapsed((value) => !value));

  if (isCollapsed) {
    return (
      <aside aria-label="訪談工作地圖" className="min-w-0">
        <Button
          variant="outline"
          className="w-full justify-start gap-2"
          aria-expanded={false}
          onClick={toggle}
        >
          <PanelLeft className="size-4" />
          開啟工作地圖
        </Button>
      </aside>
    );
  }

  return (
    <aside aria-label="訪談工作地圖" className="min-w-0">
      <Card className="border-stone-200 bg-white p-4 shadow-sm">
        <div className="flex items-start justify-between gap-3">
          <div className="flex items-start gap-2">
            <Map className="mt-0.5 size-5 text-stone-600" />
            <div>
              <p className="text-xs font-semibold tracking-[0.16em] text-stone-500 uppercase">
                導航與摘要
              </p>
              <h2 className="mt-1 font-semibold">訪談工作地圖</h2>
            </div>
          </div>
          <Button
            variant="ghost"
            size="icon-sm"
            aria-label="收合工作地圖"
            aria-expanded={true}
            onClick={toggle}
          >
            <PanelLeftClose />
          </Button>
        </div>

        <p className="mt-3 text-xs leading-5 text-stone-500">
          這裡顯示訪談脈絡與待處理方向，不會跟著目前 JD 的 Duty／Task 分組或編號變動。
        </p>

        <div className="mt-4 space-y-3">
          {snapshot.visible_work.length ? (
            snapshot.visible_work.map((work) => (
              <div key={work.work_id} className="rounded-lg border border-stone-200 px-3 py-3">
                <div className="flex items-start justify-between gap-2">
                  <p className="text-sm font-medium leading-5">{work.title}</p>
                  <Badge variant="outline">{interviewWorkStatusLabel(work.status)}</Badge>
                </div>
                <p className="mt-1 text-xs leading-5 text-stone-500">{work.priority_reason}</p>
              </div>
            ))
          ) : (
            <p className="text-sm text-stone-500">目前還沒有可顯示的訪談工作。</p>
          )}
        </div>

        <div className="mt-4 border-t border-stone-100 pt-4 text-xs text-stone-500">
          <p>目前辨識 {snapshot.semantic_progress.currently_known_work_count} 項訪談工作</p>
          <p className="mt-1">
            待處理缺口 {snapshot.semantic_progress.gaps.filter((gap) => gap.status !== "resolved").length} 項
          </p>
        </div>
      </Card>
    </aside>
  );
}
