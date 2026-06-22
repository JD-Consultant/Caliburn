"use client";

// D28 ✨ 面板＝核心 AI 入口（單任務）。5W2H 卡片（必填 1 格＋選填 CIT＋收合細節）→
// 「產生草稿」→ 呼 /ai/draft-op + /ai/recommend-ks（帶 note）→ 暫存（O/P 可改、K/S
// 勾選+來源/理由）→「套用」走現有 setOp/setKS + PATCH。太薄→clarify 一輪追問。
// 工作筆記隨套用存進 task._notes（finalize/export 後端剝除）。不碰 CopilotKit。
import { useEffect, useMemo, useState } from "react";
import { ChevronDown, ChevronRight, Layers, Loader2, Plus, Sparkles, Trash2, X } from "lucide-react";
import type {
  IndicatorSuggestion,
  KsSuggestion,
  OcsDocument,
  OutputSuggestion,
} from "@/types";
import { clarify, draftOP, recommendKS } from "@/lib/api";
import { getTaskNotes, setKS, setOp, setTaskNotes } from "@/lib/ocsDoc";
import { Button } from "@/components/ui/button";

type CheckedKs = KsSuggestion & { checked: boolean };

type Staged = {
  outputs: OutputSuggestion[];
  indicators: IndicatorSuggestion[];
  knowledge: CheckedKs[];
  skills: CheckedKs[];
};

function SourceBadge({ source }: { source: "catalog" | "ai" }) {
  return (
    <span
      className={
        "shrink-0 rounded px-1 py-0.5 text-[10px] font-medium " +
        (source === "catalog"
          ? "bg-sky-100 text-sky-700"
          : "bg-violet-100 text-violet-700")
      }
      title={source === "catalog" ? "來自職能基準目錄" : "AI 依你的描述生成"}
    >
      {source === "catalog" ? "目錄" : "AI"}
    </span>
  );
}

