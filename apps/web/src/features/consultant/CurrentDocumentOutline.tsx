"use client";

import type {
  ApprovedJobDocumentView,
  ApprovedJobDocumentWrite,
  DocumentPatchActionView,
} from "@caliburn/job-analysis-contract";
import { FileText, Link2, Plus, Trash2 } from "lucide-react";

import { Button } from "@/shared/ui/button";
import {
  buildCurrentDocumentOutline,
  type CurrentDocumentOutlineItem,
  type CurrentDocumentOutlineTask,
} from "./consultantWorkspaceModel";

type TaskDraft = ApprovedJobDocumentWrite["tasks"][number];
type OpksDraft = ApprovedJobDocumentWrite["opks"][number];
type EnablerDraft = TaskDraft["enablers"][number];
type ChangeDocument = (
  update: (document: ApprovedJobDocumentWrite) => ApprovedJobDocumentWrite,
) => void;

const itemKindLabels: Record<OpksDraft["kind"], string> = {
  output: "產出 O",
  indicator: "績效指標 P",
  knowledge: "知識 K",
  skill: "技能 S",
  attitude: "態度 A",
};

const enablerLabels: Record<EnablerDraft["kind"], string> = {
  tool_system: "工具／系統",
  method: "方法",
  knowledge: "知識",
  skill: "技能",
  other: "其他",
};

const itemKindCodes: Record<OpksDraft["kind"], string> = {
  output: "O",
  indicator: "P",
  knowledge: "K",
  skill: "S",
  attitude: "A",
};

function TextField({
  label,
  value,
  onChange,
  multiline = false,
}: {
  label: string;
  value: string | null;
  onChange: (value: string) => void;
  multiline?: boolean;
}) {
  const className =
    "mt-1 w-full rounded-lg border border-stone-300 bg-white px-3 py-2 text-sm outline-none focus:border-stone-500";
  return (
    <label className="block text-xs font-medium text-stone-600">
      {label}
      {multiline ? (
        <textarea
          aria-label={label}
          className={`${className} min-h-20 leading-6`}
          value={value ?? ""}
          onChange={(event) => onChange(event.target.value)}
        />
      ) : (
        <input
          aria-label={label}
          className={className}
          value={value ?? ""}
          onChange={(event) => onChange(event.target.value)}
        />
      )}
    </label>
  );
}

