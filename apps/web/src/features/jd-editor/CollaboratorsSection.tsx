/** Job-wide collaborators use the same revision and command boundary as other JD collections. */
import { Box, Button, Stack, Typography } from '@mui/material';
import type { Collaborator, JdWorkView } from '../../shared/api/generated/jd-work-view';
import type { WorkIntent } from './jd-work-api';
import type { WorkDialogContent } from './WorkDialog';
import { FoldableSection } from './FoldableSection';
import { InlineText } from './InlineText';
import { collaboratorNameField, collaboratorScopeField } from './inline-fields';
import { itemTarget, useSourceBadge } from './source-badge-context';
import { IconAction } from '../../shared/ui/IconAction';
import { AddIcon, ArrowDownIcon, ArrowUpIcon, CloseIcon } from '../../shared/ui/icons';

interface Props {
  baseline: JdWorkView;
  disabled: boolean;
  onCreate: (content: WorkDialogContent) => void;
  onChange: (intent: WorkIntent) => void;
  onDelete: (collaborator: Collaborator) => void;
}

export function CollaboratorsSection({ baseline, disabled, onCreate, onChange, onDelete }: Props) {
  const group = baseline.collaborators;
  const badge = useSourceBadge();
  function move(collaboratorId: string, beforeId: string | null): void {
    onChange({
      collection: 'collaborators',
      change: {
        action: 'reorder_collaborator',
        collaborator_id: collaboratorId,
        before_collaborator_id: beforeId,
      },
    });
  }
  return (
    <FoldableSection id="jd-collaborators" title="主要協作對象" count={group.length}>
      <Typography variant="body2" color="text.secondary">
        說明實際合作對象及分工，不以協作關係推定匯報或核准權限。
      </Typography>
      {group.length === 0 && <p>尚未提供協作對象</p>}
      {group.map((item, index) => (
        <Box
          component="article"
          aria-label={`協作對象：${item.name ?? '尚未命名'}`}
          key={item.collaborator_id}
          className="item jd-ruled-item"
        >
          <Stack direction="row" spacing={1} sx={{ alignItems: 'center', flexWrap: 'wrap' }}>
            <InlineText field={collaboratorNameField(item)}>
              <Typography component="h4" variant="subtitle1" sx={{ overflowWrap: 'anywhere' }}>
                {item.name ?? '名稱尚未提供'}
              </Typography>
            </InlineText>
            {badge(itemTarget('collaborator', item.collaborator_id))}
          </Stack>
          <InlineText field={collaboratorScopeField(item)}>
            <Typography sx={{ whiteSpace: 'pre-wrap', overflowWrap: 'anywhere' }}>
              {item.scope_text ?? '協作範圍尚未提供'}
            </Typography>
          </InlineText>
          <Stack
            direction="row"
            className="item-actions item-actions--corner"
            sx={{ flexWrap: 'wrap' }}
          >
            <IconAction
              label="上移協作對象"
              disabled={disabled || index === 0}
              onClick={() => move(item.collaborator_id, group[index - 1]?.collaborator_id ?? null)}
            >
              <ArrowUpIcon />
            </IconAction>
            <IconAction
              label="下移協作對象"
              disabled={disabled || index === group.length - 1}
              onClick={() => move(item.collaborator_id, group[index + 2]?.collaborator_id ?? null)}
            >
              <ArrowDownIcon />
            </IconAction>
            <IconAction
              label="刪除協作對象"
              disabled={disabled}
              color="error"
              onClick={() => onDelete(item)}
            >
              <CloseIcon />
            </IconAction>
          </Stack>
        </Box>
      ))}
      <div>
        <Button
          size="small"
          className="add-action"
          startIcon={<AddIcon />}
          disabled={disabled}
          onClick={() => onCreate({ kind: 'collaborator', baseline })}
        >
          新增協作對象
        </Button>
      </div>
    </FoldableSection>
  );
}
