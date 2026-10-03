/** Where the reader is in the sheet: the list, or one source's text or changes. */
import { useState } from 'react';

export interface SourceSelection {
  citationId: string;
  view: 'content' | 'changes';
}

interface Choice {
  listKey: string;
  selection: SourceSelection | null;
}

/**
 * The place is bound to the list read it was made on: reading the list again (a new `listKey`) drops it
 * and falls back to `initial`, so a stale revision's text or changes can never stay open. `back` also
 * remembers which source to hand focus to when the list is shown again.
 */
export function useSourceSelection(listKey: string, initial: SourceSelection | null) {
  const [choice, setChoice] = useState<Choice | null>(null);
  const [returnTo, setReturnTo] = useState<string | null>(null);
  const selected = choice?.listKey === listKey ? choice.selection : initial;
  return {
    selected,
    returnTo,
    open: (selection: SourceSelection) => setChoice({ listKey, selection }),
    back: () => {
      if (selected) setReturnTo(selected.citationId);
      setChoice({ listKey, selection: null });
    },
  };
}
