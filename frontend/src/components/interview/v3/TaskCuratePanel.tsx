"use client";

// D27〔選任務〕modal（加法/全保留）：列出已選職類所有任務（職類→職責分組）。
// 職責有獨立勾選框＝「採用整個職責」→ 勾才保留職責名稱、不勾留白（即使逐一勾完）。
// 已在文件的任務顯示「已加入」(disabled)；本面板只「加」新任務，刪除走表格。
import { useMemo, useState } from "react";
import { useBuildTasks, useTaskCandidates } from "@/hooks/useDocument";
import type { OcsDocument, PickedTask } from "@/types";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Modal } from "./OccupationPicker";

const tkey = (oc: string, tid: string) => `${oc}__${tid}`;
const ukey = (oc: string, uid: string) => `${oc}__${uid}`;

export function TaskCuratePanel({
  profileId,
  currentDoc,
  onClose,
  onError,
}: {
  profileId: string;
  currentDoc: OcsDocument | undefined;
  onClose: () => void;
  onError: (msg: string) => void;
}) {
  const { data, isLoading, isError } = useTaskCandidates(profileId, true);
  const build = useBuildTasks(profileId);
  const groups = data?.groups ?? [];

  // 已在文件的任務（依 provenance）→ 顯示為「已加入」不可勾。
  const alreadyIn = useMemo(() => {
    const s = new Set<string>();
    for (const u of currentDoc?.ocs_content?.ocu_units ?? []) {
      for (const t of u.tasks ?? []) {
        const p = t.provenance;
        if (p?.ocs_code && p?.task_id) s.add(tkey(p.ocs_code, p.task_id));
      }
    }
    return s;
  }, [currentDoc]);

  const [picked, setPicked] = useState<Set<string>>(new Set());
  const [adopted, setAdopted] = useState<Set<string>>(new Set()); // 採用的職責（保留名稱）

  const toggleTask = (k: string) =>
    setPicked((prev) => {
      const next = new Set(prev);
      if (next.has(k)) next.delete(k);
      else next.add(k);
      return next;
    });

  const toggleUnit = (oc: string, uid: string, taskIds: string[], on: boolean) => {
    const uk = ukey(oc, uid);
    setAdopted((prev) => {
      const next = new Set(prev);
      if (on) next.add(uk);
      else next.delete(uk);
      return next;
    });
    setPicked((prev) => {
      const next = new Set(prev);
      for (const tid of taskIds) {
        const k = tkey(oc, tid);
        if (alreadyIn.has(k)) continue; // 已加入的不動
        if (on) next.add(k);
        else next.delete(k);
      }
      return next;
    });
  };

  const confirm = () => {
    const out: PickedTask[] = [];
    for (const g of groups) {
      for (const u of g.units) {
        const adopt = adopted.has(ukey(g.ocs_code, u.unit_id));
        for (const t of u.tasks) {
          const k = tkey(g.ocs_code, t.task_id);
          if (alreadyIn.has(k) || !picked.has(k)) continue;
          out.push({
            ocs_code: g.ocs_code,
            unit_id: u.unit_id,
            unit_title: adopt ? u.unit_title : "", // 不採用 → 職責名留白
            occupation_name: g.occupation_name,
            task_id: t.task_id,
            task_name: t.task_title,
          });
        }
      }
    }
    if (out.length === 0) {
      onClose();
      return;
    }
    build.mutate(out, {
      onSuccess: onClose,
      onError: (e: unknown) => onError(e instanceof Error ? e.message : "建立任務失敗"),
    });
  };

  return (
    <Modal title="選擇任務（勾職責＝採用整組保留名稱；只勾任務＝職責名留白）" onClose={onClose}>
      {isLoading ? (
        <div className="h-32 animate-pulse rounded bg-muted" />
      ) : isError ? (
        <p className="text-sm text-destructive">候選載入失敗（indexer 未連線？）。</p>
      ) : groups.length === 0 ? (
        <p className="text-sm text-muted-foreground">沒有候選任務。請先〔選職類〕。</p>
      ) : (
        <div className="max-h-[60vh] space-y-4 overflow-y-auto">
          {groups.map((g) => (
            <div key={g.ocs_code}>
              <div className="mb-1 flex items-center gap-2">
                <Badge variant="outline" className="text-xs">{g.occupation_name}</Badge>
                <span className="font-mono text-xs text-muted-foreground">{g.ocs_code}</span>
              </div>
              <div className="space-y-2">
                {g.units.map((u) => {
                  const ids = u.tasks.map((t) => t.task_id);
                  const addable = ids.filter((id) => !alreadyIn.has(tkey(g.ocs_code, id)));
                  const unitDone = addable.length === 0;
                  return (
                    <div key={u.unit_id} className="rounded-md border">
                      <label className="flex cursor-pointer items-center gap-2 border-b bg-muted/40 px-2 py-1.5 text-sm font-medium">
                        <input
                          type="checkbox"
                          disabled={unitDone}
                          checked={adopted.has(ukey(g.ocs_code, u.unit_id))}
                          onChange={(e) => toggleUnit(g.ocs_code, u.unit_id, ids, e.target.checked)}
                        />
                        <span className="font-mono text-xs text-muted-foreground">{u.unit_id}</span>
                        <span>{u.unit_title}</span>
                        {unitDone ? <Badge variant="secondary" className="ml-auto text-[10px]">已加入</Badge> : null}
                      </label>
                      <div className="space-y-0.5 p-1.5">
                        {u.tasks.map((t) => {
                          const k = tkey(g.ocs_code, t.task_id);
                          const inDoc = alreadyIn.has(k);
                          return (
                            <label
                              key={t.task_id}
                              className={
                                "flex items-center gap-2 rounded px-2 py-1 text-sm " +
                                (inDoc ? "opacity-50" : "cursor-pointer hover:bg-muted/50")
                              }
                            >
                              <input
                                type="checkbox"
                                disabled={inDoc}
                                checked={inDoc || picked.has(k)}
                                onChange={() => toggleTask(k)}
                              />
                              <span className="font-mono text-xs text-muted-foreground">{t.task_id}</span>
                              <span>{t.task_title}</span>
                              {inDoc ? <span className="ml-auto text-[10px] text-muted-foreground">已加入</span> : null}
                            </label>
                          );
                        })}
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          ))}
        </div>
      )}

      <div className="mt-4 flex items-center justify-between">
        <span className="text-xs text-muted-foreground">將新增 {picked.size} 個任務</span>
        <div className="flex gap-2">
          <Button variant="ghost" onClick={onClose}>取消</Button>
          <Button onClick={confirm} disabled={build.isPending}>
            {build.isPending ? "新增中…" : "加入文件"}
          </Button>
        </div>
      </div>
    </Modal>
  );
}
