export type TextDraft = { value: string; baseValue: string | null; label: string };
export type TextDrafts = Record<string, TextDraft>;

function storageKey(workspaceId: string, jdId: string) {
  return `caliburn:jd-drafts:${workspaceId.toLowerCase()}:${jdId.toLowerCase()}`;
}

export function loadDrafts(workspaceId: string, jdId: string): TextDrafts {
  try {
    const raw = sessionStorage.getItem(storageKey(workspaceId, jdId));
    if (!raw) return {};
    const parsed: unknown = JSON.parse(raw);
    if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed)) return {};
    return Object.fromEntries(
      Object.entries(parsed).filter((entry): entry is [string, TextDraft] => {
        const value: unknown = entry[1];
        return (
          !!value &&
          typeof value === 'object' &&
          'value' in value &&
          typeof value.value === 'string' &&
          'label' in value &&
          typeof value.label === 'string' &&
          'baseValue' in value &&
          (value.baseValue === null || typeof value.baseValue === 'string')
        );
      }),
    );
  } catch {
    return {};
  }
}

export function storeDrafts(
  workspaceId: string,
  jdId: string,
  drafts: Readonly<TextDrafts>,
): boolean {
  try {
    const key = storageKey(workspaceId, jdId);
    if (Object.keys(drafts).length) sessionStorage.setItem(key, JSON.stringify(drafts));
    else sessionStorage.removeItem(key);
    return true;
  } catch {
    return false;
  }
}

export function hasStoredDrafts(workspaceId: string, jdId: string): boolean {
  return Object.keys(loadDrafts(workspaceId, jdId)).length > 0;
}
