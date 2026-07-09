"use client";

// D27 工作台主表（兩層、可編輯、可拖拉）。職責(unit)→任務(task)，皆可改名/增/刪/
// 拖拉排序；任務可跨職責拖拉。每任務 4 格（產出O/指標P/K/S）點擊開 filler。
// 純呈現+結構編輯：所有變更經 onChange(newDoc) 交回上層 PATCH。不碰 CopilotKit。
// 0028 D7(追蹤修訂):AI 直寫(evidence.review=pending)在**同格**標記——O/P/K/S 格
// 加 AI 徽章+hover 引文;訪談細節(details 11 槽)以 chips 呈現(原本無呈現位=隱形)。
import { useEffect, useMemo, useRef, useState } from "react";
import type { CompetencyBlock, KnowledgePack, OcsDocument, OcsTask } from "@/types";
import {
  addTask,
  addUnit,
  deleteTask,
  deleteUnit,
  relocateTask,
  renameTask,
  renameUnit,
  reorderUnits,
  setAttitudes,
  setTaskLevel,
} from "@/lib/ocsDoc";
import { useInterview } from "@/hooks/useInterview";
import { useKnowledge } from "@/hooks/useKnowledge";
import { groupedValueOptions, isOfficialBasis, ownTaskRefs, primaryDefaults, valuePoolOptions } from "@/lib/pack";
import { buildReviewMap, DETAIL_SLOT_LABELS, taskMarks, type ReviewMark } from "@/lib/reviewMap";
import { taskUrns } from "@/lib/urn";
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
import { DocNotes } from "./DocNotes";
import { TaskPickerMenu } from "./TaskPickerMenu";
import { Check, ChevronDown, GripVertical, Pencil, Plus, Trash2 } from "lucide-react";

export type CellKind = "o" | "p" | "k" | "s";
export type CellTarget = { kind: CellKind; unitIdx: number; taskIdx: number };

export function firstBlock(task: OcsTask): CompetencyBlock | undefined {
  return task.competency_blocks?.[0];
}

