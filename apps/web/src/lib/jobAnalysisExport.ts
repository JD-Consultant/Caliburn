export type ExportDirtyState = {
  header: boolean;
  duty: boolean;
  task: boolean;
  opks: boolean;
};

export function canExport(
  state: ExportDirtyState,
  mutationPending = false,
): boolean {
  return !mutationPending && !Object.values(state).some(Boolean);
}

export function exportFilename(title: string): string {
  const safeTitle = title
    .trim()
    .replace(/[<>:"/\\|?*\u0000-\u001f]/g, "_")
    .replace(/[. ]+$/g, "");
  return `${safeTitle || "職務說明書"}.xlsx`;
}
