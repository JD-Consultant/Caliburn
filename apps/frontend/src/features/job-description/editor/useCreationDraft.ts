import { useJobDescriptionEditor } from '../editing/useJobDescriptionEditor';

/** 新增表單保留未提交輸入；重載只恢復表單，不重播寫入。 */
export function useCreationDraft<T>(
  key: string,
  label: string,
  initial: T,
  isValid: (value: unknown) => value is T,
) {
  const editor = useJobDescriptionEditor();
  const stored = editor.drafts[key];
  let value = initial;
  if (stored) {
    try {
      const parsed: unknown = JSON.parse(stored.value);
      if (isValid(parsed)) value = parsed;
    } catch {
      /* 舊版或損壞的暫存仍由上層保留，不能假定內容有效。 */
    }
  }
  return {
    value,
    setValue: (next: T) =>
      editor.setDraft(key, { value: JSON.stringify(next), label, baseValue: null }),
    discard: () => editor.discardDraft(key),
  };
}

export function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
}
