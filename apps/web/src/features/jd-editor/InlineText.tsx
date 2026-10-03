/**
 * Click-to-edit text (Atlassian inline edit, Primer saving, Cloudscape inline edit): the read view stays the
 * caller's own element; opening swaps in one editor with explicit Save / Cancel. A real button carries the
 * same action for keyboards and screen readers, and a click on the text is only a shortcut to it.
 */
import type { ReactNode } from 'react';
import { InlineEditor } from './InlineEditor';
import { useInlineEdit } from './inline-edit-context';
import type { InlineField } from './inline-fields';
import { useFocusReturn } from './use-focus-return';

interface InlineTextProps {
  field: InlineField;
  /** The wrapper takes the layout role the read view had in its parent (a stack child, a flex item). */
  className?: string;
  /** For text that runs on into a badge or toolbar on the same line (list items, conditions). */
  inline?: boolean;
  children: ReactNode;
}

/** Dragging over text to copy it ends in a click; that is not a request to edit. */
function isSelectingText(): boolean {
  return (window.getSelection()?.toString() ?? '') !== '';
}

export function InlineText({ field, className, inline = false, children }: InlineTextProps) {
  const edit = useInlineEdit();
  const open = edit?.activeKey === field.key;
  const trigger = useFocusReturn(open);
  if (open && edit) return <InlineEditor edit={edit} field={field} />;
  const classes = ['inline-text', inline && 'inline-text--inline', className]
    .filter(Boolean)
    .join(' ');
  // Without an editor page around it (no provider) the same markup is plain text.
  if (!edit)
    return (
      <div className={classes} data-disabled="">
        {children}
      </div>
    );
  function openField(): void {
    if (edit?.canOpen) edit.open(field.key);
  }
  return (
    <div
      className={classes}
      data-disabled={edit.canOpen ? undefined : ''}
      onClick={() => {
        if (!isSelectingText()) openField();
      }}
    >
      {children}
      {/* aria-disabled, not disabled: a briefly busy page must not drop the keyboard focus parked here. */}
      <button
        type="button"
        ref={trigger}
        className="inline-text__edit"
        aria-label={`修改${field.label}`}
        aria-disabled={!edit.canOpen}
        onClick={(event) => {
          event.stopPropagation();
          openField();
        }}
      />
    </div>
  );
}
