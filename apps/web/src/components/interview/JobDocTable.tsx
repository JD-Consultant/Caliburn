"use client";

// D27 工作台主表（兩層、可編輯、可拖拉）。職責(unit)→任務(task)，皆可改名/增/刪/
// 拖拉排序；任務可跨職責拖拉。每任務 4 格（產出O/指標P/K/S）點擊開 filler。
// 純呈現+結構編輯：所有變更經 onChange(newDoc) 交回上層 PATCH。
// T8(ADR 0030 追蹤修訂):AI 寫入=文件內 `_pending` 四態(取代 0028 D7 reviewMap/
// evidence 徽章)——條目級綠字/紅刪除線+hover ✓✗?出處卡;✓✗=前端改 doc→PATCH,
// 並無聲記帳 review-events(不觸發 AI)。工具列批量「接受全部(N)/拒絕全部」。
import { useEffect, useMemo, useRef, useState } from "react";
import type { PendingMark } from "@caliburn/ocs-contract";
import type { CompetencyBlock, KnowledgePack, OcsDocument, OcsTask, OptionItem } from "@/types";
import {
  acceptPending,
  addTask,
  addUnit,
  deleteTask,
  deleteUnit,
  listPending,
  rejectPending,
  relocateTask,
  renameTask,
  renameUnit,
  reorderUnits,
  resolveAllPending,
  setAttitudes,
  setKS,
  setOp,
  setTaskLevel,
} from "@/lib/ocsDoc";
import { postReviewEvents } from "@/lib/api";
import { useKnowledge } from "@/hooks/useKnowledge";
import { groupedValueOptions, isOfficialBasis, ownTaskRefs, primaryDefaults, valuePoolOptions } from "@/lib/pack";
import { DETAIL_SLOT_LABELS, HEADER_SLOT_LABELS } from "@/lib/slots";
import { taskUrns } from "@/lib/urn";
import { PendingActions, PrevLine, pendingTextClass, type ReviewDecision } from "./PendingMark";
import { FieldCombobox } from "./fields/FieldCombobox";
import { OfficialMenu } from "./fields/OfficialMenu";
import {
  DndContext,
  PointerSensor,
  closestCenter,
  useSensor,
  useSensors,
  type DragEndEvent,
} from "@dnd-kit/core";
import {
  SortableContext,
  useSortable,
  verticalListSortingStrategy,
} from "@dnd-kit/sortable";
import { CSS } from "@dnd-kit/utilities";
import { Badge } from "@/components/ui/badge";
import { DocHeader } from "./DocHeader";
import { UnitPickerMenu } from "./UnitPickerMenu";
import { DocNotes } from "./DocNotes";
import { TaskPickerMenu } from "./TaskPickerMenu";
import { ChevronDown, GripVertical, Plus, Trash2 } from "lucide-react";

// OPLKS 值格種類（O/P/K/S）。CellTarget/CellFillerPanel 開板流已退役（ADR 0029 §8）。
export type CellKind = "o" | "p" | "k" | "s";

export function firstBlock(task: OcsTask): CompetencyBlock | undefined {
  return task.competency_blocks?.[0];
}

function EditableText({
  value,
  placeholder,
  onCommit,
  className = "",
}: {
  value: string;
  placeholder?: string;
  onCommit: (v: string) => void;
  className?: string;
}) {
  const [draft, setDraft] = useState(value);
  const focused = useRef(false);
  useEffect(() => {
    if (!focused.current) setDraft(value);
  }, [value]);
  return (
    <input
      value={draft}
      placeholder={placeholder}
      onFocus={() => (focused.current = true)}
      onBlur={() => {
        focused.current = false;
        if (draft !== value) onCommit(draft);
      }}
      onKeyDown={(e) => {
        if (e.key === "Enter") e.currentTarget.blur();
      }}
      onChange={(e) => setDraft(e.target.value)}
      className={
        "rounded border border-transparent bg-transparent px-1 py-0.5 hover:border-input focus:border-input focus:bg-background focus:outline-none " +
        className
      }
    />
  );
}