function count(arr: unknown[] | undefined): number {
  return Array.isArray(arr) ? arr.length : 0;
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

function Cell({
  label,
  filled,
  n,
  onClick,
  mark,
}: {
  label: string;
  filled: boolean;
  n: number;
  onClick: () => void;
  mark?: ReviewMark;      // 0028 D7:AI 直寫待審 → 同格標記(徽章+hover 引文)
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      title={mark ? `AI 依你的話寫入(待確認):「${mark.quote}」` : undefined}
      className={
        "flex items-center gap-1.5 rounded-md border px-2 py-1 text-xs transition-colors " +
        (filled
          ? (mark
              ? "border-sky-300 bg-sky-50 text-sky-800 ring-1 ring-sky-200 hover:bg-sky-100"
              : "border-emerald-200 bg-emerald-50 text-emerald-700 hover:bg-emerald-100")
          : "border-dashed border-muted-foreground/30 text-muted-foreground hover:border-foreground/40 hover:text-foreground")
      }
    >
      {filled ? <Check className="h-3 w-3" /> : <Pencil className="h-3 w-3" />}
      <span className="font-medium">{label}</span>
      {filled ? <span className="tabular-nums opacity-70">{n}</span> : <span>點此填</span>}
      {mark ? <span className="rounded bg-sky-600 px-1 text-[9px] leading-4 text-white">AI</span> : null}
    </button>
  );
}

function TaskRow({
  id,
  task,
  unitIdx,
  taskIdx,
  unitUid,
  reviewMap,
  pack,
  onCell,
  onChange,
  doc,
}: {
  id: string;
  task: OcsTask;
  unitIdx: number;
  taskIdx: number;
  unitUid?: string;
  reviewMap: Map<string, ReviewMark>;
  pack?: KnowledgePack;
  onCell: (t: CellTarget) => void;
  onChange: (d: OcsDocument) => void;
  doc: OcsDocument;
}) {
  const { attributes, listeners, setNodeRef, transform, transition, isDragging } = useSortable({ id });
  const style = { transform: CSS.Transform.toString(transform), transition, opacity: isDragging ? 0.5 : 1 };
  const block = firstBlock(task);
  const level = block?.competency_level;
  const tc = task.task_codes?.[0];
  // 0028 D7:此任務的待審標記(path 文法鏡像後端:uid 形優先、index 形後援)
  const marks = taskMarks(reviewMap, [
    `ocs_content.ocu_units.${unitUid ?? unitIdx}.tasks.${task._tid ?? taskIdx}`,
    `ocs_content.ocu_units.${unitIdx}.tasks.${taskIdx}`,
  ]);
  const details = (task as OcsTask & { details?: Record<string, unknown> }).details ?? {};
  const detailRows = Object.keys(DETAIL_SLOT_LABELS)
    .map((k) => ({ k, v: details[k], mark: marks.details[k] }))
    .filter((r) => r.v !== undefined && r.v !== null && r.v !== "");
  // 級別：官方值來自知識包 source_tasks（聯集取第一個非空＝順序1）；
  // fallback 帶官方時記下的 _levelSrc。選中官方值 → 存 _levelSrc（B4，來源必標）。
  const own = pack ? ownTaskRefs(pack, taskUrns(task)) : null;
  const officialLevel = own?.level ?? task._levelSrc?.level ?? null;
  const levelSrc = own?.levelSrc ?? task._levelSrc ?? null;
  const isCustomTask = taskUrns(task).length === 0; // 無官方身分=自訂(手動新增/改過名;spec §2)

  return (
    <div ref={setNodeRef} style={style} className="rounded-md border bg-background px-3 py-2">
      <div className="mb-2 flex items-center gap-1.5">
        <button
          type="button"
          className="cursor-grab text-muted-foreground/60 hover:text-foreground"
          {...attributes}
          {...listeners}
        >
          <GripVertical className="h-4 w-4" />
        </button>
        <span className="font-mono text-xs text-muted-foreground">{tc?.code}</span>
        <EditableText
          value={tc?.name ?? ""}
          placeholder="任務名稱"
          onCommit={(v) => onChange(renameTask(doc, unitIdx, taskIdx, v))}
          className="flex-1 text-sm font-medium"
        />
        {isCustomTask ? <span className="shrink-0 rounded bg-amber-100 px-1 text-[10px] text-amber-700" title="自訂任務(無官方來源)">自訂</span> : null}
        <OfficialMenu
          trigger={
            <button type="button" className="inline-flex items-center gap-0.5 rounded border px-1.5 py-0.5 text-xs text-muted-foreground hover:text-foreground" title="任務級別（可改；下拉顯示官方來源）">
              級別 {level != null ? level : "—"}<ChevronDown className="h-3 w-3" />
            </button>
          }
          options={[1, 2, 3, 4, 5, 6].map((n) => ({
            value: String(n),
            label: `級別 ${n}`,
            srcs: officialLevel === n && levelSrc ? [levelSrc] : [],
          }))}
          selected={level != null ? String(level) : ""}
          onAutoApply={officialLevel != null && levelSrc
            ? () => onChange(setTaskLevel(doc, unitIdx, taskIdx, officialLevel, { ...levelSrc, level: officialLevel }))
            : undefined}
          onPick={(v) => onChange(setTaskLevel(doc, unitIdx, taskIdx, v,
            officialLevel != null && Number(v) === officialLevel && levelSrc
              ? { ...levelSrc, level: officialLevel } : undefined))}
        />
        <button
          type="button"
          className="text-muted-foreground hover:text-destructive"
          onClick={() => onChange(deleteTask(doc, unitIdx, taskIdx))}
        >
          <Trash2 className="h-3.5 w-3.5" />
        </button>
      </div>
      <div className="flex flex-wrap gap-2 pl-6">
        <Cell label="產出 O" filled={count(block?.outputs) > 0} n={count(block?.outputs)} mark={marks.cells.outputs} onClick={() => onCell({ kind: "o", unitIdx, taskIdx })} />
        <Cell label="指標 P" filled={count(block?.indicators) > 0} n={count(block?.indicators)} mark={marks.cells.indicators} onClick={() => onCell({ kind: "p", unitIdx, taskIdx })} />
        <Cell label="知識 K" filled={count(block?.knowledge) > 0} n={count(block?.knowledge)} mark={marks.cells.knowledge} onClick={() => onCell({ kind: "k", unitIdx, taskIdx })} />
        <Cell label="技能 S" filled={count(block?.skills) > 0} n={count(block?.skills)} mark={marks.cells.skills} onClick={() => onCell({ kind: "s", unitIdx, taskIdx })} />
      </div>
      {/* 訪談細節(details 11 槽;0028 D7):書記寫入的主要內容,原本在表格**沒有呈現位**
          =隱形。chips 呈現;AI 待審=藍框+徽章+hover 引文,人可見可查。 */}
      {detailRows.length > 0 ? (
        <div className="mt-2 flex flex-wrap gap-1.5 pl-6">
          {detailRows.map(({ k, v, mark }) => (
            <span
              key={k}
              title={mark ? `AI 依你的話寫入(待確認):「${mark.quote}」` : undefined}
              className={
                "inline-flex items-center gap-1 rounded px-1.5 py-0.5 text-[11px] " +
                (mark ? "bg-sky-50 text-sky-800 ring-1 ring-sky-200" : "bg-muted text-muted-foreground")
              }
            >
              <span className="font-medium">{DETAIL_SLOT_LABELS[k]}</span>
              <span className="max-w-48 truncate">{String(v)}</span>
              {mark ? <span className="rounded bg-sky-600 px-1 text-[9px] leading-4 text-white">AI</span> : null}
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
  reviewMap,
  pack,
  onCell,
  onChange,
  doc,
}: {
  id: string;
  unit: OcsDocument["ocs_content"]["ocu_units"][number];
  unitIdx: number;
  reviewMap: Map<string, ReviewMark>;
  pack?: KnowledgePack;
  onCell: (t: CellTarget) => void;
  onChange: (d: OcsDocument) => void;
  doc: OcsDocument;
}) {
  const { attributes, listeners, setNodeRef, transform, transition, isDragging } = useSortable({ id });
  const style = { transform: CSS.Transform.toString(transform), transition, opacity: isDragging ? 0.5 : 1 };
  const tasks = unit.tasks ?? [];
  const taskIds = tasks.map((t) => `t:${t._tid}`);
  const isCustomUnit = !(unit._refs?.length) && !unit.source?.ocs_code; // 無官方來源=自訂(spec §2)

  return (
    <div ref={setNodeRef} style={style} className="rounded-lg border bg-background">
      <div className="flex items-center gap-1.5 border-b bg-muted/40 px-3 py-2">
        <button type="button" className="cursor-grab text-muted-foreground/60 hover:text-foreground" {...attributes} {...listeners}>
          <GripVertical className="h-4 w-4" />
        </button>
        <Badge variant="outline" className="font-mono text-xs">{unit.ocu_code}</Badge>
        <EditableText
          value={unit.ocu_name ?? ""}
          placeholder="職責名稱（點擊命名）"
          onCommit={(v) => onChange(renameUnit(doc, unitIdx, v))}
          className="flex-1 text-sm font-medium"
        />
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
              reviewMap={reviewMap}
              pack={pack}
              onCell={onCell}
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
}: {
  document: OcsDocument;
  pack?: KnowledgePack;
  onChange: (d: OcsDocument) => void;
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
        customMode="footer"
        autoCode="A"
        autoApplyOnFirstOpen
        value={doc.ocs_attitude?.attitudes ?? []}
        options={options}
        defaults={defaults}
        onCommit={(items) => onChange(setAttitudes(doc, items))}
      />
    </div>
  );
}

export function JobDocTable({
  document,
  profileId,
  onCell,
  onChange,
}: {
  document: OcsDocument;
  profileId: string;
  onCell: (target: CellTarget) => void;
  onChange: (d: OcsDocument) => void;
}) {
  const units = document.ocs_content?.ocu_units ?? [];
  const unitIds = units.map((u) => `u:${u._uid}`);
  // 知識包（ADR 0021）：任務級別官方值/來源（TaskRow）。選過職類才有資料。
  const { data: pack } = useKnowledge(profileId, !!document.ocs_profile?.ocs_code);
  // 0028 D7:訪談 evidence(review=pending)→ 同格追蹤修訂標記(404=尚無訪談,無標記)
  const { data: iview } = useInterview(profileId);
  const reviewMap = useMemo(() => buildReviewMap(iview?.evidence ?? []), [iview]);

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
                  reviewMap={reviewMap}
                  pack={pack}
                  onCell={onCell}
                  onChange={onChange}
                  doc={document}
                />
              ))}
            </div>
          </SortableContext>
        </DndContext>
      )}

      <button
        type="button"
        className="inline-flex items-center gap-1 rounded-md border border-dashed px-3 py-2 text-sm text-muted-foreground hover:text-foreground"
        onClick={() => onChange(addUnit(document))}
      >
        <Plus className="h-4 w-4" />
        新增職責
      </button>

      {/* 職能內涵（A=attitude 態度） */}
      <AttitudeBlock document={document} pack={pack} onChange={onChange} />

      {/* 說明與補充事項（可編輯） */}
      <DocNotes document={document} profileId={profileId} onChange={onChange} />
    </div>
  );
}