function ItemEditor({
  outlineItem,
  taskLabel,
  currentTaskId,
  document,
  onChange,
}: {
  outlineItem: CurrentDocumentOutlineItem;
  taskLabel: string;
  currentTaskId: string | null;
  document: ApprovedJobDocumentWrite;
  onChange: ChangeDocument;
}) {
  const item = outlineItem.item;
  const shared = outlineItem.sharedTaskCount > 1;
  const indicators = document.opks.filter((entry) => entry.kind === "indicator");
  const updateItem = (update: (entry: OpksDraft) => OpksDraft) =>
    onChange((value) => ({
      ...value,
      opks: value.opks.map((entry) =>
        entry.item_id === item.item_id ? update(entry) : entry,
      ),
    }));

  const changeKind = (kind: OpksDraft["kind"]) =>
    updateItem((entry) => {
      return {
        ...entry,
        kind,
        task_ids:
          kind === "attitude"
            ? []
            : kind === "output" || kind === "indicator"
              ? currentTaskId
                ? [currentTaskId]
                : []
              : entry.task_ids,
        indicator_ids:
          kind === "knowledge" || kind === "skill"
            ? entry.indicator_ids
            : [],
      };
    });

  return (
    <div className="rounded-lg border border-stone-200 bg-stone-50/70 p-3">
      <div className="flex flex-wrap items-center gap-2 text-xs">
        <span className="font-semibold text-stone-700">{outlineItem.label}</span>
        {shared ? (
          <span className="rounded-full bg-stone-200 px-2 py-1 text-stone-600">
            共用於 {outlineItem.sharedTaskCount} 項工作
          </span>
        ) : null}
        <span className="min-w-0 flex-1 truncate text-stone-500">
          {item.text || "未命名內容"}
        </span>
        <Button
          variant="ghost"
          size="icon-sm"
          aria-label={`刪除 ${taskLabel} ${outlineItem.label}`}
          onClick={() =>
            onChange((value) => ({
              ...value,
              opks: value.opks.filter((entry) => entry.item_id !== item.item_id),
            }))
          }
        >
          <Trash2 />
        </Button>
      </div>
      <div className="mt-2 grid gap-2 sm:grid-cols-[150px_minmax(0,1fr)]">
        <label className="block text-xs font-medium text-stone-600">
          類型
          <select
            aria-label={`${taskLabel} ${outlineItem.label} 類型`}
            className="mt-1 w-full rounded-lg border border-stone-300 bg-white px-2 py-2 text-sm"
            value={item.kind}
            onChange={(event) => changeKind(event.target.value as OpksDraft["kind"])}
          >
            {Object.entries(itemKindLabels).map(([kind, label]) => (
              <option key={kind} value={kind}>{label}</option>
            ))}
          </select>
        </label>
        <TextField
          label={`${taskLabel} ${outlineItem.label} 內容`}
          value={item.text}
          onChange={(text) => updateItem((entry) => ({ ...entry, text }))}
        />
      </div>
      {item.kind !== "attitude" && document.tasks.length ? (
        <details className="mt-3 rounded-lg border border-stone-200 bg-white px-3 py-2">
          <summary className="cursor-pointer text-xs font-medium text-stone-600">
            關聯設定
          </summary>
          <div className="mt-3 space-y-3">
            <div>
              <p className="text-xs font-medium text-stone-600">連結工作</p>
              {item.kind === "output" || item.kind === "indicator" ? (
                <select
                  aria-label={`${taskLabel} ${outlineItem.label} 連結工作`}
                  className="mt-1 w-full rounded-lg border border-stone-300 bg-white px-3 py-2 text-sm"
                  value={item.task_ids[0] ?? ""}
                  onChange={(event) =>
                    updateItem((entry) => ({
                      ...entry,
                      task_ids: event.target.value ? [event.target.value] : [],
                    }))
                  }
                >
                  <option value="">尚未連結</option>
                  {document.tasks.map((task) => (
                    <option key={task.task_id} value={task.task_id}>
                      {task.statement}
                    </option>
                  ))}
                </select>
              ) : (
                <div className="mt-2 flex flex-wrap gap-3">
                  {document.tasks.map((task) => (
                    <label key={task.task_id} className="flex items-center gap-1.5 text-xs">
                      <input
                        type="checkbox"
                        checked={item.task_ids.includes(task.task_id)}
                        onChange={(event) =>
                          updateItem((entry) => ({
                            ...entry,
                            task_ids: event.target.checked
                              ? [...entry.task_ids, task.task_id]
                              : entry.task_ids.filter((id) => id !== task.task_id),
                          }))
                        }
                      />
                      {task.statement}
                    </label>
                  ))}
                </div>
              )}
            </div>
            {(item.kind === "knowledge" || item.kind === "skill") && indicators.length ? (
              <div>
                <p className="text-xs font-medium text-stone-600">關聯績效指標（選填）</p>
                <div className="mt-2 flex flex-wrap gap-3">
                  {indicators.map((indicator) => (
                    <label key={indicator.item_id} className="flex items-center gap-1.5 text-xs">
                      <input
                        type="checkbox"
                        checked={item.indicator_ids.includes(indicator.item_id)}
                        onChange={(event) =>
                          updateItem((entry) => ({
                            ...entry,
                            indicator_ids: event.target.checked
                              ? [...entry.indicator_ids, indicator.item_id]
                              : entry.indicator_ids.filter((id) => id !== indicator.item_id),
                          }))
                        }
                      />
                      {indicator.text}
                    </label>
                  ))}
                </div>
              </div>
            ) : null}
          </div>
        </details>
      ) : null}
    </div>
  );
}

