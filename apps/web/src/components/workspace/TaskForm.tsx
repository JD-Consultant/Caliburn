"use client";

import type { DutyView } from "@caliburn/job-analysis-contract";
import { Plus, Trash2 } from "lucide-react";

import { Button } from "@/components/ui/button";
import { TASK_COMPETENCY_LEVELS } from "@/lib/jobAnalysisDuties";
import type { TaskFormValue } from "@/lib/jobAnalysisForm";

interface TaskFormProps {
  value: TaskFormValue;
  duties: readonly DutyView[];
  onChange: (value: TaskFormValue) => void;
  onSave: () => void;
  onCancel: () => void;
  isSaving: boolean;
  canSave: boolean;
  error?: string;
}

export function TaskForm({
  value,
  duties,
  onChange,
  onSave,
  onCancel,
  isSaving,
  canSave,
  error,
}: TaskFormProps) {
  const set = <K extends keyof TaskFormValue>(key: K, next: TaskFormValue[K]) =>
    onChange({ ...value, [key]: next });

  return (
    <form
      className="space-y-5"
      onSubmit={(event) => {
        event.preventDefault();
        onSave();
      }}
      onKeyDown={(event) => {
        if (event.key === "Enter" && (event.ctrlKey || event.metaKey)) {
          event.preventDefault();
          onSave();
        } else if (event.key === "Escape") {
          event.preventDefault();
          onCancel();
        }
      }}
    >
      <label className="block space-y-1.5">
        <span className="text-sm font-medium">工作敘述</span>
        <textarea
          className="min-h-24 w-full rounded-lg border bg-background px-3 py-2 text-sm"
          value={value.statement}
          onChange={(event) => set("statement", event.target.value)}
          placeholder="例如：每週彙整營運週報"
          autoFocus
        />
      </label>

      <div className="grid gap-4 md:grid-cols-2">
        <label className="block space-y-1.5">
          <span className="text-sm font-medium">目的／結果</span>
          <input
            className="w-full rounded-lg border bg-background px-3 py-2 text-sm"
            value={value.purposeResult}
            onChange={(event) => set("purposeResult", event.target.value)}
            placeholder="尚未填寫"
          />
        </label>
        <label className="block space-y-1.5">
          <span className="text-sm font-medium">情境／條件</span>
          <input
            className="w-full rounded-lg border bg-background px-3 py-2 text-sm"
            value={value.context}
            onChange={(event) => set("context", event.target.value)}
            placeholder="尚未填寫"
          />
        </label>
        <label className="block space-y-1.5">
          <span className="text-sm font-medium">頻率</span>
          <input
            className="w-full rounded-lg border bg-background px-3 py-2 text-sm"
            value={value.frequencyText}
            onChange={(event) => set("frequencyText", event.target.value)}
            placeholder="尚未填寫"
          />
        </label>
        <label className="block space-y-1.5">
          <span className="text-sm font-medium">責任角色</span>
          <select
            className="w-full rounded-lg border bg-background px-3 py-2 text-sm"
            value={value.responsibilityRole}
            onChange={(event) =>
              set(
                "responsibilityRole",
                event.target.value as TaskFormValue["responsibilityRole"],
              )
            }
          >
            <option value="">尚未填寫</option>
            <option value="primary">主要負責</option>
            <option value="shared">共同負責</option>
            <option value="assist">協助</option>
          </select>
        </label>
      </div>

      <div className="grid gap-4 md:grid-cols-2">
        <label className="block space-y-1.5">
          <span className="text-sm font-medium">所屬主要職責</span>
          <select
            className="w-full rounded-lg border bg-background px-3 py-2 text-sm"
            value={value.dutyId ?? ""}
            onChange={(event) => set("dutyId", event.target.value || null)}
          >
            <option value="">尚未歸入主要職責</option>
            {duties.map((duty) => (
              <option key={duty.duty_id} value={duty.duty_id}>
                {duty.statement}
              </option>
            ))}
          </select>
          {duties.length === 0 ? (
            <span className="block text-xs text-muted-foreground">
              先在上方新增主要職責，才能歸入。
            </span>
          ) : null}
        </label>
        <label className="block space-y-1.5">
          <span className="text-sm font-medium">職能級別</span>
          <select
            className="w-full rounded-lg border bg-background px-3 py-2 text-sm"
            value={value.competencyLevel === null ? "" : String(value.competencyLevel)}
            onChange={(event) =>
              set(
                "competencyLevel",
                event.target.value ? Number(event.target.value) : null,
              )
            }
          >
            <option value="">尚未填寫</option>
            {TASK_COMPETENCY_LEVELS.map((level) => (
              <option key={level} value={level}>
                第 {level} 級
              </option>
            ))}
          </select>
        </label>
      </div>

      <fieldset className="space-y-3" aria-labelledby="enablers-label">
        <div className="flex items-center justify-between">
          <span id="enablers-label" className="text-sm font-medium">
            工具／方法／知識／技能
          </span>
          <Button
            type="button"
            variant="outline"
            size="sm"
            onClick={() =>
              set("enablers", [...value.enablers, { kind: "other", name: "" }])
            }
          >
            <Plus />
            新增
          </Button>
        </div>
        {value.enablers.length === 0 ? (
          <p className="text-sm text-muted-foreground">尚未填寫</p>
        ) : (
          value.enablers.map((enabler, index) => (
            <div className="flex items-end gap-2" key={index}>
              <label className="space-y-1 text-xs text-muted-foreground">
                類型
                <select
                  className="block rounded-lg border bg-background px-2 py-2 text-sm text-foreground"
                  value={enabler.kind}
                  onChange={(event) => {
                    const enablers = [...value.enablers];
                    enablers[index] = {
                      ...enabler,
                      kind: event.target.value as typeof enabler.kind,
                    };
                    set("enablers", enablers);
                  }}
                >
                  <option value="tool_system">工具／系統</option>
                  <option value="method">方法</option>
                  <option value="knowledge">知識</option>
                  <option value="skill">技能</option>
                  <option value="other">其他</option>
                </select>
              </label>
              <label className="min-w-0 flex-1 space-y-1 text-xs text-muted-foreground">
                名稱
                <input
                  className="block w-full rounded-lg border bg-background px-3 py-2 text-sm text-foreground"
                  value={enabler.name}
                  onChange={(event) => {
                    const enablers = [...value.enablers];
                    enablers[index] = { ...enabler, name: event.target.value };
                    set("enablers", enablers);
                  }}
                  placeholder="尚未填寫"
                />
              </label>
              <Button
                type="button"
                variant="ghost"
                size="icon"
                aria-label={`移除第 ${index + 1} 項`}
                onClick={() =>
                  set(
                    "enablers",
                    value.enablers.filter((_, itemIndex) => itemIndex !== index),
                  )
                }
              >
                <Trash2 />
              </Button>
            </div>
          ))
        )}
      </fieldset>

      <div aria-live="polite" className="min-h-5 text-sm text-destructive">
        {error}
      </div>
      <div className="flex gap-2">
        <Button
          type="submit"
          disabled={!value.statement.trim() || !canSave || isSaving}
        >
          {isSaving ? "儲存中…" : "儲存"}
        </Button>
        <Button type="button" variant="ghost" onClick={onCancel}>
          取消
        </Button>
        <span className="self-center text-xs text-muted-foreground">
          Ctrl/Cmd+Enter 儲存 · Esc 取消
        </span>
      </div>
    </form>
  );
}
