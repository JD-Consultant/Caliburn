/** Derived groups do not mirror server state or imply inheritance by task. */
import { Box, Button, Paper, Stack, Typography } from '@mui/material';
import type { Condition, JdWorkView } from '../../shared/api/generated/jd-work-view';
import type { WorkIntent } from './jd-work-api';
import type { WorkEditing } from './WorkEditDialog';
import { conditionLabels } from './condition-labels';
import { itemTarget, useSourceBadge } from './source-badge-context';
import { IconAction } from '../../shared/ui/IconAction';
import { AddIcon, ArrowDownIcon, ArrowUpIcon, DeleteIcon, EditIcon } from '../../shared/ui/icons';

interface Props {
  baseline: JdWorkView;
  disabled: boolean;
  onEdit: (editing: WorkEditing) => void;
  onChange: (intent: WorkIntent) => void;
  onDelete: (condition: Condition) => void;
}

export function ConditionsSection({ baseline, disabled, onEdit, onChange, onDelete }: Props) {
  const badge = useSourceBadge();
  function move(conditionId: string, beforeId: string | null): void {
    onChange({
      collection: 'conditions',
      change: {
        action: 'reorder_condition',
        condition_id: conditionId,
        before_condition_id: beforeId,
      },
    });
  }
  return (
    <Paper
      component="section"
      id="jd-conditions"
      aria-label="工作條件與責任邊界"
      variant="outlined"
      sx={{ p: { xs: 1.5, sm: 2 } }}
    >
      <Stack spacing={2}>
        <Typography component="h3" variant="h6">
          工作條件與責任邊界
        </Typography>
        <Typography color="text.secondary">
          只集中跨任務共通的條件。未提供不等於不需要，不會自動套用到各任務。
        </Typography>
        {baseline.conditions.length === 0 && <p>尚未提供共通條件</p>}
        {Object.entries(conditionLabels).map(([kind, label]) => {
          const group = baseline.conditions.filter((item) => item.kind === kind);
          if (group.length === 0) return null;
          return (
            <Box component="section" key={kind} aria-label={label}>
              <Typography component="h4" variant="subtitle1">
                {label}
              </Typography>
              {group.map((item, index) => (
                <Box
                  component="article"
                  key={item.condition_id}
                  aria-label={`${label} ${String(index + 1)}`}
                  className="item"
                  sx={{ mt: 1 }}
                >
                  <Typography
                    sx={{ whiteSpace: 'pre-wrap', overflowWrap: 'anywhere', display: 'inline' }}
                  >
                    {item.text}
                  </Typography>
                  {badge(itemTarget('condition', item.condition_id))}
                  <Stack
                    direction="row"
                    className="item-actions item-actions--corner"
                    sx={{ flexWrap: 'wrap' }}
                  >
                    <IconAction
                      label="編輯條件"
                      disabled={disabled}
                      onClick={() => onEdit({ kind: 'condition', baseline, condition: item })}
                    >
                      <EditIcon />
                    </IconAction>
                    <IconAction
                      label="上移條件"
                      disabled={disabled || index === 0}
                      onClick={() =>
                        move(item.condition_id, group[index - 1]?.condition_id ?? null)
                      }
                    >
                      <ArrowUpIcon />
                    </IconAction>
                    <IconAction
                      label="下移條件"
                      disabled={disabled || index === group.length - 1}
                      onClick={() =>
                        move(item.condition_id, group[index + 2]?.condition_id ?? null)
                      }
                    >
                      <ArrowDownIcon />
                    </IconAction>
                    <IconAction
                      label="刪除條件"
                      disabled={disabled}
                      color="error"
                      onClick={() => onDelete(item)}
                    >
                      <DeleteIcon />
                    </IconAction>
                  </Stack>
                </Box>
              ))}
            </Box>
          );
        })}
        <div>
          <Button
            size="small"
            startIcon={<AddIcon />}
            disabled={disabled}
            onClick={() => onEdit({ kind: 'condition', baseline })}
          >
            新增條件
          </Button>
        </div>
      </Stack>
    </Paper>
  );
}