function TaskRow({
  id,
  task,
  unitIdx,
  taskIdx,
  unitUid,
  onReview,
  pack,
  onChange,
  doc,
}: {
  id: string;
  task: OcsTask;
  unitIdx: number;
  taskIdx: number;
  unitUid?: string;
  onReview: (path: string, decision: ReviewDecision) => void;
  pack?: KnowledgePack;
  onChange: (d: OcsDocument) => void;
  doc: OcsDocument;
}) {
  const { attributes, listeners, setNodeRef, transform, transition, isDragging } = useSortable({ id });
  const style = { transform: CSS.Transform.toString(transform), transition, opacity: isDragging ? 0.5 : 1 };
  const block = firstBlock(task);
  const level = block?.competency_level;
  const tc = task.task_codes?.[0];
  const taskNum = (tc?.code ?? "").replace(/^T/i, ""); // O/P 任務範圍碼前綴（O1.1.…）
  // T8:path 文法鏡像後端 docpath(穩定 id 段優先、index 後援)
  const taskPath = `ocs_content.ocu_units.${unitUid ?? unitIdx}.tasks.${task._tid ?? taskIdx}`;
  const taskMark = (task as { _pending?: PendingMark | null })._pending ?? null;
  const details = (task as OcsTask & { details?: Record<string, unknown> }).details ?? {};
  const detailPending =
    (details as { _pending?: Record<string, PendingMark | undefined> })._pending ?? {};
  const detailRows = Object.keys(DETAIL_SLOT_LABELS)
    .map((k) => ({ k, v: details[k], mark: detailPending[k] }))
    .filter((r) => (r.v !== undefined && r.v !== null && r.v !== "") || r.mark);
  const levelMark = (block as { _pending?: { competency_level?: PendingMark | null } } | undefined)
    ?._pending?.competency_level ?? null;
  const reviewItemAt = (kind: "outputs" | "indicators" | "knowledge" | "skills") =>
    (item: { _id?: string }, idx: number, d: ReviewDecision) =>
      onReview(`${taskPath}.competency_blocks.0.${kind}.${item._id ?? idx}`, d);
  // 級別：官方值來自知識包 source_tasks（聯集取第一個非空＝順序1）；
  // fallback 帶官方時記下的 _levelSrc。選中官方值 → 存 _levelSrc（B4，來源必標）。
  const own = pack ? ownTaskRefs(pack, taskUrns(task)) : null;
  const officialLevel = own?.level ?? task._levelSrc?.level ?? null;
  const levelSrc = own?.levelSrc ?? task._levelSrc ?? null;
  const isCustomTask = taskUrns(task).length === 0; // 無官方身分=自訂(手動新增/改過名;spec §2)

  // 各值格(O/P/K/S)的池選項＋官方配套(「選同工作任務」用);own-first 重排對到本任務。
  const forKind = (kind: CellKind): { options: OptionItem[]; defaults: OptionItem[] } => {
    if (!pack || !own) return { options: [], defaults: [] };
    const pool = { o: pack.pools.outputs, p: pack.pools.indicators, k: pack.pools.knowledge, s: pack.pools.skills }[kind];
    const ownKeys = new Set({ o: own.o, p: own.p, k: own.k, s: own.s }[kind]);
    const options = valuePoolOptions(pool, own.pairs);
    return { options, defaults: options.filter((op) => ownKeys.has(op.name)) };
  };
  const oK = forKind("o"), pK = forKind("p"), kK = forKind("k"), sK = forKind("s");

  return (
    <div ref={setNodeRef} style={style} className={
      "group/task rounded-md border bg-background px-3 py-2" +
      (taskMark ? (taskMark.op === "del"
        ? " animate-in fade-in border-red-200 bg-red-50/40 duration-500"
        : " animate-in fade-in border-emerald-200 bg-emerald-50/40 duration-500") : "")
    }>
      <div className="group/pending mb-2 flex items-center gap-1.5">
        <button
          type="button"
          className="cursor-grab text-muted-foreground/60 opacity-0 hover:text-foreground group-hover/task:opacity-100"
          {...attributes}
          {...listeners}
        >
          <GripVertical className="h-4 w-4" />
        </button>
        <span className="font-mono text-xs text-muted-foreground">{tc?.code}</span>
        {taskMark ? (
          // 整任務待審(add=綠/del=紅刪除線):任務名唯讀+✓✗?(去標/還原是筆級決策)
          <span className={"flex-1 text-sm font-semibold " + pendingTextClass(taskMark.op)}>
            {tc?.name ?? ""}
          </span>
        ) : (
        <EditableText
          value={tc?.name ?? ""}
          placeholder="任務名稱"
          onCommit={(v) => onChange(renameTask(doc, unitIdx, taskIdx, v))}
          className="flex-1 text-sm font-semibold"
        />
        )}
        {taskMark ? <PendingActions mark={taskMark} onDecide={(d) => onReview(taskPath, d)} /> : null}
        {isCustomTask ? <span className="shrink-0 rounded bg-amber-100 px-1 text-[10px] text-amber-700" title="自訂任務(無官方來源)">自訂</span> : null}
        <button
          type="button"
          className="text-muted-foreground opacity-0 hover:text-destructive group-hover/task:opacity-100"
          title="刪除此任務"
          onClick={() => onChange(deleteTask(doc, unitIdx, taskIdx))}
        >
          <Trash2 className="h-3.5 w-3.5" />
        </button>
      </div>
      {/* OPLKS 全展開區(spec §7):列序 O→P→L→K→S;▾ 在左欄標籤旁開格選單窗;hover 才見工具 */}
      <div className="space-y-1 pl-6">
        <FieldCombobox gridLayout title="工作產出(O)" layout="list" autoApplyLabel="選同工作任務"
          autoCode={`O${taskNum}.`} value={block?.outputs ?? []}
          options={oK.options} defaults={oK.defaults} onReviewItem={reviewItemAt("outputs")}
          onCommit={(items) => onChange(setOp(doc, unitIdx, taskIdx, items, block?.indicators ?? []))} />
        <FieldCombobox gridLayout title="行為指標(P)" layout="list" autoApplyLabel="選同工作任務"
          autoCode={`P${taskNum}.`}
          value={(block?.indicators ?? []).map((i) => ({ code: i.code, name: i.text, _id: i._id, _src: i._src, _ref: i._ref, _pending: i._pending }))}
          options={pK.options} defaults={pK.defaults} onReviewItem={reviewItemAt("indicators")}
          onCommit={(items) => onChange(setOp(doc, unitIdx, taskIdx, block?.outputs ?? [],
            items.map((i) => ({ code: i.code, text: i.name, _id: i._id, _src: i._src, _ref: i._ref }))))} />
        {/* L 職能級別(每任務;控制單選) */}
        <div className="flex items-start gap-3">
          <div className="flex w-40 shrink-0 items-center gap-1 pt-1">
            <span className="text-sm font-medium">職能級別(L)</span>
            <OfficialMenu
              title="選任務級別"
              autoApplyLabel="選同官方級別"
              trigger={<button type="button" className="inline-flex items-center text-muted-foreground hover:text-foreground" title="選級別"><ChevronDown className="h-4 w-4" /></button>}
              options={[1, 2, 3, 4, 5, 6].map((n) => ({ value: String(n), label: `級別 ${n}`, srcs: officialLevel === n && levelSrc ? [levelSrc] : [] }))}
              selected={level != null ? String(level) : ""}
              onAutoApply={officialLevel != null && levelSrc
                ? () => onChange(setTaskLevel(doc, unitIdx, taskIdx, officialLevel, { ...levelSrc, level: officialLevel }))
                : undefined}
              onPick={(v) => onChange(setTaskLevel(doc, unitIdx, taskIdx, v,
                officialLevel != null && Number(v) === officialLevel && levelSrc ? { ...levelSrc, level: officialLevel } : undefined))}
            />
          </div>
          <div className="group/pending flex min-w-0 flex-1 items-center gap-1.5 pt-1 text-sm">
            {levelMark ? (
              <>
                <span className={pendingTextClass(levelMark.op)}>{level != null ? level : "—"}</span>
                <PrevLine mark={levelMark} />
                <PendingActions mark={levelMark}
                  onDecide={(d) => onReview(`${taskPath}.competency_blocks.0.competency_level`, d)} />
              </>
            ) : (level != null ? level : "—")}
          </div>
        </div>
        <FieldCombobox gridLayout title="職能內涵(K)" layout="list" autoApplyLabel="選同工作任務"
          autoCode="K" value={block?.knowledge ?? []}
          options={kK.options} defaults={kK.defaults} onReviewItem={reviewItemAt("knowledge")}
          onCommit={(items) => onChange(setKS(doc, unitIdx, taskIdx, "knowledge", items))} />
        <FieldCombobox gridLayout title="職能內涵(S)" layout="list" autoApplyLabel="選同工作任務"
          autoCode="S" value={block?.skills ?? []}
          options={sK.options} defaults={sK.defaults} onReviewItem={reviewItemAt("skills")}
          onCommit={(items) => onChange(setKS(doc, unitIdx, taskIdx, "skills", items))} />
      </div>
      {/* 訪談細節(details 11 槽):書記寫入的主要內容。chips 呈現;T8 待審=
          `_pending` 四態(綠=add/mod、紅刪除線=del)+舊值副行+hover ✓✗?。 */}
      {detailRows.length > 0 ? (
        <div className="mt-2 flex flex-wrap gap-1.5 pl-6">
          {detailRows.map(({ k, v, mark }) => (
            <span
              key={k}
              className={
                "group/pending inline-flex items-center gap-1 rounded px-1.5 py-0.5 text-[11px] " +
                (mark
                  ? (mark.op === "del"
                    ? "animate-in fade-in bg-red-50 text-red-600 ring-1 ring-red-200 duration-500"
                    : "animate-in fade-in bg-emerald-50 text-emerald-700 ring-1 ring-emerald-200 duration-500")
                  : "bg-muted text-muted-foreground")
              }
            >
              <span className="font-medium">{DETAIL_SLOT_LABELS[k]}</span>
              <span className={"max-w-48 truncate" + (mark?.op === "del" ? " line-through decoration-red-400" : "")}>
                {String(v ?? "")}
              </span>
              {mark ? <PrevLine mark={mark} /> : null}
              {mark ? (
                <PendingActions mark={mark} onDecide={(d) => onReview(`${taskPath}.details.${k}`, d)} />
              ) : null}
            </span>
          ))}
        </div>
      ) : null}
    </div>
  );
}

