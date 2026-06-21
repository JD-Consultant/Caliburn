"use client";

// D27 各格 filler（T7）：點表格某格 → 開此面板。O/P = 手打兩清單（產出 + 行為
// 指標）；K/S/A = catalog 候選選單（勾/加/改）。儲存時用 lib/ocsDoc 就地更新整份
// 文件後交回上層 PATCH。不碰 CopilotKit。由上層以 key={target} 重新掛載，狀態
// 用 useState initializer 從當前文件帶入。
import { useState } from "react";
import type { CodeName, Indicator, KsaPool, OcsDocument } from "@/types";
import { getBlock, setAttitudes, setKS, setOp } from "@/lib/ocsDoc";
import type { CellTarget } from "./JobDocTable";
import { Button } from "@/components/ui/button";
import { Plus, Trash2, X } from "lucide-react";

function taskName(doc: OcsDocument, unitIdx: number, taskIdx: number): string {
  const tc = doc.ocs_content?.ocu_units?.[unitIdx]?.tasks?.[taskIdx]?.task_codes?.[0];
  return tc?.name || "任務";
}

// ── O/P 手打兩清單 ───────────────────────────────────────────────────────────
function OpEditor({
  initialOutputs,
  initialIndicators,
  onSubmit,
  saving,
}: {
  initialOutputs: CodeName[];
  initialIndicators: Indicator[];
  onSubmit: (outputs: CodeName[], indicators: Indicator[]) => void;
  saving: boolean;
}) {
  const [outputs, setOutputs] = useState<CodeName[]>(() =>
    initialOutputs.map((o) => ({ ...o })),
  );
  const [indicators, setIndicators] = useState<Indicator[]>(() =>
    initialIndicators.map((i) => ({ ...i })),
  );

  const save = () =>
    onSubmit(
      outputs.map((o) => ({ ...o, name: o.name.trim() })).filter((o) => o.name),
      indicators.map((i) => ({ ...i, text: i.text.trim() })).filter((i) => i.text),
    );

  return (
    <div className="space-y-4">
      <ListEditor
        title="工作產出 O"
        placeholder="例：系統導入前後作業流程比較表"
        rows={outputs.map((o) => o.name)}
        onChange={(rows) =>
          setOutputs(rows.map((name, idx) => ({ code: outputs[idx]?.code ?? "", name })))
        }
      />
      <ListEditor
        title="行為指標 P"
        placeholder="例：能分析系統導入前後之作業模式差異"
        rows={indicators.map((i) => i.text)}
        onChange={(rows) =>
          setIndicators(rows.map((text, idx) => ({ code: indicators[idx]?.code ?? "", text })))
        }
      />
      <SaveBar saving={saving} onSave={save} />
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
  const set = (idx: number, val: string) =>
    onChange(rows.map((r, i) => (i === idx ? val : r)));
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
            <button
              type="button"
              className="shrink-0 rounded-md p-1.5 text-muted-foreground hover:text-destructive"
              onClick={() => remove(idx)}
            >
              <Trash2 className="h-4 w-4" />
            </button>
          </div>
        ))}
        <button
          type="button"
          className="inline-flex items-center gap-1 rounded-md border border-dashed px-2.5 py-1.5 text-xs text-muted-foreground hover:text-foreground"
          onClick={add}
        >
          <Plus className="h-3.5 w-3.5" />
          新增一列
        </button>
      </div>
    </div>
  );
}

