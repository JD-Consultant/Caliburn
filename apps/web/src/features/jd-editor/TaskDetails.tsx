/**
 * One list of a task, its outcomes or its requirements: each item's text is edited in place, ordered and
 * removed there. A "+" beside the list's label adds an item at the end, as Linear's sub-issues header does.
 */
import { Box, Typography } from '@mui/material';
import type { Detail } from '../../shared/api/generated/jd-work-view';
import { IconAction } from '../../shared/ui/IconAction';
import { AddIcon, ArrowDownIcon, ArrowUpIcon, CloseIcon } from '../../shared/ui/icons';
import { InlineEditor } from './InlineEditor';
import { InlineText } from './InlineText';
import { useInlineEdit } from './inline-edit-context';
import { detailTextField, newDetailField } from './inline-fields';
import { detailTarget, useSourceBadge } from './source-badge-context';
import { useFocusReturn } from './use-focus-return';

type DetailKind = 'outcome' | 'requirement';
const labels: Record<DetailKind, string> = { outcome: '工作成果', requirement: '工作要求' };

interface TaskDetailsProps {
  taskId: string;
  kind: DetailKind;
  details: readonly Detail[];
  disabled: boolean;
  onMove: (detailId: string, beforeId: string | null) => void;
  onRemove: (detail: Detail, label: string) => void;
}

export function TaskDetails({
  taskId,
  kind,
  details,
  disabled,
  onMove,
  onRemove,
}: TaskDetailsProps) {
  const edit = useInlineEdit();
  const badge = useSourceBadge();
  const label = labels[kind];
  const addField = newDetailField(taskId, kind, `${label} ${String(details.length + 1)}`);
  const adding = edit?.activeKey === addField.key;
  const addButton = useFocusReturn(adding);
  return (
    <Box className="jd-details">
      <div className="jd-details__head">
        <Typography component="h5" variant="overline" className="jd-label">
          {label}
        </Typography>
        {edit && (
          // aria-disabled, not disabled: a briefly busy page must not drop the keyboard focus parked here.
          <IconAction
            ref={addButton}
            label={`新增${label}`}
            className="jd-add-detail"
            aria-disabled={!edit.canOpen}
            onClick={() => {
              if (edit.canOpen) edit.open(addField.key);
            }}
          >
            <AddIcon />
          </IconAction>
        )}
      </div>
      {details.length === 0 ? (
        <Typography variant="body2" className="jd-empty">
          尚未提供
        </Typography>
      ) : (
        <Box component="ol" sx={{ pl: 3, my: 1 }}>
          {details.map((detail, index) => (
            <li key={detail.detail_id} className="item">
              <InlineText
                field={detailTextField(taskId, detail, `${label} ${String(index + 1)}`)}
                inline
              >
                <Typography
                  sx={{ whiteSpace: 'pre-wrap', overflowWrap: 'anywhere', display: 'inline' }}
                >
                  {detail.text}
                </Typography>
              </InlineText>
              {badge(detailTarget(taskId, detail.detail_id))}
              <span className="item-actions">
                <IconAction
                  label={`上移${label} ${String(index + 1)}`}
                  disabled={disabled || index === 0}
                  onClick={() => onMove(detail.detail_id, details[index - 1]?.detail_id ?? null)}
                >
                  <ArrowUpIcon />
                </IconAction>
                <IconAction
                  label={`下移${label} ${String(index + 1)}`}
                  disabled={disabled || index === details.length - 1}
                  onClick={() => onMove(detail.detail_id, details[index + 2]?.detail_id ?? null)}
                >
                  <ArrowDownIcon />
                </IconAction>
                <IconAction
                  label={`刪除${label} ${String(index + 1)}`}
                  color="error"
                  disabled={disabled}
                  onClick={() => onRemove(detail, label)}
                >
                  <CloseIcon />
                </IconAction>
              </span>
            </li>
          ))}
        </Box>
      )}
      {adding && edit && <InlineEditor edit={edit} field={addField} />}
    </Box>
  );
}