function TaskSection({
  outlineTask,
  document,
  onChange,
}: {
  outlineTask: CurrentDocumentOutlineTask;
  document: ApprovedJobDocumentWrite;
  onChange: ChangeDocument;
}) {
  const { task, items, label: taskLabel } = outlineTask;
  const updateTask = (update: (entry: TaskDraft) => TaskDraft) =>
    onChange((value) => ({
      ...value,
      tasks: value.tasks.map((entry) =>
        entry.task_id === task.task_id ? update(entry) : entry,
      ),
    }));
  const updateTaskField = (
    field: keyof Pick<TaskDraft, "statement" | "action" | "object" | "purpose_result" | "context" | "frequency_text">,
    value: string,
  ) => updateTask((entry) => ({ ...entry, [field]: value }));
  const addItem = (kind: OpksDraft["kind"]) =>
    onChange((value) => ({
      ...value,
      opks: [
        ...value.opks,
        {
          item_id: crypto.randomUUID(),
          kind,
          text: `新增${itemKindLabels[kind]}`,
          display_order: value.opks.filter((entry) => entry.kind === kind).length,
          task_ids: kind === "attitude" ? [] : [task.task_id],
          indicator_ids: [],
        },
      ],
    }));
  const deleteTask = () =>
    onChange((value) => ({
      ...value,
      tasks: value.tasks
        .filter((entry) => entry.task_id !== task.task_id)
        .map((entry, index) => ({ ...entry, display_order: index })),
      opks: value.opks
        .filter(
          (entry) => !(
            (entry.kind === "output" || entry.kind === "indicator") &&
            entry.task_ids.includes(task.task_id)
          ),
        )
        .map((entry) => ({
          ...entry,
          task_ids: entry.task_ids.filter((id) => id !== task.task_id),
        })),
    }));

  return (
    <article
      aria-label={`${taskLabel} ${task.statement || "未命名工作"}`}
      className="rounded-xl border border-stone-200 bg-white p-4 shadow-sm"
    >
      <div className="flex items-start gap-3">
        <div className="mt-1 rounded-md bg-stone-100 px-2 py-1 text-[11px] font-semibold text-stone-600">
          {taskLabel}
        </div>
        <div className="min-w-0 flex-1">
          <div className="flex items-start justify-between gap-3">
            <h4 className="text-base font-semibold text-stone-900">
              {task.statement || "未命名工作"}
            </h4>
            <Button variant="ghost" size="icon-sm" aria-label={`刪除 ${taskLabel}`} onClick={deleteTask}>
              <Trash2 />
            </Button>
          </div>
          <div className="mt-3 grid gap-3 sm:grid-cols-2">
            <TextField label={`${taskLabel} 工作敘述`} value={task.statement} onChange={(value) => updateTaskField("statement", value)} multiline />
            <TextField label={`${taskLabel} 動作`} value={task.action} onChange={(value) => updateTaskField("action", value)} />
            <TextField label={`${taskLabel} 對象`} value={task.object} onChange={(value) => updateTaskField("object", value)} />
            <TextField label={`${taskLabel} 目的／結果`} value={task.purpose_result} onChange={(value) => updateTaskField("purpose_result", value)} />
            <TextField label={`${taskLabel} 情境`} value={task.context} onChange={(value) => updateTaskField("context", value)} />
            <TextField label={`${taskLabel} 頻率`} value={task.frequency_text} onChange={(value) => updateTaskField("frequency_text", value)} />
          </div>
          <details className="mt-3 rounded-lg border border-stone-200 bg-stone-50/70 px-3 py-2">
            <summary className="cursor-pointer text-xs font-medium text-stone-600">分組與其他欄位</summary>
            <div className="mt-3 grid gap-3 sm:grid-cols-2">
              <label className="block text-xs font-medium text-stone-600">
                所屬職責（可先不分組）
                <select
                  aria-label={`${taskLabel} 所屬職責`}
                  className="mt-1 w-full rounded-lg border border-stone-300 bg-white px-3 py-2 text-sm"
                  value={task.duty_id ?? ""}
                  onChange={(event) => updateTask((entry) => ({ ...entry, duty_id: event.target.value || null }))}
                >
                  <option value="">尚未分組</option>
                  {document.duties.map((duty) => (
                    <option key={duty.duty_id} value={duty.duty_id}>{duty.statement}</option>
                  ))}
                </select>
              </label>
              <label className="block text-xs font-medium text-stone-600">
                責任角色
                <select
                  aria-label={`${taskLabel} 責任角色`}
                  className="mt-1 w-full rounded-lg border border-stone-300 bg-white px-3 py-2 text-sm"
                  value={task.responsibility_role ?? ""}
                  onChange={(event) =>
                    updateTask((entry) => ({
                      ...entry,
                      responsibility_role: (event.target.value || null) as TaskDraft["responsibility_role"],
                    }))
                  }
                >
                  <option value="">未填</option>
                  <option value="primary">主要負責</option>
                  <option value="shared">共同負責</option>
                  <option value="assist">協助</option>
                </select>
              </label>
            </div>
            <div className="mt-4">
              <div className="flex items-center justify-between gap-2">
                <p className="text-xs font-medium text-stone-600">工具／方法／其他促成條件</p>
                <Button
                  size="xs"
                  variant="ghost"
                  onClick={() => updateTask((entry) => ({ ...entry, enablers: [...entry.enablers, { kind: "other", name: "" }] }))}
                >
                  <Plus />新增
                </Button>
              </div>
              {task.enablers.map((enabler, enablerIndex) => (
                <div key={`${task.task_id}:${enablerIndex}`} className="mt-2 flex gap-2">
                  <select
                    aria-label={`${taskLabel} 促成條件 ${enablerIndex + 1} 類型`}
                    className="rounded-lg border border-stone-300 bg-white px-2 py-2 text-xs"
                    value={enabler.kind}
                    onChange={(event) =>
                      updateTask((entry) => ({
                        ...entry,
                        enablers: entry.enablers.map((value, index) =>
                          index === enablerIndex ? { ...value, kind: event.target.value as EnablerDraft["kind"] } : value,
                        ),
                      }))
                    }
                  >
                    {Object.entries(enablerLabels).map(([kind, label]) => (
                      <option key={kind} value={kind}>{label}</option>
                    ))}
                  </select>
                  <input
                    aria-label={`${taskLabel} 促成條件 ${enablerIndex + 1} 名稱`}
                    className="min-w-0 flex-1 rounded-lg border border-stone-300 bg-white px-3 py-2 text-sm"
                    value={enabler.name}
                    onChange={(event) =>
                      updateTask((entry) => ({
                        ...entry,
                        enablers: entry.enablers.map((value, index) =>
                          index === enablerIndex ? { ...value, name: event.target.value } : value,
                        ),
                      }))
                    }
                  />
                  <Button
                    variant="ghost"
                    size="icon-sm"
                    aria-label={`刪除 ${taskLabel} 促成條件 ${enablerIndex + 1}`}
                    onClick={() => updateTask((entry) => ({ ...entry, enablers: entry.enablers.filter((_, index) => index !== enablerIndex) }))}
                  >
                    <Trash2 />
                  </Button>
                </div>
              ))}
            </div>
          </details>
        </div>
      </div>
      <div className="mt-4 border-t border-stone-100 pt-4">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div className="flex items-center gap-2">
            <Link2 className="size-4 text-stone-500" />
            <h5 className="text-xs font-semibold tracking-[0.14em] text-stone-500 uppercase">O／P／K／S</h5>
          </div>
          <div className="flex flex-wrap gap-1">
            {(["output", "indicator", "knowledge", "skill"] as const).map((kind) => (
              <Button key={kind} size="xs" variant="outline" aria-label={`新增${itemKindLabels[kind]}`} onClick={() => addItem(kind)}>
                <Plus />{itemKindLabels[kind]}
              </Button>
            ))}
          </div>
        </div>
        {items.length === 0 ? (
          <p className="mt-2 text-xs text-stone-500">這項工作目前沒有已列出的 O／P／K／S。</p>
        ) : (
          <div className="mt-3 grid gap-2 sm:grid-cols-2">
            {items.map((outlineItem) => (
              <ItemEditor
                key={`${task.task_id}:${outlineItem.item.item_id}`}
                outlineItem={outlineItem}
                taskLabel={taskLabel}
                currentTaskId={task.task_id}
                document={document}
                onChange={onChange}
              />
            ))}
          </div>
        )}
      </div>
    </article>
  );
}