// ── K/S/A 候選選單 ───────────────────────────────────────────────────────────
function CandidatePicker({
  candidates,
  initialSelected,
  onSubmit,
  saving,
}: {
  candidates: CodeName[];
  initialSelected: CodeName[];
  onSubmit: (items: CodeName[]) => void;
  saving: boolean;
}) {
  const [selected, setSelected] = useState<CodeName[]>(() =>
    initialSelected.map((s) => ({ ...s })),
  );
  const [custom, setCustom] = useState("");

  const isSel = (c: CodeName) =>
    selected.some((s) => (c.code ? s.code === c.code : s.name === c.name));
  const toggle = (c: CodeName) =>
    setSelected((prev) =>
      isSel(c)
        ? prev.filter((s) => (c.code ? s.code !== c.code : s.name !== c.name))
        : [...prev, { ...c }],
    );
  const addCustom = () => {
    const name = custom.trim();
    if (!name || selected.some((s) => s.name === name)) {
      setCustom("");
      return;
    }
    setSelected((prev) => [...prev, { code: "", name }]);
    setCustom("");
  };
  // 已選但不在候選池的自訂項目（讓人能移除）。
  const customSelected = selected.filter(
    (s) => !candidates.some((c) => (s.code ? c.code === s.code : c.name === s.name)),
  );

  return (
    <div className="space-y-3">
      {candidates.length === 0 ? (
        <p className="text-xs text-muted-foreground">
          目前沒有候選（indexer 未連線或此職類無資料）。可在下方自行新增。
        </p>
      ) : (
        <div className="max-h-72 space-y-1 overflow-y-auto rounded-md border p-2">
          {candidates.map((c, idx) => (
            <label
              key={`${c.code || c.name}-${idx}`}
              className="flex cursor-pointer items-start gap-2 rounded px-1.5 py-1 text-sm hover:bg-muted/50"
            >
              <input
                type="checkbox"
                className="mt-0.5"
                checked={isSel(c)}
                onChange={() => toggle(c)}
              />
              {c.code ? (
                <span className="font-mono text-xs text-muted-foreground">{c.code}</span>
              ) : null}
              <span>{c.name}</span>
            </label>
          ))}
        </div>
      )}

      {customSelected.length > 0 ? (
        <div className="flex flex-wrap gap-1.5">
          {customSelected.map((s, idx) => (
            <span
              key={`${s.name}-${idx}`}
              className="inline-flex items-center gap-1 rounded-full bg-muted px-2 py-0.5 text-xs"
            >
              {s.name}
              <button
                type="button"
                onClick={() => setSelected((prev) => prev.filter((x) => x.name !== s.name))}
              >
                <X className="h-3 w-3" />
              </button>
            </span>
          ))}
        </div>
      ) : null}

      <div className="flex items-center gap-1.5">
        <input
          className="w-full rounded-md border px-2.5 py-1.5 text-sm"
          placeholder="自行新增（按 Enter）"
          value={custom}
          onChange={(e) => setCustom(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter") {
              e.preventDefault();
              addCustom();
            }
          }}
        />
        <Button type="button" size="sm" variant="outline" onClick={addCustom}>
          新增
        </Button>
      </div>

      <p className="text-xs text-muted-foreground">已選 {selected.length} 項</p>
      <SaveBar saving={saving} onSave={() => onSubmit(selected)} />
    </div>
  );
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
    body = (
      <CandidatePicker
        candidates={pool.attitudes}
        initialSelected={document.ocs_attitude?.attitudes ?? []}
        saving={saving}
        onSubmit={(items) => onSave(setAttitudes(document, items))}
      />
    );
  } else {
    const { unitIdx, taskIdx } = target;
    const block = getBlock(document, unitIdx, taskIdx);
    const tn = taskName(document, unitIdx, taskIdx);
    if (target.kind === "op") {
      title = `${tn}：產出 O / 行為指標 P`;
      body = (
        <OpEditor
          initialOutputs={block?.outputs ?? []}
          initialIndicators={block?.indicators ?? []}
          saving={saving}
          onSubmit={(outputs, indicators) =>
            onSave(setOp(document, unitIdx, taskIdx, outputs, indicators))
          }
        />
      );
    } else {
      const field = target.kind === "k" ? "knowledge" : "skills";
      title = `${tn}：${target.kind === "k" ? "知識 K" : "技能 S"}`;
      body = (
        <CandidatePicker
          candidates={target.kind === "k" ? pool.knowledge : pool.skills}
          initialSelected={(block?.[field] as CodeName[]) ?? []}
          saving={saving}
          onSubmit={(items) => onSave(setKS(document, unitIdx, taskIdx, field, items))}
        />
      );
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex justify-end bg-black/30" onClick={onClose}>
      <div
        className="h-full w-full max-w-md overflow-y-auto bg-background p-5 shadow-xl"
        onClick={(e) => e.stopPropagation()}
      >
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