function UnitRow({
  id,
  unit,
  unitIdx,
  onReview,
  pack,
  onChange,
  doc,
}: {
  id: string;
  unit: OcsDocument["ocs_content"]["ocu_units"][number];
  unitIdx: number;
  onReview: (path: string, decision: ReviewDecision) => void;
  pack?: KnowledgePack;
  onChange: (d: OcsDocument) => void;
  doc: OcsDocument;
}) {
  const { attributes, listeners, setNodeRef, transform, transition, isDragging } = useSortable({ id });
  const style = { transform: CSS.Transform.toString(transform), transition, opacity: isDragging ? 0.5 : 1 };
  const tasks = unit.tasks ?? [];
  const taskIds = tasks.map((t) => `t:${t._tid}`);
  const isCustomUnit = !(unit._refs?.length) && !unit.source?.ocs_code; // 無官方來源=自訂(spec §2)
  const unitPath = `ocs_content.ocu_units.${unit._uid ?? unitIdx}`;
  const unitMark = (unit as { _pending?: PendingMark | null })._pending ?? null;

  return (
    <div ref={setNodeRef} style={style} className={
      "rounded-lg border bg-background" +
      (unitMark ? (unitMark.op === "del"
        ? " animate-in fade-in border-red-200 duration-500"
        : " animate-in fade-in border-emerald-200 duration-500") : "")
    }>
      <div className="group/pending flex items-center gap-1.5 border-b bg-muted/40 px-3 py-2">
        <button type="button" className="cursor-grab text-muted-foreground/60 hover:text-foreground" {...attributes} {...listeners}>
          <GripVertical className="h-4 w-4" />
        </button>
        <Badge variant="outline" className="font-mono text-xs">{unit.ocu_code}</Badge>
        {unitMark ? (
          <span className={"flex-1 text-sm font-medium " + pendingTextClass(unitMark.op)}>
            {unit.ocu_name ?? ""}
          </span>
        ) : (
        <EditableText
          value={unit.ocu_name ?? ""}
          placeholder="職責名稱（點擊命名）"
          onCommit={(v) => onChange(renameUnit(doc, unitIdx, v))}
          className="flex-1 text-sm font-medium"
        />
        )}
        {unitMark ? <PendingActions mark={unitMark} onDecide={(d) => onReview(unitPath, d)} /> : null}
        {isCustomUnit ? <span className="shrink-0 rounded bg-amber-100 px-1 text-[10px] text-amber-700" title="自訂職責(無官方來源)">自訂</span> : null}
        {unit.source?.occupation_name ? (
          <span className="text-xs text-muted-foreground">來源：{unit.source.occupation_name}</span>
        ) : null}
        <button type="button" className="text-muted-foreground hover:text-destructive" onClick={() => onChange(deleteUnit(doc, unitIdx))}>
          <Trash2 className="h-4 w-4" />
        </button>
      </div>
      <div className="space-y-2 p-2">
        <SortableContext items={taskIds} strategy={verticalListSortingStrategy}>
          {tasks.map((task, ti) => (
            <TaskRow
              key={task._tid}
              id={`t:${task._tid}`}
              task={task}
              unitIdx={unitIdx}
              taskIdx={ti}
              unitUid={unit._uid}
              onReview={onReview}
              pack={pack}
              onChange={onChange}
              doc={doc}
            />
          ))}
        </SortableContext>
        <div className="flex items-center gap-1.5">
          {/* 選任務(獨立選單窗)＝任務大池（預勾自己的、可借用）；＋＝手動空白任務 */}
          <TaskPickerMenu document={doc} pack={pack} unitIdx={unitIdx} onChange={onChange} />
          <button
            type="button"
            className="inline-flex items-center gap-1 rounded-md border border-dashed px-2.5 py-1.5 text-xs text-muted-foreground hover:text-foreground"
            onClick={() => onChange(addTask(doc, unitIdx))}
          >
            <Plus className="h-3.5 w-3.5" />
            新增任務
          </button>
        </div>
      </div>
    </div>
  );
}

