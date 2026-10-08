/** The open editor of one inline field: a draft, explicit Save / Cancel, Esc to leave. It never rebases the draft. */
import { useEffect, useState } from 'react';
import { TextField } from '@mui/material';
import { IconAction } from '../../shared/ui/IconAction';
import { CheckIcon, CloseIcon } from '../../shared/ui/icons';
import type { InlineEdit } from './inline-edit-context';
import type { InlineField } from './inline-fields';
import { WorkStatus } from './WorkStatus';

/**
 * Focus the field and bring the whole form into view: focusing alone scrolls only far enough to show the field,
 * which near the bottom of the pane would hide Save and Cancel (and on a phone, where they are the way out).
 */
function focusAtEnd(element: HTMLInputElement | HTMLTextAreaElement | null): void {
  if (!element) return;
  element.focus({ preventScroll: true });
  element.setSelectionRange(element.value.length, element.value.length);
  const form = element.closest('form');
  // jsdom has no layout and no scrollIntoView.
  if (form && typeof form.scrollIntoView === 'function') form.scrollIntoView({ block: 'nearest' });
}

export function InlineEditor({ edit, field }: { edit: InlineEdit; field: InlineField }) {
  // 開啟時固定比較基準與修訂，背景更新不能改變草稿是否已修改的判定。
  const [initial] = useState(field.value ?? '');
  const [draft, setDraft] = useState(initial);
  const [problem, setProblem] = useState<string | null>(null);
  const [revisionId] = useState(edit.revisionId);
  const { canEdit, status, setEditorOpen } = edit;
  useEffect(() => {
    setEditorOpen(true);
    return () => setEditorOpen(false);
  }, [setEditorOpen]);
  function submit(): void {
    if (!canEdit) return;
    if (draft === initial) {
      edit.close();
      return;
    }
    if (edit.save(revisionId, field.intentFor(draft)) === 'invalid')
      setProblem(`${field.label}不能是空白，也不能包含無法儲存的字元。`);
  }
  return (
    <form
      className="inline-edit"
      onSubmit={(event) => {
        event.preventDefault();
        submit();
      }}
      onKeyDown={(event) => {
        if (event.nativeEvent.isComposing) return;
        if (event.key === 'Escape') {
          if (!status.isSending) edit.close();
        } else if (field.multiline && event.key === 'Enter' && (event.ctrlKey || event.metaKey)) {
          event.preventDefault();
          event.currentTarget.requestSubmit();
        }
      }}
    >
      <TextField
        size="small"
        fullWidth
        multiline={field.multiline}
        value={draft}
        disabled={!canEdit}
        onChange={(event) => {
          setDraft(event.target.value);
          setProblem(null);
        }}
        inputRef={focusAtEnd}
        slotProps={{ htmlInput: { 'aria-label': field.label } }}
      />
      <WorkStatus {...status} message={status.message ?? problem} />
      {/* Confirm and dismiss as icons at the end of the field, confirm first (Atlassian inline edit,
          PatternFly, Cloudscape); the hints name the keys that do the same. */}
      <div className="inline-edit__actions">
        {!status.canConfirm && (
          <IconAction
            type="submit"
            label="儲存"
            hint={field.multiline ? '儲存（Ctrl／⌘＋Enter）' : '儲存（Enter）'}
            className="inline-edit__save"
            disabled={!canEdit}
          >
            <CheckIcon />
          </IconAction>
        )}
        <IconAction
          label="取消"
          hint="取消（Esc）"
          disabled={status.isSending}
          onClick={edit.close}
        >
          <CloseIcon />
        </IconAction>
      </div>
    </form>
  );
}
