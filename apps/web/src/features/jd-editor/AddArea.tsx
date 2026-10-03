/**
 * The end-of-list row that adds a responsibility. It becomes the field for the new name right where the area
 * will appear, as the outcome and requirement lists already add theirs (Things adds at the end of its list
 * in place), instead of a form in a dialog; the scope is then filled in place like every other text. It is
 * the same editor as every inline edit, so Enter, Esc, a lost answer and a read-only JD all behave as they
 * do there.
 */
import { Button } from '@mui/material';
import { AddIcon } from '../../shared/ui/icons';
import { InlineEditor } from './InlineEditor';
import { useInlineEdit } from './inline-edit-context';
import { newAreaField } from './inline-fields';
import { useFocusReturn } from './use-focus-return';

export function AddArea() {
  const edit = useInlineEdit();
  const open = edit?.activeKey === newAreaField.key;
  const trigger = useFocusReturn(open);
  if (!edit) return null;
  if (open) return <InlineEditor edit={edit} field={newAreaField} />;
  return (
    <div>
      {/* aria-disabled, not disabled: after a save the page is briefly busy, and focus must still land here. */}
      <Button
        ref={trigger}
        size="small"
        className="add-action"
        startIcon={<AddIcon />}
        aria-disabled={!edit.canOpen}
        onClick={() => {
          if (edit.canOpen) edit.open(newAreaField.key);
        }}
      >
        新增職責
      </Button>
    </div>
  );
}
