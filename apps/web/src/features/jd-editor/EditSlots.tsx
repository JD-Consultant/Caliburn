/** Keeps the set of editors that currently hold the JD; the rule is in edit-slots-context.ts. */
import { useCallback, useMemo, useState } from 'react';
import type { ReactNode } from 'react';
import { EditSlotsContext } from './edit-slots-context';

export function EditSlots({ children }: { children: ReactNode }) {
  const [holders, setHolders] = useState<ReadonlySet<string>>(() => new Set());
  const hold = useCallback((holder: string, holding: boolean) => {
    setHolders((current) => {
      if (current.has(holder) === holding) return current;
      const next = new Set(current);
      if (holding) next.add(holder);
      else next.delete(holder);
      return next;
    });
  }, []);
  const value = useMemo(() => ({ holders, hold }), [holders, hold]);
  return <EditSlotsContext value={value}>{children}</EditSlotsContext>;
}