export function CurrentDocumentOutline({
  document,
  onChange,
}: {
  document: ApprovedJobDocumentWrite;
  onChange: ChangeDocument;
}) {
  const outline = buildCurrentDocumentOutline(document);
  const addDuty = () =>
    onChange((value) => ({
      ...value,
      duties: [...value.duties, { duty_id: crypto.randomUUID(), statement: "新職責", display_order: value.duties.length }],
    }));
  const deleteDuty = (dutyId: string) =>
    onChange((value) => ({
      ...value,
      duties: value.duties.filter((duty) => duty.duty_id !== dutyId).map((duty, index) => ({ ...duty, display_order: index })),
      tasks: value.tasks.map((task) => task.duty_id === dutyId ? { ...task, duty_id: null } : task),
    }));
  const addTask = () =>
    onChange((value) => ({
      ...value,
      tasks: [
        ...value.tasks,
        {
          task_id: crypto.randomUUID(),
          duty_id: null,
          statement: "新工作",
          action: "執行",
          object: "待補充對象",
          purpose_result: null,
          context: null,
          frequency_text: null,
          responsibility_role: null,
          enablers: [],
          display_order: value.tasks.length,
          competency_level: null,
        },
      ],
    }));
  const addDocumentItem = (kind: "knowledge" | "skill" | "attitude") =>
    onChange((value) => ({
      ...value,
      opks: [
        ...value.opks,
        {
          item_id: crypto.randomUUID(),
          kind,
          text: `新增${itemKindLabels[kind]}`,
          display_order: value.opks.filter((entry) => entry.kind === kind).length,
          task_ids: [],
          indicator_ids: [],
        },
      ],
    }));
  const updateDuty = (dutyId: string, statement: string) =>
    onChange((value) => ({
      ...value,
      duties: value.duties.map((duty) => duty.duty_id === dutyId ? { ...duty, statement } : duty),
    }));
  const renderTask = (outlineTask: CurrentDocumentOutlineTask) => (
    <TaskSection key={outlineTask.task.task_id} outlineTask={outlineTask} document={document} onChange={onChange} />
  );

  return (
    <section aria-label="目前 JD 階層" className="space-y-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          <div className="rounded-lg bg-stone-100 p-2 text-stone-700"><FileText className="size-5" /></div>
          <div>
            <p className="text-xs font-semibold tracking-[0.16em] text-stone-500 uppercase">工作骨架</p>
            <p className="text-sm text-stone-600">Duty → Task → O／P／K／S</p>
          </div>
        </div>
        <Button size="sm" variant="outline" onClick={addDuty}><Plus />新增職責</Button>
      </div>
      <div className="space-y-4">
        {outline.duties.map((group, dutyIndex) => {
          const dutyLabel = `Duty ${dutyIndex + 1}`;
          return (
            <section key={group.duty.duty_id} aria-label={`${dutyLabel} ${group.duty.statement}`} className="rounded-2xl border border-stone-200 bg-stone-50/80 p-4">
              <div className="flex items-start gap-3">
                <div className="mt-0.5 rounded-md bg-stone-900 px-2 py-1 text-[11px] font-semibold text-white">{dutyLabel}</div>
                <div className="min-w-0 flex-1">
                  <div className="flex items-start justify-between gap-3">
                    <h3 className="text-lg font-semibold">{group.duty.statement || "未命名職責"}</h3>
                    <Button variant="ghost" size="icon-sm" aria-label={`刪除 ${dutyLabel}`} onClick={() => deleteDuty(group.duty.duty_id)}><Trash2 /></Button>
                  </div>
                  <TextField label={`${dutyLabel} 名稱`} value={group.duty.statement} onChange={(statement) => updateDuty(group.duty.duty_id, statement)} />
                </div>
              </div>
              <div className="mt-4 space-y-3">
                {group.tasks.length ? group.tasks.map(renderTask) : (
                  <p className="rounded-lg border border-dashed border-stone-300 px-3 py-4 text-sm text-stone-500">目前沒有歸屬於這項 Duty 的工作。</p>
                )}
              </div>
            </section>
          );
        })}
        <section aria-label="尚未歸屬" className="rounded-2xl border border-dashed border-stone-300 bg-white p-4">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div className="flex items-start gap-3">
              <div className="mt-0.5 rounded-md bg-stone-100 px-2 py-1 text-[11px] font-semibold text-stone-600">其他</div>
              <div>
                <h3 className="text-lg font-semibold">尚未歸屬</h3>
                <p className="mt-1 text-sm text-stone-500">尚未分到 Duty／Task 的內容會留在這裡，不會因側欄收合而消失。</p>
              </div>
            </div>
            <div className="flex flex-wrap gap-1">
              <Button size="sm" variant="outline" onClick={addTask}><Plus />新增工作</Button>
              <Button size="sm" variant="ghost" onClick={() => addDocumentItem("knowledge")}><Plus />未歸屬 K</Button>
              <Button size="sm" variant="ghost" onClick={() => addDocumentItem("skill")}><Plus />未歸屬 S</Button>
            </div>
          </div>
          <div className="mt-4 space-y-3">
            {outline.unassignedTasks.map(renderTask)}
            {outline.unassignedItems.length ? (
              <div className="grid gap-2 sm:grid-cols-2">
                {outline.unassignedItems.map((outlineItem) => (
                  <ItemEditor key={`unassigned:${outlineItem.item.item_id}`} outlineItem={outlineItem} taskLabel="尚未歸屬" currentTaskId={null} document={document} onChange={onChange} />
                ))}
              </div>
            ) : null}
            {!outline.unassignedTasks.length && !outline.unassignedItems.length ? (
              <p className="rounded-lg border border-dashed border-stone-200 px-3 py-4 text-sm text-stone-500">目前沒有尚未歸屬的工作或項目。</p>
            ) : null}
          </div>
        </section>
        <section aria-label="文件層級 A" className="rounded-2xl border border-stone-200 bg-white p-4">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div className="flex items-center gap-3">
              <div className="rounded-md bg-stone-100 px-2 py-1 text-[11px] font-semibold text-stone-600">A</div>
              <div>
                <h3 className="text-lg font-semibold">文件層級項目</h3>
                <p className="mt-1 text-sm text-stone-500">A 保持獨立，不掛到 Duty 或 Task。</p>
              </div>
            </div>
            <Button size="sm" variant="outline" onClick={() => addDocumentItem("attitude")}><Plus />新增態度 A</Button>
          </div>
          <div className="mt-4 grid gap-3 sm:grid-cols-2">
            {outline.documentItems.length ? outline.documentItems.map((outlineItem) => (
              <ItemEditor key={`document:${outlineItem.item.item_id}`} outlineItem={outlineItem} taskLabel="文件層級" currentTaskId={null} document={document} onChange={onChange} />
            )) : <p className="text-sm text-stone-500">目前沒有文件層級 A 項目。</p>}
          </div>
        </section>
      </div>
    </section>
  );
}

