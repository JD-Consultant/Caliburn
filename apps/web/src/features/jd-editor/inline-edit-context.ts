/**
 * What an inline text editor needs from the page, and nothing else. JdWorkEditor owns the one edit that may
 * be open and the command pipeline behind `save`; the text fields deep in the tree (AreaSection, TaskCard, ...)
 * reach it through this context instead of props. Outside the editor there is no provider, so the same
 * components render as plain read-only text.
 */
import { createContext, useContext } from 'react';
import type { InlineIntent } from './inline-fields';
import type { WorkStatusProps } from './WorkStatus';

/** `invalid`: the change is not a command the App can send (for example only whitespace); nothing left the editor. */
export type InlineSaveResult = 'submitted' | 'invalid';

export interface InlineEdit {
  /** The field whose editor is open, or null. At most one editor is open at a time. */
  activeKey: string | null;
  open: (key: string) => void;
  close: () => void;
  /** The JD revision on screen; an editor freezes it when it opens and saves against that, never a newer one. */
  revisionId: string;
  save: (revisionId: string, intent: InlineIntent) => InlineSaveResult;
  /** A field may be opened: not while a command is pending, the JD is loading or read-only, or an editor is open. */
  canOpen: boolean;
  /** An open editor's draft may be changed and saved: not while a command is pending or the JD is read-only. */
  canEdit: boolean;
  /** The command in flight, with the notice an open draft needs (it also explains a read-only JD). */
  status: WorkStatusProps;
  /** An open editor reports true while it is on screen and false when it goes, so the page cannot wait on one that vanished. */
  setEditorOpen: (open: boolean) => void;
}

export const InlineEditContext = createContext<InlineEdit | null>(null);

export function useInlineEdit(): InlineEdit | null {
  return useContext(InlineEditContext);
}