// O/P 共用的可編輯清單（帶來源徽章）。
function StagedList({
  title,
  rows,
  placeholder,
  onChange,
}: {
  title: string;
  rows: { text: string; source: "catalog" | "ai" }[];
  placeholder: string;
  onChange: (rows: { text: string; source: "catalog" | "ai" }[]) => void;
}) {
  const set = (i: number, v: string) =>
    onChange(rows.map((r, idx) => (idx === i ? { ...r, text: v } : r)));
  const remove = (i: number) => onChange(rows.filter((_, idx) => idx !== i));
  const add = () => onChange([...rows, { text: "", source: "ai" }]);
  return (
    <div>
      <p className="mb-1.5 text-sm font-medium">{title}</p>
      <div className="space-y-1.5">
        {rows.map((r, i) => (
          <div key={i} className="flex items-center gap-1.5">
            <SourceBadge source={r.source} />
            <input
              className="w-full rounded-md border px-2.5 py-1.5 text-sm"
              placeholder={placeholder}
              value={r.text}
              onChange={(e) => set(i, e.target.value)}
            />
            <button
              type="button"
              className="shrink-0 rounded-md p-1.5 text-muted-foreground hover:text-destructive"
              onClick={() => remove(i)}
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

// K/S 勾選清單（顯示來源 + 理由）。
function StagedPicker({
  title,
  items,
  onToggle,
}: {
  title: string;
  items: CheckedKs[];
  onToggle: (i: number) => void;
}) {
  return (
    <div>
      <p className="mb-1.5 text-sm font-medium">{title}</p>
      {items.length === 0 ? (
        <p className="text-xs text-muted-foreground">（無建議）</p>
      ) : (
        <div className="space-y-1 rounded-md border p-2">
          {items.map((it, i) => (
            <label
              key={`${it.code || it.name}-${i}`}
              className="flex cursor-pointer items-start gap-2 rounded px-1.5 py-1 text-sm hover:bg-muted/50"
            >
              <input
                type="checkbox"
                className="mt-0.5"
                checked={it.checked}
                onChange={() => onToggle(i)}
              />
              {it.code ? (
                <span className="mt-0.5 shrink-0 font-mono text-xs text-muted-foreground">{it.code}</span>
              ) : null}
              <span className="flex-1">
                <span className="flex items-center gap-1.5">
                  <span>{it.name}</span>
                  <SourceBadge source={it.source} />
                </span>
                {it.reason ? (
                  <span className="block text-xs text-muted-foreground">理由：{it.reason}</span>
                ) : null}
              </span>
            </label>
          ))}
        </div>
      )}
    </div>
  );
}

export function AiTaskPanel({
  document,
  profileId,
  unitIdx,
  taskIdx,
  saving,
  autoCatalog = false,
  onApply,
  onClose,
}: {
  document: OcsDocument;
  profileId: string;
  unitIdx: number;
  taskIdx: number;
  saving: boolean;
  // T12 次要任務「一鍵帶 catalog」：開啟即以空 note 自動產生 → 回 catalog 官方
  // O/P/K/S（source=catalog），跳過 5W2H 卡片與 clarify，使用者瞄一眼採用/略過。
  autoCatalog?: boolean;
  onApply: (doc: OcsDocument) => void;
  onClose: () => void;
}) {
  const task = document.ocs_content?.ocu_units?.[unitIdx]?.tasks?.[taskIdx];
  const taskKey = task?.task_codes?.[0]?.code ?? "";
  const taskName = task?.task_codes?.[0]?.name || "任務";

  // 5W2H 卡片欄位（必填只 1 格；其餘選填、收合）。
  const existingNotes = useMemo(() => getTaskNotes(document, unitIdx, taskIdx), [document, unitIdx, taskIdx]);
  const [whatOutput, setWhatOutput] = useState(existingNotes);
  const [cit, setCit] = useState("");
  const [when, setWhen] = useState("");
  const [who, setWho] = useState("");
  const [how, setHow] = useState("");
  const [supplement, setSupplement] = useState(""); // clarify 一輪後的補充
  const [showDetails, setShowDetails] = useState(false);

  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [staged, setStaged] = useState<Staged | null>(null);
  const [clarifyQ, setClarifyQ] = useState<string | null>(null);
  const [clarifyAsked, setClarifyAsked] = useState(false);
  const [clarifyAnswer, setClarifyAnswer] = useState("");

  const buildNote = (): string => {
    const parts: string[] = [];
    if (whatOutput.trim()) parts.push(`做什麼／產出：${whatOutput.trim()}`);
    if (cit.trim()) parts.push(`做得好的一次（實例）：${cit.trim()}`);
    if (when.trim()) parts.push(`何時／情境：${when.trim()}`);
    if (who.trim()) parts.push(`對象：${who.trim()}`);
    if (how.trim()) parts.push(`工具／方法：${how.trim()}`);
    if (supplement.trim()) parts.push(`補充：${supplement.trim()}`);
    return parts.join("\n");
  };

  const generate = async (noteArg?: string, skipClarify = false) => {
    const note = noteArg ?? buildNote();
    if (!taskKey) {
      setErr("此任務尚未儲存（無任務代碼），請先關閉面板讓變更自動儲存後再試。");
      return;
    }
    const askClarify = !skipClarify && !autoCatalog && !clarifyAsked;
    setBusy(true);
    setErr(null);
    try {
      const [op, ks, cl] = await Promise.all([
        draftOP({ profile_id: profileId, task_key: taskKey, note }),
        recommendKS({ profile_id: profileId, task_key: taskKey, note }),
        askClarify ? clarify({ task: taskName, note }) : Promise.resolve({ question: null }),
      ]);
      setStaged({
        outputs: op.outputs,
        indicators: op.indicators,
        knowledge: ks.knowledge.map((k) => ({ ...k, checked: true })),
        skills: ks.skills.map((s) => ({ ...s, checked: true })),
      });
      setClarifyQ(cl.question);
    } catch (e: unknown) {
      setErr(e instanceof Error ? e.message : "產生失敗");
    } finally {
      setBusy(false);
    }
  };

  // T12：catalog 模式開啟即自動帶入官方內容（空 note，跳過 clarify），只跑一次。
  // 用 setTimeout 把 setState 推離 effect 同步階段（避免 set-state-in-effect 連鎖渲染）。
  useEffect(() => {
    if (!autoCatalog) return;
    const t = setTimeout(() => void generate("", true), 0);
    return () => clearTimeout(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const refineOnce = async () => {
    setClarifyAsked(true);
    setClarifyQ(null);
    setSupplement(clarifyAnswer);
    const note = buildNote() + (clarifyAnswer.trim() ? `\n補充：${clarifyAnswer.trim()}` : "");
    await generate(note);
  };

  const setAllChecked = (checked: boolean) =>
    setStaged((s) =>
      s
        ? {
            ...s,
            knowledge: s.knowledge.map((k) => ({ ...k, checked })),
            skills: s.skills.map((k) => ({ ...k, checked })),
          }
        : s,
    );

  const apply = () => {
    if (!staged) return;
    let d = setOp(
      document,
      unitIdx,
      taskIdx,
      staged.outputs.map((o) => ({ code: "", name: o.name.trim() })).filter((o) => o.name),
      staged.indicators.map((i) => ({ code: "", text: i.text.trim() })).filter((i) => i.text),
    );
    d = setKS(
      d,
      unitIdx,
      taskIdx,
      "knowledge",
      staged.knowledge.filter((k) => k.checked).map((k) => ({ code: k.code, name: k.name })),
    );
    d = setKS(
      d,
      unitIdx,
      taskIdx,
      "skills",
      staged.skills.filter((k) => k.checked).map((k) => ({ code: k.code, name: k.name })),
    );
    d = setTaskNotes(d, unitIdx, taskIdx, buildNote());
    onApply(d);
  };

  return (
    <div className="fixed inset-0 z-50 flex justify-end bg-black/30" onClick={onClose}>
      <div
        className="h-full w-full max-w-lg overflow-y-auto bg-background p-5 shadow-xl"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="mb-4 flex items-center justify-between">
          <h3 className="flex items-center gap-1.5 text-sm font-semibold">
            {autoCatalog ? (
              <>
                <Layers className="h-4 w-4 text-sky-500" />
                一鍵帶入 catalog：{taskName}
              </>
            ) : (
              <>
                <Sparkles className="h-4 w-4 text-violet-500" />
                ✨ AI 協助填寫：{taskName}
              </>
            )}
          </h3>
          <button type="button" onClick={onClose} className="text-muted-foreground hover:text-foreground">
            <X className="h-5 w-5" />
          </button>
        </div>

        {err ? (
          <div className="mb-3 rounded-md border border-destructive/30 bg-destructive/10 px-3 py-2 text-xs text-destructive">
            {err}
          </div>
        ) : null}

        {/* ── catalog 模式：略過 5W2H，僅顯示說明 + 重新帶入 ── */}
        {autoCatalog ? (
          <div className="space-y-2 rounded-lg border bg-muted/20 p-3">
            <p className="text-xs text-muted-foreground">
              直接帶入此任務在職能基準目錄的官方產出 O／指標 P／知識 K／技能 S。瞄一眼後採用或略過。
            </p>
            <Button size="sm" variant="outline" className="w-full gap-1.5" disabled={busy} onClick={() => generate("", true)}>
              {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : <Layers className="h-4 w-4" />}
              重新帶入
            </Button>
          </div>
        ) : null}

        {/* ── 5W2H 卡片（✨ 模式） ── */}
        {!autoCatalog ? (
        <div className="space-y-3 rounded-lg border bg-muted/20 p-3">
          <div>
            <label className="mb-1 block text-sm font-medium">
              這個任務你做什麼、產出什麼？<span className="text-destructive">*</span>
            </label>
            <textarea
              className="w-full rounded-md border px-2.5 py-1.5 text-sm"
              rows={3}
              placeholder="例：每月彙整各部門用電數據，產出節能分析報表給管理層"
              value={whatOutput}
              onChange={(e) => setWhatOutput(e.target.value)}
            />
          </div>
          <div>
            <label className="mb-1 block text-sm font-medium">做得好的一次（實例，選填）</label>
            <textarea
              className="w-full rounded-md border px-2.5 py-1.5 text-sm"
              rows={2}
              placeholder="舉一個實際做得好的例子，AI 會更準"
              value={cit}
              onChange={(e) => setCit(e.target.value)}
            />
          </div>
          <button
            type="button"
            className="inline-flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground"
            onClick={() => setShowDetails((v) => !v)}
          >
            {showDetails ? <ChevronDown className="h-3.5 w-3.5" /> : <ChevronRight className="h-3.5 w-3.5" />}
            更多細節（選填，填越多 AI 越準）
          </button>
          {showDetails ? (
            <div className="space-y-2">
              <input className="w-full rounded-md border px-2.5 py-1.5 text-sm" placeholder="何時／多常／情境" value={when} onChange={(e) => setWhen(e.target.value)} />
              <input className="w-full rounded-md border px-2.5 py-1.5 text-sm" placeholder="對象（服務／協作對象）" value={who} onChange={(e) => setWho(e.target.value)} />
              <input className="w-full rounded-md border px-2.5 py-1.5 text-sm" placeholder="工具／方法／步驟" value={how} onChange={(e) => setHow(e.target.value)} />
            </div>
          ) : null}
          <Button size="sm" className="w-full gap-1.5" disabled={busy || !whatOutput.trim()} onClick={() => generate()}>
            {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : <Sparkles className="h-4 w-4" />}
            {staged ? "重新產生" : "產生草稿"}
          </Button>
        </div>
        ) : null}

        {/* ── clarify 追問（最多一輪） ── */}
        {clarifyQ ? (
          <div className="mt-3 rounded-lg border border-amber-200 bg-amber-50 p-3">
            <p className="mb-1.5 text-sm text-amber-800">💡 AI 想多了解：{clarifyQ}</p>
            <textarea
              className="w-full rounded-md border px-2.5 py-1.5 text-sm"
              rows={2}
              placeholder="補充說明（選填）"
              value={clarifyAnswer}
              onChange={(e) => setClarifyAnswer(e.target.value)}
            />
            <div className="mt-1.5 flex justify-end gap-2">
              <Button size="sm" variant="ghost" onClick={() => setClarifyQ(null)}>略過</Button>
              <Button size="sm" variant="outline" disabled={busy} onClick={refineOnce}>補充並重新產生</Button>
            </div>
          </div>
        ) : null}

        {/* ── 暫存（提議，可改/可勾） ── */}
        {staged ? (
          <div className="mt-4 space-y-4">
            <p className="rounded-md bg-muted px-2.5 py-1.5 text-xs text-muted-foreground">
              AI 建議，可能有誤，未自動儲存，由你決定。
            </p>
            <StagedList
              title="工作產出 O"
              placeholder="產出物名稱"
              rows={staged.outputs.map((o) => ({ text: o.name, source: o.source }))}
              onChange={(rows) =>
                setStaged((s) => (s ? { ...s, outputs: rows.map((r) => ({ name: r.text, source: r.source })) } : s))
              }
            />
            <StagedList
              title="行為指標 P"
              placeholder="可觀察、可衡量的指標"
              rows={staged.indicators.map((i) => ({ text: i.text, source: i.source }))}
              onChange={(rows) =>
                setStaged((s) => (s ? { ...s, indicators: rows.map((r) => ({ text: r.text, source: r.source })) } : s))
              }
            />
            <StagedPicker
              title="知識 K"
              items={staged.knowledge}
              onToggle={(i) =>
                setStaged((s) =>
                  s ? { ...s, knowledge: s.knowledge.map((k, idx) => (idx === i ? { ...k, checked: !k.checked } : k)) } : s,
                )
              }
            />
            <StagedPicker
              title="技能 S"
              items={staged.skills}
              onToggle={(i) =>
                setStaged((s) =>
                  s ? { ...s, skills: s.skills.map((k, idx) => (idx === i ? { ...k, checked: !k.checked } : k)) } : s,
                )
              }
            />

            <div className="flex flex-wrap items-center justify-between gap-2 border-t pt-3">
              <div className="flex gap-2">
                <Button size="sm" variant="ghost" onClick={() => setAllChecked(true)}>全部採用</Button>
                <Button size="sm" variant="ghost" onClick={() => setAllChecked(false)}>全部捨棄</Button>
              </div>
              <Button size="sm" disabled={saving} onClick={apply}>
                {saving ? "套用中…" : "套用到文件"}
              </Button>
            </div>
          </div>
        ) : null}
      </div>
    </div>
  );
}