type ReviewDocument = ApprovedJobDocumentView;
type ReviewTask = ReviewDocument["tasks"][number];
type ReviewItem = ReviewDocument["opks"][number];

const reviewTaskFields: Array<{
  field: keyof ReviewTask;
  label: string;
}> = [
  { field: "action", label: "動作" },
  { field: "object", label: "對象" },
  { field: "purpose_result", label: "目的／結果" },
  { field: "context", label: "情境" },
  { field: "frequency_text", label: "頻率" },
  { field: "responsibility_role", label: "責任角色" },
  { field: "enablers", label: "工具／方法／其他促成條件" },
];

function reviewObject(value: unknown): Record<string, unknown> | null {
  return typeof value === "object" && value !== null && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : null;
}

function reviewValueText(value: unknown): string {
  if (value === null || value === undefined || value === "") return "未填";
  if (Array.isArray(value)) {
    const names = value.flatMap((entry) => {
      const object = reviewObject(entry);
      return object && typeof object.name === "string" ? [object.name] : [];
    });
    return names.length ? names.join("、") : value.map(String).join("、") || "未填";
  }
  if (typeof value === "object") return JSON.stringify(value);
  return String(value);
}

function pathAction(
  actions: DocumentPatchActionView[],
  path: string,
): DocumentPatchActionView | undefined {
  return actions.find((action) => action.path === path);
}

function entityAction(
  actions: DocumentPatchActionView[],
  collection: "duties" | "tasks" | "opks",
  identity: string,
  operation: "add" | "withdraw",
): DocumentPatchActionView | undefined {
  const idField = collection === "duties"
    ? "duty_id"
    : collection === "tasks"
      ? "task_id"
      : "item_id";
  return actions.find((action) => {
    if (action.operation !== operation) return false;
    if (operation === "withdraw") {
      return action.path === `/${collection}/${identity}`;
    }
    const after = reviewObject(action.after);
    return action.path === `/${collection}` && after?.[idField] === identity;
  });
}

