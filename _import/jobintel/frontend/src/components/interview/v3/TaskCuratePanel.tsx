"use client";

// D27〔選任務〕modal（加法/全保留）：列出已選職類所有任務（職類→職責分組）。
// 職責有獨立勾選框＝「採用整個職責」→ 勾才保留職責名稱、不勾留白（即使逐一勾完）。
// 已在文件的任務顯示「已加入」(disabled)；本面板只「加」新任務，刪除走表格。
import { useEffect, useMemo, useState } from "react";
import { Loader2, Plus, Sparkles, Trash2 } from "lucide-react";
import { useBuildTasks, useTaskCandidates } from "@/hooks/useDocument";
import { extractTasks, structureTask } from "@/lib/api";
import type { OcsDocument, PickedTask } from "@/types";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Modal } from "./OccupationPicker";

const tkey = (oc: string, tid: string) => `${oc}__${tid}`;
const ukey = (oc: string, uid: string) => `${oc}__${uid}`;

function newUid(): string {
  return globalThis.crypto?.randomUUID?.() ?? `id-${Math.random().toString(36).slice(2)}`;
}

export function TaskCuratePanel({
  profileId,
  currentDoc,
  intake = "",
  autoExtract = false,
  onClose,
  onError,
}: {
  profileId: string;
  currentDoc: OcsDocument | undefined;
  // D28 T11：員工自述（job_summary）餵 extract-tasks 預勾；intake 流程進來時 autoExtract。
  intake?: string;
  autoExtract?: boolean;
  onClose: () => void;
  onError: (msg: string) => void;
}) {
  const { data, isLoading, isError } = useTaskCandidates(profileId, true);
  const build = useBuildTasks(profileId);
  const groups = useMemo(() => data?.groups ?? [], [data]);

  // 已在文件的任務（依 provenance）→ 顯示為「已加入」不可勾。
  const alreadyIn = useMemo(() => {
    const s = new Set<string>();
    for (const u of currentDoc?.ocs_content?.ocu_units ?? []) {
      for (const t of u.tasks ?? []) {
        const p = t.provenance;
        if (p?.ocs_code && p?.task_code) s.add(tkey(p.ocs_code, p.task_code));
      }
    }
    return s;
  }, [currentDoc]);

  const [picked, setPicked] = useState<Set<string>>(new Set());
  const [adopted, setAdopted] = useState<Set<string>>(new Set()); // 採用的職責（保留名稱）

  // D28 T11：extract-tasks 預勾 + CIT 補漏自訂任務。
  const [aiBusy, setAiBusy] = useState(false);
  const [extracted, setExtracted] = useState(false);
  const [aiCustoms, setAiCustoms] = useState<{ name: string }[]>([]); // 候選自訂（AI 列）
  const [customPicks, setCustomPicks] = useState<PickedTask[]>([]); // 已加入的自訂任務（送 build）
  const [citDesc, setCitDesc] = useState("");
  const [citBusy, setCitBusy] = useState(false);
  const [citProposal, setCitProposal] = useState<{ task_name: string; unit_suggestion: string } | null>(null);

  const ocsCodes = useMemo(() => groups.map((g) => g.ocs_code), [groups]);

  const runExtract = async () => {
    if (!intake.trim() || groups.length === 0) return;
    setAiBusy(true);
    setExtracted(true);
    try {
      const res = await extractTasks({ intake, ocs_codes: ocsCodes });
      const byCode = new Map<string, { oc: string; tc: string }>();
      for (const g of groups) for (const u of g.units) for (const t of u.tasks)
        byCode.set(`${g.ocs_code}__${t.task_code}`, { oc: g.ocs_code, tc: t.task_code });
      setPicked((prev) => {
        const next = new Set(prev);
        // suggested_task_ids are task_codes scoped per OCS: try each group
        for (const id of res.suggested_task_ids) {
          for (const g of groups) {
            const m = byCode.get(`${g.ocs_code}__${id}`);
            if (m && !alreadyIn.has(tkey(m.oc, m.tc))) next.add(tkey(m.oc, m.tc));
          }
        }
        return next;
      });
      setAiCustoms(res.custom_candidates ?? []);
    } catch (e: unknown) {
      onError(e instanceof Error ? e.message : "AI 預勾失敗");
    } finally {
      setAiBusy(false);
    }
  };

  // intake 流程進來：候選載入後自動跑一次 extract（setTimeout 推離 effect 同步階段）。
  useEffect(() => {
    if (!autoExtract || extracted || groups.length === 0 || !intake.trim()) return;
    const t = setTimeout(() => void runExtract(), 0);
    return () => clearTimeout(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [autoExtract, groups.length, intake]);

  const addCustom = (name: string, unit: string) => {
    const n = name.trim();
    if (!n) return;
    const u = unit.trim() || "自訂任務";
    setCustomPicks((prev) => [
      ...prev,
      {
        ocs_code: "",
        ocu_code: u, // 同建議職責名 → build_from_picked 併入同一自訂職責
        ocu_name: u,
        ocs_name: "",
        task_code: `custom:${newUid()}`, // 唯一假碼，避免 provenance dedup 撞（catalog 用真 task_code）
        task_name: n,
      },
    ]);
  };

  const proposeCustom = async () => {
    if (!citDesc.trim()) return;
    setCitBusy(true);
    try {
      const res = await structureTask({ description: citDesc.trim(), ocs_codes: ocsCodes });
      setCitProposal(res);
    } catch (e: unknown) {
      onError(e instanceof Error ? e.message : "結構化失敗");
    } finally {
      setCitBusy(false);
    }
  };

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
        const adopt = adopted.has(ukey(g.ocs_code, u.ocu_code));
        for (const t of u.tasks) {
          const k = tkey(g.ocs_code, t.task_code);
          if (alreadyIn.has(k) || !picked.has(k)) continue;
          out.push({
            ocs_code: g.ocs_code,
            ocu_code: u.ocu_code,
            ocu_name: adopt ? u.ocu_name : "", // 不採用 → 職責名留白
            ocs_name: g.ocs_name,
            task_code: t.task_code,
            task_name: t.task_name,
          });
        }
      }
    }
    out.push(...customPicks);
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
          {/* T11：依員工自述 AI 預勾建議任務 */}
          {intake.trim() ? (
            <div className="flex items-center justify-between gap-2 rounded-md border border-violet-200 bg-violet-50 px-3 py-2">
              <span className="text-xs text-violet-800">依你的自述自動預勾可能負責的任務。</span>
              <Button size="sm" variant="outline" className="gap-1.5" disabled={aiBusy} onClick={runExtract}>
                {aiBusy ? <Loader2 className="h-4 w-4 animate-spin" /> : <Sparkles className="h-4 w-4" />}
                {extracted ? "重新預勾" : "AI 預勾"}
              </Button>
            </div>
          ) : null}

          {groups.map((g) => (
            <div key={g.ocs_code}>
              <div className="mb-1 flex items-center gap-2">
                <Badge variant="outline" className="text-xs">{g.ocs_name}</Badge>
                <span className="font-mono text-xs text-muted-foreground">{g.ocs_code}</span>
              </div>
              <div className="space-y-2">
                {g.units.map((u) => {
                  const ids = u.tasks.map((t) => t.task_code);
                  const addable = ids.filter((id) => !alreadyIn.has(tkey(g.ocs_code, id)));
                  const unitDone = addable.length === 0;
                  return (
                    <div key={u.ocu_code} className="rounded-md border">
                      <label className="flex cursor-pointer items-center gap-2 border-b bg-muted/40 px-2 py-1.5 text-sm font-medium">
                        <input
                          type="checkbox"
                          disabled={unitDone}
                          checked={adopted.has(ukey(g.ocs_code, u.ocu_code))}
                          onChange={(e) => toggleUnit(g.ocs_code, u.ocu_code, ids, e.target.checked)}
                        />
                        <span className="font-mono text-xs text-muted-foreground">{u.ocu_code}</span>
                        <span>{u.ocu_name}</span>
                        {unitDone ? <Badge variant="secondary" className="ml-auto text-[10px]">已加入</Badge> : null}
                      </label>
                      <div className="space-y-0.5 p-1.5">
                        {u.tasks.map((t) => {
                          const k = tkey(g.ocs_code, t.task_code);
                          const inDoc = alreadyIn.has(k);
                          return (
                            <label
                              key={t.task_code}
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
                              <span className="font-mono text-xs text-muted-foreground">{t.task_code}</span>
                              <span>{t.task_name}</span>
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

      {/* T11：CIT 補漏 — 清單外的關鍵/棘手任務，一句描述 → structure-task → 新增自訂 */}
      {!isLoading && !isError ? (
        <div className="mt-4 space-y-2 rounded-md border border-dashed p-3">
          <p className="text-sm font-medium">有沒有特別關鍵、清單上沒有的任務？</p>
          {aiCustoms.length > 0 ? (
            <div className="flex flex-wrap gap-1.5">
              {aiCustoms.map((c, i) => (
                <button
                  key={`${c.name}-${i}`}
                  type="button"
                  className="inline-flex items-center gap-1 rounded-full border border-violet-200 bg-violet-50 px-2.5 py-1 text-xs text-violet-700 hover:bg-violet-100"
                  onClick={() => {
                    addCustom(c.name, "自訂任務");
                    setAiCustoms((prev) => prev.filter((_, idx) => idx !== i));
                  }}
                >
                  <Plus className="h-3 w-3" />
                  {c.name}
                </button>
              ))}
            </div>
          ) : null}
          <div className="flex items-center gap-1.5">
            <input
              className="w-full rounded-md border px-2.5 py-1.5 text-sm"
              placeholder="用一句話描述這個任務（例：緊急停機時的故障排除與通報）"
              value={citDesc}
              onChange={(e) => setCitDesc(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter") {
                  e.preventDefault();
                  void proposeCustom();
                }
              }}
            />
            <Button size="sm" variant="outline" className="shrink-0 gap-1" disabled={citBusy || !citDesc.trim()} onClick={proposeCustom}>
              {citBusy ? <Loader2 className="h-4 w-4 animate-spin" /> : <Sparkles className="h-4 w-4" />}
              產生任務
            </Button>
          </div>
          {citProposal ? (
            <div className="flex items-center justify-between gap-2 rounded-md bg-muted/50 px-2.5 py-2 text-sm">
              <span>
                <span className="font-medium">{citProposal.task_name}</span>
                {citProposal.unit_suggestion ? (
                  <span className="text-xs text-muted-foreground">（職責：{citProposal.unit_suggestion}）</span>
                ) : null}
              </span>
              <div className="flex shrink-0 gap-1.5">
                <Button size="sm" variant="ghost" onClick={() => setCitProposal(null)}>捨棄</Button>
                <Button
                  size="sm"
                  onClick={() => {
                    addCustom(citProposal.task_name, citProposal.unit_suggestion);
                    setCitProposal(null);
                    setCitDesc("");
                  }}
                >
                  加入
                </Button>
              </div>
            </div>
          ) : null}
          {customPicks.length > 0 ? (
            <ul className="space-y-1">
              {customPicks.map((c, i) => (
                <li key={c.task_code} className="flex items-center gap-2 text-sm">
                  <Badge variant="secondary" className="text-[10px]">自訂</Badge>
                  <span className="flex-1">{c.task_name}</span>
                  <button
                    type="button"
                    className="text-muted-foreground hover:text-destructive"
                    onClick={() => setCustomPicks((prev) => prev.filter((_, idx) => idx !== i))}
                  >
                    <Trash2 className="h-3.5 w-3.5" />
                  </button>
                </li>
              ))}
            </ul>
          ) : null}
        </div>
      ) : null}

      <div className="mt-4 flex items-center justify-between">
        <span className="text-xs text-muted-foreground">將新增 {picked.size + customPicks.length} 個任務</span>
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