function AttitudeBlock({
  document: doc,
  pack,
  onChange,
  onReview,
}: {
  document: OcsDocument;
  pack?: KnowledgePack;
  onChange: (d: OcsDocument) => void;
  onReview: (path: string, decision: ReviewDecision) => void;
}) {
  // 態度池 key=name（A5：文件自編碼跨職類必撞，不當 key）；選單序號顯示+引用行。
  // defaults=主基準來源(spec 2026-07-04 §4;主基準空白/自訂不套)。
  // 相似比對(ADR 0022):defaults/自動套跑在**平選項**(鐵律);分群只變顯示清單。
  const primary = doc.ocs_profile?.ocs_code ?? "";
  const flat = pack ? valuePoolOptions(pack.pools.attitudes) : [];
  const options = pack ? groupedValueOptions(flat, pack.similarity?.attitude, primary) : [];
  const defaults = pack && isOfficialBasis(pack, primary) ? primaryDefaults(flat, primary) : [];
  return (
    <div className="rounded-lg border bg-background p-4">
      <FieldCombobox
        label="選態度"
        title="職能內涵（A=態度，全職類共用）"
        layout="list"
        autoCode="A"
        autoApplyLabel="選同職能基準"
        value={doc.ocs_attitude?.attitudes ?? []}
        options={options}
        defaults={defaults}
        onReviewItem={(it, idx, d) => onReview(`ocs_attitude.attitudes.${it._id ?? idx}`, d)}
        onCommit={(items) => onChange(setAttitudes(doc, items))}
      />
    </div>
  );
}