function ReviewDiffValue({
  label,
  current,
  action,
}: {
  label: string;
  current: unknown;
  action?: DocumentPatchActionView;
}) {
  if (!action) {
    return (
      <div>
        <p className="text-[11px] font-medium text-stone-500">{label}</p>
        <p className="mt-0.5 text-sm leading-6 text-stone-700">
          {reviewValueText(current)}
        </p>
      </div>
    );
  }
  return (
    <div data-change-id={action.action_id}>
      <p className="text-[11px] font-medium text-stone-500">{label}</p>
      {action.before !== null ? (
        <p className="mt-0.5 text-sm leading-6 text-rose-700 line-through decoration-rose-400">
          {reviewValueText(action.before)}
        </p>
      ) : null}
      {action.after !== null ? (
        <p className="mt-0.5 rounded-md bg-emerald-50 px-2 py-1 text-sm leading-6 text-emerald-800">
          {reviewValueText(action.after)}
        </p>
      ) : null}
    </div>
  );
}

function ReviewItemCard({
  item,
  approvedItem,
  label,
  taskId,
  actions,
  removedRelation = false,
}: {
  item: ReviewItem | null;
  approvedItem: ReviewItem | null;
  label: string;
  taskId: string | null;
  actions: DocumentPatchActionView[];
  removedRelation?: boolean;
}) {
  const identity = item?.item_id ?? approvedItem!.item_id;
  const add = entityAction(actions, "opks", identity, "add");
  const withdraw = entityAction(actions, "opks", identity, "withdraw");
  const textChange = pathAction(actions, `/opks/${identity}/text`);
  const relationChange = pathAction(actions, `/opks/${identity}/task_ids`);
  const currentLinked = taskId ? Boolean(item?.task_ids.includes(taskId)) : false;
  const approvedLinked = taskId
    ? Boolean(approvedItem?.task_ids.includes(taskId))
    : false;
  const relationAdded = Boolean(relationChange && currentLinked && !approvedLinked);
  const removed = !item || Boolean(withdraw) || removedRelation;
  const currentText = item?.text ?? approvedItem?.text ?? "未命名內容";

  return (
    <div
      data-change-id={(withdraw ?? add ?? relationChange ?? textChange)?.action_id}
      className={`rounded-lg border p-3 ${
        removed
          ? "border-rose-200 bg-rose-50/60"
          : add || relationAdded
            ? "border-emerald-200 bg-emerald-50/60"
            : "border-stone-200 bg-stone-50/70"
      }`}
    >
      <div className="flex flex-wrap items-center gap-2 text-xs">
        <span className="font-semibold text-stone-700">{label}</span>
        {item && ["knowledge", "skill"].includes(item.kind) && item.task_ids.length > 1 ? (
          <span className="rounded-full bg-white px-2 py-1 text-stone-600 ring-1 ring-stone-200">
            共用於 {item.task_ids.length} 項工作
          </span>
        ) : null}
        {removed ? <span className="text-rose-700">{removedRelation ? "從這項工作移除" : "移除"}</span> : null}
        {add ? <span className="text-emerald-700">新增</span> : null}
        {relationAdded ? <span className="text-emerald-700">新增關聯</span> : null}
      </div>
      {textChange ? (
        <div className="mt-2">
          <ReviewDiffValue label="內容" current={currentText} action={textChange} />
        </div>
      ) : (
        <p className={`mt-2 text-sm leading-6 ${removed ? "text-rose-700 line-through" : "text-stone-700"}`}>
          {currentText}
        </p>
      )}
    </div>
  );
}

