"use client";

// D27〔選任務〕modal——遞迴選單模式（ADR 0021 / spec §5）：
// 職責選單＝units 池全部（序號＋引用行；預勾＝含主基準來源的職責＋其官方任務聯集）；
// 展開職責 → 任務選單＝tasks 池**全部**（不過濾不分組；自己的預勾、其餘可勾＝借用）；
// 已在文件（任何職責下）的任務標「已加入」不可再勾。確認＝前端文件編輯（addFromPool）
// → autosave PATCH（資料流決策①：單一寫入路徑；document:buildTasks 不再使用）。
import { useEffect, useMemo, useState } from "react";
import { ChevronDown, Loader2, Plus, Sparkles, Trash2 } from "lucide-react";
import { useKnowledge } from "@/hooks/useKnowledge";
import { taskRows, unitRows, type TaskRowVM, type UnitRowVM } from "@/lib/pack";
import { addFromPool, type PoolPick } from "@/lib/ocsDoc";
import { taskUrns } from "@/lib/urn";
import { extractTasks, structureTask } from "@/lib/api";
import type { OcsDocument } from "@/types";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Modal } from "./OccupationPicker";
import { SourceLine } from "./fields/SourceLine";

export function TaskCuratePanel({
  profileId,
  currentDoc,
  intake = "",
  autoExtract = false,
  onApply,
  onClose,
  onError,
}: {
  profileId: string;
  currentDoc: OcsDocument | undefined;
  // D28 T11：員工自述（job_summary）餵 extract-tasks 預勾；intake 流程進來時 autoExtract。
  intake?: string;
  autoExtract?: boolean;
  onApply: (d: OcsDocument) => void;
  onClose: () => void;
  onError: (msg: string) => void;
}) {
  const { data: pack, isLoading, isError } = useKnowledge(profileId, true);
  const units = useMemo(() => (pack ? unitRows(pack) : []), [pack]);
  const tasks = useMemo(() => (pack ? taskRows(pack) : []), [pack]);
  const taskByKey = useMemo(() => new Map(tasks.map((t) => [t.name, t])), [tasks]);
  const primary = pack?.occupation_details[0]?.ocs_code ?? "";
  const ocsCodes = useMemo(() => (pack?.occupation_details ?? []).map((d) => d.ocs_code), [pack]);

  // 已在文件（任何職責下）的任務：provenance/_refs URN 命中池列 → 標「已加入」不可再勾。
  const alreadyIn = useMemo(() => {
    const s = new Set<string>();
    for (const u of currentDoc?.ocs_content?.ocu_units ?? [])
      for (const t of u.tasks ?? []) for (const urn of taskUrns(t)) s.add(urn);
    return s;
  }, [currentDoc]);
  const rowInDoc = (row: TaskRowVM) => row.urns.some((u) => alreadyIn.has(u));

  // 預勾（spec 預勾統一規則：主基準(順序1)來源的職責列＋其官方任務聯集）。
  const defaults = useMemo(() => {
    const m = new Map<string, Set<string>>();
    if (!primary) return m;
    for (const u of units) {
      if (!u.srcs.some((s) => s.ocs_code === primary)) continue;
      const picks = new Set(u.ownTaskKeys.filter((k) => {
        const row = taskByKey.get(k);
        return row && !rowInDoc(row);
      }));
      if (picks.size) m.set(u.name, picks);
    }
    return m;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [units, taskByKey, primary, alreadyIn]);

  // 暫存勾選：職責 key → 該職責底下勾的任務 key（derived state：null＝未動過＝顯示預勾；
  // 「自動勾選」鈕＝setStaged(null) 回預設）。同一任務列勾在別職責 → 他處 disabled
  // （選單開在誰底下就進誰；勾任務＝職責自動採用）。
  const [stagedState, setStaged] = useState<Map<string, Set<string>> | null>(null);
  const staged = stagedState ?? defaults;
  const [openUnit, setOpenUnit] = useState<string | null>(null);
  const stagedUnitOf = (taskKey: string): string | null => {
    for (const [uk, set] of staged) if (set.has(taskKey)) return uk;
    return null;
  };
  // updater 內以「當下暫存(或預設)」為底深拷貝（defaults 是 memo，不可就地改）。
  const copyOf = (base: Map<string, Set<string>>) =>
    new Map([...base].map(([k, v]) => [k, new Set(v)] as const));

  const toggleUnit = (u: UnitRowVM, on: boolean) =>
    setStaged((prev) => {
      const next = copyOf(prev ?? defaults);
      if (!on) {
        next.delete(u.name);
        return next;
      }
      const stagedElsewhere = (k: string) => {
        for (const [uk, set] of next) if (uk !== u.name && set.has(k)) return true;
        return false;
      };
      const set = next.get(u.name) ?? new Set<string>();
      for (const k of u.ownTaskKeys) {
        const row = taskByKey.get(k);
        if (row && !rowInDoc(row) && !stagedElsewhere(k)) set.add(k);
      }
      next.set(u.name, set);
      return next;
    });

  const toggleTask = (unitName: string, taskKey: string) =>
    setStaged((prev) => {
      const next = copyOf(prev ?? defaults);
      const set = next.get(unitName) ?? new Set<string>();
      if (set.has(taskKey)) set.delete(taskKey);
      else set.add(taskKey); // 勾任務＝職責自動採用
      if (set.size === 0) next.delete(unitName);
      else next.set(unitName, set);
      return next;
    });

  // D28 T11：extract-tasks 預勾 + CIT 補漏自訂任務。
  const [aiBusy, setAiBusy] = useState(false);
  const [extracted, setExtracted] = useState(false);
  const [aiCustoms, setAiCustoms] = useState<{ name: string }[]>([]); // 候選自訂（AI 列）
  const [customPicks, setCustomPicks] = useState<{ ocu_name: string; task_name: string }[]>([]);
  const [citDesc, setCitDesc] = useState("");
  const [citBusy, setCitBusy] = useState(false);
  const [citProposal, setCitProposal] = useState<{ task_name: string; unit_suggestion: string } | null>(null);

  const runExtract = async () => {
    if (!intake.trim() || !pack || ocsCodes.length === 0) return;
    setAiBusy(true);
    setExtracted(true);
    try {
      const res = await extractTasks({ intake, ocs_codes: ocsCodes });
      // suggested_task_ids＝各 OCS 的 task_code → URN → 池列，放回它自己的職責（自動採用）。
      setStaged((prev) => {
        const next = copyOf(prev ?? defaults);
        const stagedSomewhere = (k: string) => {
          for (const set of next.values()) if (set.has(k)) return true;
          return false;
        };
        for (const id of res.suggested_task_ids) {
          for (const oc of ocsCodes) {
            const st = pack.source_tasks[`ocs:${oc}:T:${id}`];
            if (!st?.task_name || !st.ocu_name) continue;
            const row = taskByKey.get(st.task_name);
            if (!row || rowInDoc(row) || stagedSomewhere(st.task_name)) continue;
            const set = new Set(next.get(st.ocu_name) ?? []);
            set.add(st.task_name);
            next.set(st.ocu_name, set);
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

  // intake 流程進來：知識包載入後自動跑一次 extract（setTimeout 推離 effect 同步階段）。
  useEffect(() => {
    if (!autoExtract || extracted || !pack || !intake.trim()) return;
    const t = setTimeout(() => void runExtract(), 0);
    return () => clearTimeout(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [autoExtract, pack, intake]);

  const addCustom = (name: string, unit: string) => {
    const n = name.trim();
    if (!n) return;
    setCustomPicks((prev) => [...prev, { ocu_name: unit.trim() || "自訂任務", task_name: n }]);
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

  // 確認＝前端文件編輯：職責/任務照池序 append；provenance 優先取「與本職責同職業」的來源。
  const confirm = () => {
    const picks: PoolPick[] = [];
    for (const u of units) {
      const set = staged.get(u.name);
      if (!set?.size) continue;
      const unitCodes = new Set(u.srcs.map((s) => s.ocs_code));
      const pickTasks: PoolPick["tasks"] = [];
      for (const t of tasks) {
        if (!set.has(t.name)) continue;
        const pref = t.srcs.find((s) => unitCodes.has(s.ocs_code)) ?? t.srcs[0];
        pickTasks.push({
          name: t.name,
          srcs: t.srcs,
          provenance: { ocs_code: pref?.ocs_code ?? "", task_code: pref?.task_code ?? "" },
        });
      }
      picks.push({ unit: { name: u.name, srcs: u.srcs }, tasks: pickTasks });
    }
    for (const c of customPicks) {
      picks.push({
        unit: { name: c.ocu_name, srcs: [] },
        tasks: [{ name: c.task_name, srcs: [], provenance: { ocs_code: "", task_code: "" } }],
      });
    }
    if (picks.length === 0) {
      onClose();
      return;
    }
    if (!currentDoc) {
      onError("文件尚未載入");
      return;
    }
    onApply(addFromPool(currentDoc, picks));
    onClose();
  };

  const stagedCount = [...staged.values()].reduce((a, s) => a + s.size, 0);

  return (
    <Modal title="選擇任務（勾職責＝帶入其官方任務；展開可跨職責借用）" onClose={onClose}>
      {isLoading ? (
        <div className="h-32 animate-pulse rounded bg-muted" />
      ) : isError ? (
        <p className="text-sm text-destructive">知識包載入失敗（indexer 未連線？）。</p>
      ) : units.length === 0 ? (
        <p className="text-sm text-muted-foreground">沒有候選任務。請先〔選職類〕。</p>
      ) : (
        <>
          <div className="mb-2 flex items-center justify-between gap-2">
            {/* T11：依員工自述 AI 預勾建議任務 */}
            {intake.trim() ? (
              <div className="flex min-w-0 flex-1 items-center justify-between gap-2 rounded-md border border-violet-200 bg-violet-50 px-3 py-2">
                <span className="truncate text-xs text-violet-800">依你的自述自動預勾可能負責的任務。</span>
                <Button size="sm" variant="outline" className="shrink-0 gap-1.5" disabled={aiBusy} onClick={runExtract}>
                  {aiBusy ? <Loader2 className="h-4 w-4 animate-spin" /> : <Sparkles className="h-4 w-4" />}
                  {extracted ? "重新預勾" : "AI 預勾"}
                </Button>
              </div>
            ) : <span />}
            <Button size="sm" variant="outline" className="shrink-0"
              title="重套預設：主基準（順序1）的職責與任務"
              onClick={() => setStaged(null)}>
              自動勾選
            </Button>
          </div>

          <div className="max-h-[60vh] space-y-2 overflow-y-auto">
            {units.map((u, ui) => {
              const set = staged.get(u.name);
              const isOpen = openUnit === u.name;
              return (
                <div key={u.name} className="rounded-md border">
                  <div className="flex items-start gap-2 border-b bg-muted/40 px-2 py-1.5 text-sm font-medium">
                    <input
                      type="checkbox"
                      className="mt-1"
                      checked={!!set?.size}
                      onChange={(e) => toggleUnit(u, e.target.checked)}
                    />
                    <button type="button" className="min-w-0 flex-1 text-left" onClick={() => setOpenUnit(isOpen ? null : u.name)}>
                      <div className="flex items-center gap-1.5">
                        <span className="font-mono text-xs text-muted-foreground">{ui + 1}.</span>
                        <span>{u.name}</span>
                        {set?.size ? <Badge variant="secondary" className="ml-1 text-[10px]">已勾 {set.size}</Badge> : null}
                        <ChevronDown className={"ml-auto h-3.5 w-3.5 shrink-0 transition-transform " + (isOpen ? "rotate-180" : "")} />
                      </div>
                      <SourceLine srcs={u.srcs} />
                    </button>
                  </div>
                  {isOpen ? (
                    <div className="space-y-0.5 p-1.5">
                      {tasks.map((t, ti) => {
                        const inDoc = rowInDoc(t);
                        const elsewhere = stagedUnitOf(t.name);
                        const here = !!set?.has(t.name);
                        const disabled = inDoc || (!!elsewhere && elsewhere !== u.name);
                        const isOwn = u.ownTaskKeys.includes(t.name);
                        return (
                          <label
                            key={t.name}
                            className={
                              "flex items-start gap-2 rounded px-2 py-1 text-sm " +
                              (disabled ? "opacity-50" : "cursor-pointer hover:bg-muted/50")
                            }
                          >
                            <input
                              type="checkbox"
                              className="mt-1"
                              disabled={disabled}
                              checked={inDoc || here}
                              onChange={() => toggleTask(u.name, t.name)}
                            />
                            <span className="mt-0.5 font-mono text-xs text-muted-foreground">{ti + 1}.</span>
                            <div className="min-w-0 flex-1">
                              <div className="flex items-center gap-1.5">
                                <span>{t.name}</span>
                                {isOwn ? null : <Badge variant="outline" className="text-[10px]">借用</Badge>}
                                {inDoc ? <span className="ml-auto text-[10px] text-muted-foreground">已加入</span> : null}
                                {!inDoc && elsewhere && elsewhere !== u.name ? (
                                  <span className="ml-auto text-[10px] text-muted-foreground">已勾於「{elsewhere}」</span>
                                ) : null}
                              </div>
                              <SourceLine srcs={t.srcs} />
                            </div>
                          </label>
                        );
                      })}
                    </div>
                  ) : null}
                </div>
              );
            })}
          </div>
        </>
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
                <li key={`${c.task_name}-${i}`} className="flex items-center gap-2 text-sm">
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
        <span className="text-xs text-muted-foreground">將新增 {stagedCount + customPicks.length} 個任務</span>
        <div className="flex gap-2">
          <Button variant="ghost" onClick={onClose}>取消</Button>
          <Button onClick={confirm}>加入文件</Button>
        </div>
      </div>
    </Modal>
  );
}
