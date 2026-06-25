"use client";

// D27 各格 filler（T7，修訂）：O 與 P 各自獨立面板（手打清單）；K/S/A 為候選選單
// ——顯示代號、依代號排序、可「新增」(只打名稱，代號自動 K01/S01/A01 遞增) 並進
// 全域池(_pool，跨任務共用) 再打勾。儲存即 PATCH。不碰 CopilotKit。
import { useState } from "react";
import type { CodeName, Indicator, KsaPool, KsaPoolItem, OcsDocument } from "@/types";
import { getBlock, mergePool, setAttitudes, setKS, setOp } from "@/lib/ocsDoc";
import type { CellTarget } from "./JobDocTable";
import { Button } from "@/components/ui/button";
import { Plus, Trash2, X } from "lucide-react";

function taskName(doc: OcsDocument, unitIdx: number, taskIdx: number): string {
  const tc = doc.ocs_content?.ocu_units?.[unitIdx]?.tasks?.[taskIdx]?.task_codes?.[0];
  return tc?.name || "任務";
}

function byCode(a: CodeName, b: CodeName): number {
  if (!a.code && !b.code) return a.name.localeCompare(b.name);
  if (!a.code) return 1;
  if (!b.code) return -1;
  return a.code.localeCompare(b.code, undefined, { numeric: true });
}

function SaveBar({ saving, onSave }: { saving: boolean; onSave: () => void }) {
  return (
    <div className="flex justify-end pt-1">
      <Button size="sm" disabled={saving} onClick={onSave}>
        {saving ? "儲存中…" : "儲存"}
      </Button>
    </div>
  );
}

function ListEditor({
  title,
  placeholder,
  rows,
  onChange,
}: {
  title: string;
  placeholder: string;
  rows: string[];
  onChange: (rows: string[]) => void;
}) {
  const set = (idx: number, val: string) => onChange(rows.map((r, i) => (i === idx ? val : r)));
  const remove = (idx: number) => onChange(rows.filter((_, i) => i !== idx));
  const add = () => onChange([...rows, ""]);
  return (
    <div>
      <p className="mb-1.5 text-sm font-medium">{title}</p>
      <div className="space-y-1.5">
        {rows.map((r, idx) => (
          <div key={idx} className="flex items-center gap-1.5">
            <input
              className="w-full rounded-md border px-2.5 py-1.5 text-sm"
              placeholder={placeholder}
              value={r}
              onChange={(e) => set(idx, e.target.value)}
            />
            <button type="button" className="shrink-0 rounded-md p-1.5 text-muted-foreground hover:text-destructive" onClick={() => remove(idx)}>
              <Trash2 className="h-4 w-4" />
            </button>
          </div>
        ))}
        <button type="button" className="inline-flex items-center gap-1 rounded-md border border-dashed px-2.5 py-1.5 text-xs text-muted-foreground hover:text-foreground" onClick={add}>
          <Plus className="h-3.5 w-3.5" />
          新增一列
        </button>
      </div>
    </div>
  );
}

// ── O：工作產出（手打） ──────────────────────────────────────────────────────
function OutputEditor({ initial, onSubmit, saving }: { initial: CodeName[]; onSubmit: (o: CodeName[]) => void; saving: boolean }) {
  const [items, setItems] = useState<CodeName[]>(() => initial.map((o) => ({ ...o })));
  return (
    <div className="space-y-4">
      <ListEditor
        title="工作產出 O"
        placeholder="例：系統導入前後作業流程比較表"
        rows={items.map((o) => o.name)}
        onChange={(rows) => setItems(rows.map((name, i) => ({ code: items[i]?.code ?? "", name })))}
      />
      <SaveBar saving={saving} onSave={() => onSubmit(items.map((o) => ({ ...o, name: o.name.trim() })).filter((o) => o.name))} />
    </div>
  );
}

// ── P：行為指標（手打） ──────────────────────────────────────────────────────
function IndicatorEditor({ initial, onSubmit, saving }: { initial: Indicator[]; onSubmit: (p: Indicator[]) => void; saving: boolean }) {
  const [items, setItems] = useState<Indicator[]>(() => initial.map((i) => ({ ...i })));
  return (
    <div className="space-y-4">
      <ListEditor
        title="行為指標 P"
        placeholder="例：能分析系統導入前後之作業模式差異"
        rows={items.map((i) => i.text)}
        onChange={(rows) => setItems(rows.map((text, i) => ({ code: items[i]?.code ?? "", text })))}
      />
      <SaveBar saving={saving} onSave={() => onSubmit(items.map((i) => ({ ...i, text: i.text.trim() })).filter((i) => i.text))} />
    </div>
  );
}