function ReviewTaskCard({
  task,
  approvedTask,
  taskLabel,
  currentDocument,
  approvedDocument,
  actions,
  movedIn,
  removed,
}: {
  task: ReviewTask | null;
  approvedTask: ReviewTask | null;
  taskLabel: string;
  currentDocument: ReviewDocument;
  approvedDocument: ReviewDocument;
  actions: DocumentPatchActionView[];
  movedIn?: boolean;
  removed?: boolean;
}) {
  const visibleTask = task ?? approvedTask!;
  const identity = visibleTask.task_id;
  const add = entityAction(actions, "tasks", identity, "add");
  const withdraw = entityAction(actions, "tasks", identity, "withdraw");
  const statementChange = pathAction(actions, `/tasks/${identity}/statement`);
  const isRemoved = Boolean(removed || withdraw || !task);
  const currentItems = currentDocument.opks.filter(
    (item) => item.kind !== "attitude" && item.task_ids.includes(identity),
  );
  const approvedItems = approvedDocument.opks.filter(
    (item) => item.kind !== "attitude" && item.task_ids.includes(identity),
  );
  const itemIds = [
    ...currentItems.map((item) => item.item_id),
    ...approvedItems
      .filter((item) => !currentItems.some((current) => current.item_id === item.item_id))
      .filter((item) => {
        const current = currentDocument.opks.find((entry) => entry.item_id === item.item_id);
        return Boolean(
          entityAction(actions, "opks", item.item_id, "withdraw") ||
            (current && pathAction(actions, `/opks/${item.item_id}/task_ids`)),
        );
      })
      .map((item) => item.item_id),
  ];
  const itemOrdinals = new Map<ReviewItem["kind"], number>();

  return (
    <article
      aria-label={`${taskLabel} ${visibleTask.statement || "未命名工作"}`}
      data-change-id={(withdraw ?? add ?? statementChange)?.action_id}
      className={`rounded-xl border p-4 ${
        isRemoved
          ? "border-rose-200 bg-rose-50/50"
          : add || movedIn
            ? "border-emerald-200 bg-emerald-50/45"
            : "border-stone-200 bg-white"
      }`}
    >
      <div className="flex flex-wrap items-start gap-3">
        <span className="rounded-md bg-stone-100 px-2 py-1 text-[11px] font-semibold text-stone-600">
          {taskLabel}
        </span>
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            {isRemoved ? <span className="text-xs font-medium text-rose-700">{movedIn ? "" : "從此職責移出"}</span> : null}
            {movedIn ? <span className="text-xs font-medium text-emerald-700">移入此職責</span> : null}
            {add ? <span className="text-xs font-medium text-emerald-700">新增工作</span> : null}
          </div>
          {statementChange ? (
            <ReviewDiffValue label="工作敘述" current={visibleTask.statement} action={statementChange} />
          ) : (
            <h4 className={`mt-1 text-base font-semibold ${isRemoved ? "text-rose-700 line-through" : "text-stone-900"}`}>
              {visibleTask.statement || "未命名工作"}
            </h4>
          )}
          {!isRemoved ? (
            <div className="mt-3 grid gap-3 sm:grid-cols-2">
              {reviewTaskFields.map(({ field, label }) => {
                const action = pathAction(actions, `/tasks/${identity}/${field}`);
                const value = task?.[field];
                if (!action && (value === null || value === "" || (Array.isArray(value) && !value.length))) {
                  return null;
                }
                return <ReviewDiffValue key={field} label={label} current={value} action={action} />;
              })}
            </div>
          ) : null}
        </div>
      </div>
      {itemIds.length ? (
        <div className="mt-4 border-t border-stone-100 pt-4">
          <p className="text-xs font-semibold tracking-[0.14em] text-stone-500 uppercase">O／P／K／S</p>
          <div className="mt-3 grid gap-2 sm:grid-cols-2">
            {itemIds.map((itemId) => {
              const item = currentDocument.opks.find((entry) => entry.item_id === itemId) ?? null;
              const approvedItem = approvedDocument.opks.find((entry) => entry.item_id === itemId) ?? null;
              const kind = item?.kind ?? approvedItem!.kind;
              const ordinal = (itemOrdinals.get(kind) ?? 0) + 1;
              itemOrdinals.set(kind, ordinal);
              return (
                <ReviewItemCard
                  key={`${identity}:${itemId}`}
                  item={item}
                  approvedItem={approvedItem}
                  label={`${itemKindCodes[kind]} ${ordinal}`}
                  taskId={identity}
                  actions={actions}
                  removedRelation={Boolean(approvedItem?.task_ids.includes(identity) && !item?.task_ids.includes(identity))}
                />
              );
            })}
          </div>
        </div>
      ) : null}
    </article>
  );
}

