/** Derived groups do not mirror server state or imply inheritance by task. */
import { Box, Button, Stack, Typography } from '@mui/material';
import type { ConditionKind } from '../../shared/api/generated/edit-jd-conditions-request';
import type { Condition, JdWorkView } from '../../shared/api/generated/jd-work-view';
import type { WorkIntent } from './jd-work-api';
import type { WorkDialogContent } from './WorkDialog';
import { conditionLabels, isConditionKind } from './condition-labels';
import { FoldableSection } from './FoldableSection';
import { InlineText } from './InlineText';
import { conditionTextField } from './inline-fields';
import { MoveMenu } from './MoveMenu';
import { itemTarget, useSourceBadge } from './source-badge-context';
import { IconAction } from '../../shared/ui/IconAction';
import { AddIcon, ArrowDownIcon, ArrowUpIcon, CloseIcon } from '../../shared/ui/icons';

interface Props {
  baseline: JdWorkView;
  disabled: boolean;
  onCreate: (content: WorkDialogContent) => void;
  onChange: (intent: WorkIntent) => void;
  onDelete: (condition: Condition) => void;
}

export function ConditionsSection({ baseline, disabled, onCreate, onChange, onDelete }: Props) {
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
  /** Keeps the condition's identity; the server places it last in the new category. */
  function reclassify(conditionId: string, kind: ConditionKind): void {
    onChange({
      collection: 'conditions',
      change: {
        action: 'revise_condition',
        condition_id: conditionId,
        changes: [{ field: 'kind', value: kind }],
      },
    });
  }
  return (
    <FoldableSection
      id="jd-conditions"
      title="工作條件與責任邊界"
      count={baseline.conditions.length}
    >
      <Typography variant="body2" color="text.secondary">
        只集中跨任務共通的條件。未提供不等於不需要，不會自動套用到各任務。
      </Typography>
      {baseline.conditions.length === 0 && <p>尚未提供共通條件</p>}
      {Object.entries(conditionLabels).map(([kind, label]) => {
        const group = baseline.conditions.filter((item) => item.kind === kind);
        if (group.length === 0) return null;
        return (
          <Box component="section" key={kind} aria-label={label}>
            <Typography component="h4" variant="overline" className="jd-label">
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
                <InlineText field={conditionTextField(item)} inline>
                  <Typography
                    sx={{ whiteSpace: 'pre-wrap', overflowWrap: 'anywhere', display: 'inline' }}
                  >
                    {item.text}
                  </Typography>
                </InlineText>
                {badge(itemTarget('condition', item.condition_id))}
                <Stack
                  direction="row"
                  className="item-actions item-actions--corner"
                  sx={{ flexWrap: 'wrap' }}
                >
                  <IconAction
                    label="上移條件"
                    disabled={disabled || index === 0}
                    onClick={() => move(item.condition_id, group[index - 1]?.condition_id ?? null)}
                  >
                    <ArrowUpIcon />
                  </IconAction>
                  <IconAction
                    label="下移條件"
                    disabled={disabled || index === group.length - 1}
                    onClick={() => move(item.condition_id, group[index + 2]?.condition_id ?? null)}
                  >
                    <ArrowDownIcon />
                  </IconAction>
                  <MoveMenu
                    label="移到其他分類"
                    heading="移到分類"
                    destinations={Object.entries(conditionLabels).map(([value, text]) => ({
                      value,
                      label: text,
                    }))}
                    current={item.kind}
                    disabled={disabled}
                    onMove={(value) => {
                      if (isConditionKind(value)) reclassify(item.condition_id, value);
                    }}
                  />
                  <IconAction
                    label="刪除條件"
                    disabled={disabled}
                    color="error"
                    onClick={() => onDelete(item)}
                  >
                    <CloseIcon />
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
          className="add-action"
          startIcon={<AddIcon />}
          disabled={disabled}
          onClick={() => onCreate({ kind: 'condition', baseline })}
        >
          新增條件
        </Button>
      </div>
    </FoldableSection>
  );
}