export function JobDocTable({
  document,
  profileId,
  onChange,
}: {
  document: OcsDocument;
  profileId: string;
  onChange: (d: OcsDocument) => void;
}) {
  const units = document.ocs_content?.ocu_units ?? [];
  const unitIds = units.map((u) => `u:${u._uid}`);
  // 知識包（ADR 0021）：任務級別官方值/來源（TaskRow）。選過職類才有資料。
  const { data: pack } = useKnowledge(profileId, !!document.ocs_profile?.ocs_code);
  // T8(ADR 0030):AI 待審=文件內 `_pending`(取代 evidence/reviewMap 資料流)。
  const pendingEntries = useMemo(() => listPending(document), [document]);
  const headerPendings = pendingEntries.filter((e) => e.path.startsWith("ocs_profile."));

  // ✓/✗:前端改 doc(去標/還原+renumber)→ onChange 走既有 PATCH;
  // 並無聲記帳 review-events(§6.3:記錄不觸發 AI;失敗不擋編輯)。
  const review = (path: string, decision: ReviewDecision) => {
    onChange(decision === "accepted" ? acceptPending(document, path) : rejectPending(document, path));
    postReviewEvents(profileId, [{ doc_path: path, decision }]).catch(() => {});
  };
  const reviewAll = (decision: "accepted" | "rejected") => {
    onChange(resolveAllPending(document, decision === "accepted" ? "accept" : "reject"));
    postReviewEvents(profileId, pendingEntries.map((e) => ({
      doc_path: e.path,
      decision: decision === "accepted" ? ("accepted" as const) : ("batch_rejected" as const),
    }))).catch(() => {});
  };

  const sensors = useSensors(useSensor(PointerSensor, { activationConstraint: { distance: 6 } }));

  // 由穩定 id（u:<uid> / t:<tid>）查出目前索引。t<0 表示這是職責本身/容器。
  const resolve = (id: string): { u: number; t: number } | null => {
    if (id.startsWith("u:")) {
      const u = units.findIndex((x) => x._uid === id.slice(2));
      return u < 0 ? null : { u, t: -1 };
    }
    if (id.startsWith("t:")) {
      const tid = id.slice(2);
      for (let u = 0; u < units.length; u++) {
        const t = (units[u].tasks ?? []).findIndex((x) => x._tid === tid);
        if (t >= 0) return { u, t };
      }
    }
    return null;
  };

  const onDragEnd = (e: DragEndEvent) => {
    const a = String(e.active.id);
    const A = resolve(a);
    const O = e.over ? resolve(String(e.over.id)) : null;
    if (!A || !O) return;

    if (a.startsWith("u:")) {
      // 拖職責：不論 over 是職責或其底下任務，都換算成該任務所屬職責來重排。
      if (A.u !== O.u) onChange(reorderUnits(document, A.u, O.u));
      return;
    }
    // 拖任務：over 是任務→精準插入；是職責容器→接到該職責尾端。
    if (O.t >= 0) {
      onChange(relocateTask(document, A.u, A.t, O.u, O.t));
    } else {
      onChange(relocateTask(document, A.u, A.t, O.u, -1));
    }
  };

  return (
    <div className="space-y-5">
      {/* T8 工具列:待審計數+批量「接受全部(N)/拒絕全部」常駐(待審>0);
          表頭槽(主基準/工作描述/級別)的待審在此以 chips 呈現(✓✗?)。 */}
      {pendingEntries.length > 0 ? (
        <div id="ai-pending-bar" className="flex flex-wrap items-center gap-2 rounded-lg border border-emerald-200 bg-emerald-50/50 px-3 py-2 text-sm">
          <span className="font-medium text-emerald-800">AI 待審 {pendingEntries.length} 筆</span>
          {headerPendings.map((e) => {
            const slot = e.path.split(".").pop() ?? "";
            const shown = e.mark.value ?? e.mark.prev;
            return (
              <span key={e.path}
                className="group/pending inline-flex items-center gap-1 rounded bg-background px-1.5 py-0.5 text-[11px] ring-1 ring-emerald-200">
                <span className="font-medium">{HEADER_SLOT_LABELS[slot] ?? slot}</span>
                <span className={"max-w-40 truncate " + pendingTextClass(e.op)}>
                  {shown != null ? String(shown) : e.op}
                </span>
                <PendingActions mark={e.mark} onDecide={(d) => review(e.path, d)} />
              </span>
            );
          })}
          <div className="ml-auto flex items-center gap-2">
            <button type="button"
              className="rounded border border-emerald-600 bg-emerald-600 px-2 py-1 text-xs text-white hover:bg-emerald-700"
              onClick={() => reviewAll("accepted")}>
              接受全部({pendingEntries.length})
            </button>
            <button type="button"
              className="rounded border px-2 py-1 text-xs text-muted-foreground hover:text-destructive"
              onClick={() => reviewAll("rejected")}>
              拒絕全部
            </button>
          </div>
        </div>
      ) : null}

      {/* 官方職能基準表頭（可編輯） */}
      <DocHeader document={document} profileId={profileId} onChange={onChange} />

      {/* 單元 → 任務（可拖拉） */}
      {units.length === 0 ? (
        <div className="rounded-lg border border-dashed p-8 text-center text-sm text-muted-foreground">
          尚無任務。上方〔選職類〕→〔選職責〕帶入職責，再從職責列〔選任務〕挑任務；或〔＋新增職責〕手動建立。
        </div>
      ) : (
        <DndContext sensors={sensors} collisionDetection={closestCenter} onDragEnd={onDragEnd}>
          <SortableContext items={unitIds} strategy={verticalListSortingStrategy}>
            <div className="space-y-4">
              {units.map((unit, ui) => (
                <UnitRow
                  key={unit._uid}
                  id={`u:${unit._uid}`}
                  unit={unit}
                  unitIdx={ui}
                  onReview={review}
                  pack={pack}
                  onChange={onChange}
                  doc={document}
                />
              ))}
            </div>
          </SortableContext>
        </DndContext>
      )}

      {/* 表格底部:〔選主要職責〕(參考;搬自頂欄,ADR 0029 §6)與〔＋新增職責〕(自訂)並排 */}
      <div className="flex flex-wrap items-center gap-2">
        <UnitPickerMenu document={document} pack={pack} disabled={!pack} onChange={onChange} />
        <button
          type="button"
          className="inline-flex items-center gap-1 rounded-md border border-dashed px-3 py-2 text-sm text-muted-foreground hover:text-foreground"
          onClick={() => onChange(addUnit(document))}
        >
          <Plus className="h-4 w-4" />
          新增職責
        </button>
      </div>

      {/* 職能內涵（A=attitude 態度） */}
      <AttitudeBlock document={document} pack={pack} onChange={onChange} onReview={review} />

      {/* 說明與補充事項（可編輯） */}
      <DocNotes document={document} profileId={profileId} onChange={onChange} />
    </div>
  );
}