export function CurrentDocumentSemanticOutline({
  document,
  approvedDocument,
  actions = [],
}: {
  document: ReviewDocument;
  approvedDocument: ReviewDocument;
  actions?: DocumentPatchActionView[];
}) {
  const currentDuties = [...document.duties].sort((a, b) => a.display_order - b.display_order);
  const approvedDuties = [...approvedDocument.duties].sort((a, b) => a.display_order - b.display_order);
  const currentTasks = [...document.tasks].sort((a, b) => a.display_order - b.display_order);
  const approvedTasks = [...approvedDocument.tasks].sort((a, b) => a.display_order - b.display_order);
  const taskIds = [
    ...currentTasks.map((task) => task.task_id),
    ...approvedTasks
      .filter((task) => !currentTasks.some((current) => current.task_id === task.task_id))
      .map((task) => task.task_id),
  ];
  const taskLabels = new Map(taskIds.map((id, index) => [id, `Task ${index + 1}`]));
  const dutyIds = [
    ...currentDuties.map((duty) => duty.duty_id),
    ...approvedDuties
      .filter(
        (duty) =>
          !currentDuties.some((current) => current.duty_id === duty.duty_id) &&
          Boolean(entityAction(actions, "duties", duty.duty_id, "withdraw")),
      )
      .map((duty) => duty.duty_id),
  ];

  const taskCards = (dutyId: string | null) => {
    const currentAtLocation = currentTasks.filter((task) => task.duty_id === dutyId);
    const oldTraces = approvedTasks.filter((approvedTask) => {
      if (approvedTask.duty_id !== dutyId) return false;
      const current = currentTasks.find((task) => task.task_id === approvedTask.task_id);
      if (!current) return Boolean(entityAction(actions, "tasks", approvedTask.task_id, "withdraw"));
      return current.duty_id !== dutyId && Boolean(pathAction(actions, `/tasks/${approvedTask.task_id}/duty_id`));
    });
    return (
      <div className="mt-4 space-y-3">
        {currentAtLocation.map((task) => {
          const approvedTask = approvedTasks.find((entry) => entry.task_id === task.task_id) ?? null;
          const movedIn = Boolean(
            approvedTask &&
              approvedTask.duty_id !== task.duty_id &&
              pathAction(actions, `/tasks/${task.task_id}/duty_id`),
          );
          return (
            <ReviewTaskCard
              key={`current:${task.task_id}`}
              task={task}
              approvedTask={approvedTask}
              taskLabel={taskLabels.get(task.task_id) ?? "Task"}
              currentDocument={document}
              approvedDocument={approvedDocument}
              actions={actions}
              movedIn={movedIn}
            />
          );
        })}
        {oldTraces.map((task) => (
          <ReviewTaskCard
            key={`old:${dutyId ?? "unassigned"}:${task.task_id}`}
            task={null}
            approvedTask={task}
            taskLabel={taskLabels.get(task.task_id) ?? "Task"}
            currentDocument={document}
            approvedDocument={approvedDocument}
            actions={actions}
            removed
          />
        ))}
        {!currentAtLocation.length && !oldTraces.length ? (
          <p className="rounded-lg border border-dashed border-stone-300 px-3 py-4 text-sm text-stone-500">
            目前沒有這個位置的工作。
          </p>
        ) : null}
      </div>
    );
  };

  const currentUnassignedItems = document.opks.filter(
    (item) => item.kind !== "attitude" && !item.task_ids.some((id) => currentTasks.some((task) => task.task_id === id)),
  );
  const documentItems = document.opks.filter((item) => item.kind === "attitude");

  return (
    <section aria-label="JD 語意比較" className="space-y-4">
      {dutyIds.map((dutyId, index) => {
        const duty = currentDuties.find((entry) => entry.duty_id === dutyId) ?? null;
        const approvedDuty = approvedDuties.find((entry) => entry.duty_id === dutyId) ?? null;
        const visibleDuty = duty ?? approvedDuty!;
        const add = entityAction(actions, "duties", dutyId, "add");
        const withdraw = entityAction(actions, "duties", dutyId, "withdraw");
        const statementChange = pathAction(actions, `/duties/${dutyId}/statement`);
        const dutyLabel = `Duty ${index + 1}`;
        return (
          <section
            key={dutyId}
            aria-label={`${dutyLabel} ${visibleDuty.statement}`}
            className={`rounded-2xl border p-4 ${withdraw ? "border-rose-200 bg-rose-50/45" : add ? "border-emerald-200 bg-emerald-50/40" : "border-stone-200 bg-stone-50/80"}`}
          >
            <div className="flex items-start gap-3">
              <span className="rounded-md bg-stone-900 px-2 py-1 text-[11px] font-semibold text-white">{dutyLabel}</span>
              <div className="min-w-0 flex-1">
                {statementChange ? (
                  <ReviewDiffValue label="職責名稱" current={visibleDuty.statement} action={statementChange} />
                ) : (
                  <h3 className={`text-lg font-semibold ${withdraw ? "text-rose-700 line-through" : ""}`}>{visibleDuty.statement}</h3>
                )}
                {add ? <p className="mt-1 text-xs font-medium text-emerald-700">新增職責</p> : null}
                {withdraw ? <p className="mt-1 text-xs font-medium text-rose-700">移除職責</p> : null}
              </div>
            </div>
            {taskCards(dutyId)}
          </section>
        );
      })}

      <section aria-label="尚未歸屬" className="rounded-2xl border border-dashed border-stone-300 bg-white p-4">
        <h3 className="text-lg font-semibold">尚未歸屬</h3>
        <p className="mt-1 text-sm text-stone-500">尚未分到 Duty／Task 的內容仍會清楚留在這裡。</p>
        {taskCards(null)}
        {currentUnassignedItems.length ? (
          <div className="mt-4 grid gap-2 sm:grid-cols-2">
            {currentUnassignedItems.map((item, index) => (
              <ReviewItemCard
                key={`unassigned:${item.item_id}`}
                item={item}
                approvedItem={approvedDocument.opks.find((entry) => entry.item_id === item.item_id) ?? null}
                label={`${itemKindCodes[item.kind]} ${index + 1}`}
                taskId={null}
                actions={actions}
              />
            ))}
          </div>
        ) : null}
      </section>

      {documentItems.length ? (
        <section aria-label="文件層級 A" className="rounded-2xl border border-stone-200 bg-white p-4">
          <h3 className="text-lg font-semibold">文件層級項目</h3>
          <div className="mt-4 grid gap-2 sm:grid-cols-2">
            {documentItems.map((item, index) => (
              <ReviewItemCard
                key={`document:${item.item_id}`}
                item={item}
                approvedItem={approvedDocument.opks.find((entry) => entry.item_id === item.item_id) ?? null}
                label={`A ${index + 1}`}
                taskId={null}
                actions={actions}
              />
            ))}
          </div>
        </section>
      ) : null}
    </section>
  );
}
