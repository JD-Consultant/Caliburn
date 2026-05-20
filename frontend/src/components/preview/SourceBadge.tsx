import { cn } from "@/lib/utils";

const LABEL_STYLES: Record<string, string> = {
  "[訪談確認]":
    "bg-blue-100 text-blue-700 border-blue-200 dark:bg-blue-950 dark:text-blue-300",
  "[AI整理]":
    "bg-violet-100 text-violet-700 border-violet-200 dark:bg-violet-950 dark:text-violet-300",
  "[iCAP參考]":
    "bg-amber-100 text-amber-700 border-amber-200 dark:bg-amber-950 dark:text-amber-300",
  "[待確認]":
    "bg-gray-100 text-gray-600 border-gray-200 dark:bg-gray-900 dark:text-gray-400",
};

export function SourceBadge({ label }: { label: string }) {
  const style =
    LABEL_STYLES[label] ??
    "bg-muted text-muted-foreground border-muted";
  return (
    <span
      className={cn(
        "inline-flex text-[10px] font-medium px-1.5 py-0.5 rounded border shrink-0",
        style,
      )}
    >
      {label}
    </span>
  );
}