// ── K/S/A：候選選單（顯示代號、排序、新增進全域池） ──────────────────────────
function Picker({
  doc,
  kind,
  catalog,
  unitIdx,
  taskIdx,
  saving,
  onSave,
}: {
  doc: OcsDocument;
  kind: "knowledge" | "skills" | "attitudes";
  catalog: KsaPoolItem[];
  unitIdx: number;
  taskIdx: number;
  saving: boolean;
  onSave: (d: OcsDocument) => void;
}) {
  const prefix = kind === "knowledge" ? "K" : kind === "skills" ? "S" : "A";
  const poolExtra = doc._pool?.[kind] ?? [];
  // catalog + 全域池，去重 by code（無 code 以 name 區分）。
  const seen = new Set<string>();
  const base: KsaPoolItem[] = [];
  for (const c of [...catalog, ...poolExtra]) {
    const k = c.code || `name:${c.name}`;
    if (!seen.has(k)) {
      seen.add(k);
      base.push(c);
    }
  }

  const initialSelected =
    kind === "attitudes"
      ? doc.ocs_attitude?.attitudes ?? []
      : (getBlock(doc, unitIdx, taskIdx)?.[kind] ?? []);

  const [selected, setSelected] = useState<CodeName[]>(() => initialSelected.map((s) => ({ ...s })));
  const [newItems, setNewItems] = useState<CodeName[]>([]);
  const [name, setName] = useState("");

  const candidates = [...base, ...newItems].sort(byCode);

  const nextCode = (): string => {
    let max = 0;
    for (const c of [...base, ...newItems]) {
      const m = /^[KSA](\d+)$/.exec(c.code || "");
      if (m) max = Math.max(max, parseInt(m[1], 10));
    }
    return `${prefix}${String(max + 1).padStart(2, "0")}`;
  };

  const isSel = (c: CodeName) => selected.some((s) => (c.code ? s.code === c.code : s.name === c.name));
  const toggle = (c: CodeName) =>
    setSelected((prev) => (isSel(c) ? prev.filter((s) => (c.code ? s.code !== c.code : s.name !== c.name)) : [...prev, { ...c }]));

  const add = () => {
    const n = name.trim();
    if (!n) return;
    setNewItems((prev) => [...prev, { code: nextCode(), name: n }]);
    setName("");
  };

  const save = () => {
    let d = kind === "attitudes" ? setAttitudes(doc, selected) : setKS(doc, unitIdx, taskIdx, kind, selected);
    if (newItems.length) d = mergePool(d, kind, newItems);
    onSave(d);
  };

  return (
    <div className="space-y-3">
      {candidates.length === 0 ? (
        <p className="text-xs text-muted-foreground">目前沒有候選（indexer 未連線或此職類無資料）。可用下方新增。</p>
      ) : (
        <div className="max-h-72 space-y-1 overflow-y-auto rounded-md border p-2">
          {candidates.map((c, idx) => (
            <label key={`${c.code || c.name}-${idx}`} className="flex cursor-pointer items-start gap-2 rounded px-1.5 py-1 text-sm hover:bg-muted/50">
              <input type="checkbox" className="mt-0.5" checked={isSel(c)} onChange={() => toggle(c)} />
              {c.code ? <span className="font-mono text-xs text-muted-foreground">{c.code}</span> : null}
              <span>{c.name}</span>
              {(c as KsaPoolItem).sources && (c as KsaPoolItem).sources!.length > 0 ? (
                <span className="ml-auto shrink-0 rounded bg-sky-100 px-1 py-0.5 text-[10px] text-sky-700"
                      title={"來自：" + (c as KsaPoolItem).sources!.join("、")}>
                  共 {(c as KsaPoolItem).sources!.length}
                </span>
              ) : null}
            </label>
          ))}
        </div>
      )}

      <div className="flex items-center gap-1.5">
        <input
          className="w-full rounded-md border px-2.5 py-1.5 text-sm"
          placeholder={`新增${prefix}（只打名稱，代號自動；按 Enter）`}
          value={name}
          onChange={(e) => setName(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter") {
              e.preventDefault();
              add();
            }
          }}
        />
        <Button type="button" size="sm" variant="outline" onClick={add}>新增</Button>
      </div>

      <p className="text-xs text-muted-foreground">已選 {selected.length} 項{newItems.length ? `；新增 ${newItems.length} 項（存檔後進全域池）` : ""}</p>
      <SaveBar saving={saving} onSave={save} />
    </div>
  );
}

export function CellFillerPanel({
  document,
  target,
  pool,
  saving,
  onSave,
  onClose,
}: {
  document: OcsDocument;
  target: CellTarget;
  pool: KsaPool;
  saving: boolean;
  onSave: (doc: OcsDocument) => void;
  onClose: () => void;
}) {
  let title = "";
  let body: React.ReactNode = null;

  if (target.kind === "a") {
    title = "全域態度 A";
    body = <Picker doc={document} kind="attitudes" catalog={pool.attitudes} unitIdx={-1} taskIdx={-1} saving={saving} onSave={onSave} />;
  } else {
    const { unitIdx, taskIdx } = target;
    const block = getBlock(document, unitIdx, taskIdx);
    const tn = taskName(document, unitIdx, taskIdx);
    if (target.kind === "o") {
      title = `${tn}：工作產出 O`;
      body = <OutputEditor initial={block?.outputs ?? []} saving={saving} onSubmit={(o) => onSave(setOp(document, unitIdx, taskIdx, o, block?.indicators ?? []))} />;
    } else if (target.kind === "p") {
      title = `${tn}：行為指標 P`;
      body = <IndicatorEditor initial={block?.indicators ?? []} saving={saving} onSubmit={(p) => onSave(setOp(document, unitIdx, taskIdx, block?.outputs ?? [], p))} />;
    } else {
      const kind = target.kind === "k" ? "knowledge" : "skills";
      title = `${tn}：${target.kind === "k" ? "知識 K" : "技能 S"}`;
      body = <Picker doc={document} kind={kind} catalog={target.kind === "k" ? pool.knowledge : pool.skills} unitIdx={unitIdx} taskIdx={taskIdx} saving={saving} onSave={onSave} />;
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex justify-end bg-black/30" onClick={onClose}>
      <div className="h-full w-full max-w-md overflow-y-auto bg-background p-5 shadow-xl" onClick={(e) => e.stopPropagation()}>
        <div className="mb-4 flex items-center justify-between">
          <h3 className="text-sm font-semibold">{title}</h3>
          <button type="button" onClick={onClose} className="text-muted-foreground hover:text-foreground">
            <X className="h-5 w-5" />
          </button>
        </div>
        {body}
      </div>
    </div>
  );
}
