/**
 * One manual edit at a time across the whole JD. The basic data and the collections are written by two
 * separate commands, yet both are written against the same formal revision: an open editor froze it, so
 * any other write (or an unconfirmed one) would make its save conflict. Each editor reports whether it
 * holds the JD (an editor is open, or a command is in flight, unconfirmed or rejected) and learns whether
 * another one does. With no provider around, an editor stands alone.
 */
import { createContext, useContext, useEffect, useId } from 'react';

export interface EditSlotsState {
  holders: ReadonlySet<string>;
  hold: (holder: string, holding: boolean) => void;
}

export const EditSlotsContext = createContext<EditSlotsState | null>(null);

/** `holding`: this editor needs the JD to stay as it is. Returns whether another editor holds it. */
export function useEditSlot(holding: boolean): { heldByAnother: boolean } {
  const slots = useContext(EditSlotsContext);
  const holder = useId();
  const hold = slots?.hold;
  useEffect(() => {
    hold?.(holder, holding);
    return () => hold?.(holder, false);
  }, [hold, holder, holding]);
  return { heldByAnother: slots ? [...slots.holders].some((other) => other !== holder) : false };
}
