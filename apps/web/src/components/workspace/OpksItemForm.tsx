"use client";

import { Button } from "@/components/ui/button";

export function OpksItemForm({
  label,
  value,
  onChange,
  onSave,
  onCancel,
  isSaving,
  error,
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  onSave: () => void;
  onCancel: () => void;
  isSaving: boolean;
  error?: string;
}) {
  return (
    <form
      className="space-y-3 rounded-lg border p-3"
      onSubmit={(event) => {
        event.preventDefault();
        onSave();
      }}
      onKeyDown={(event) => {
        if (event.key === "Escape") {
          event.preventDefault();
          onCancel();
        }
        if (event.key === "Enter" && (event.ctrlKey || event.metaKey)) {
          event.preventDefault();
          onSave();
        }
      }}
    >
      <label className="block space-y-1">
        <span className="text-xs font-medium text-muted-foreground">{label}</span>
        <textarea
          autoFocus
          className="min-h-20 w-full rounded-lg border bg-background px-3 py-2 text-sm"
          value={value}
          onChange={(event) => onChange(event.target.value)}
        />
      </label>
      <div className="flex items-center gap-2">
        <Button type="submit" size="sm" disabled={isSaving || !value.trim()}>
          {isSaving ? "儲存中…" : "儲存"}
        </Button>
        <Button type="button" size="sm" variant="ghost" onClick={onCancel}>
          取消
        </Button>
      </div>
      <p className="text-xs text-muted-foreground">
        Ctrl/Cmd+Enter 儲存 · Esc 取消
      </p>
      {error ? (
        <p role="alert" className="text-sm text-destructive">
          {error}
        </p>
      ) : null}
    </form>
  );
}
