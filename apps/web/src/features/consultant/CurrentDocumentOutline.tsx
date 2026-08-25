"use client";

import type { ApprovedJobDocumentWrite } from "@caliburn/job-analysis-contract";
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
