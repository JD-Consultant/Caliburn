/** Job-wide collaborators use the same revision and command boundary as other JD collections. */
import { Box, Button, Paper, Stack, Typography } from '@mui/material';
import type { Collaborator, JdWorkView } from '../../shared/api/generated/jd-work-view';
import type { WorkIntent } from './jd-work-api';
import type { WorkEditing } from './WorkEditDialog';

interface Props {
  baseline: JdWorkView;
  disabled: boolean;
  onEdit: (editing: WorkEditing) => void;
  onChange: (intent: WorkIntent) => void;
  onDelete: (collaborator: Collaborator) => void;
}

export function CollaboratorsSection({ baseline, disabled, onEdit, onChange, onDelete }: Props) {
  const group = baseline.collaborators;
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
    <Paper
      component="section"
      aria-label="主要協作對象"
      variant="outlined"
      sx={{ p: { xs: 1.5, sm: 2 } }}
    >
      <Stack spacing={2}>
        <Typography component="h3" variant="h6">
          主要協作對象
        </Typography>
        <Typography color="text.secondary">
          說明實際合作對象及分工，不以協作關係推定匯報或核准權限。
        </Typography>
        {group.length === 0 && <p>尚未提供協作對象</p>}
        {group.map((item, index) => (
          <Box
            component="article"
            aria-label={`協作對象：${item.name ?? '尚未命名'}`}
            key={item.collaborator_id}
            sx={{ borderTop: 1, borderColor: 'divider', pt: 2 }}
          >
            <Typography component="h4" variant="subtitle1" sx={{ overflowWrap: 'anywhere' }}>
              {item.name ?? '名稱尚未提供'}
            </Typography>
            <Typography sx={{ whiteSpace: 'pre-wrap', overflowWrap: 'anywhere' }}>
              {item.scope_text ?? '協作範圍尚未提供'}
            </Typography>
            <Stack direction="row" sx={{ flexWrap: 'wrap' }}>
              <Button
                disabled={disabled}
                onClick={() => onEdit({ kind: 'collaborator', baseline, collaborator: item })}
              >
                編輯協作對象
              </Button>
              <Button
                disabled={disabled || index === 0}
                onClick={() =>
                  move(item.collaborator_id, group[index - 1]?.collaborator_id ?? null)
                }
              >
                上移協作對象
              </Button>
              <Button
                disabled={disabled || index === group.length - 1}
                onClick={() =>
                  move(item.collaborator_id, group[index + 2]?.collaborator_id ?? null)
                }
              >
                下移協作對象
              </Button>
              <Button disabled={disabled} color="error" onClick={() => onDelete(item)}>
                刪除協作對象
              </Button>
            </Stack>
          </Box>
        ))}
        <div>
          <Button disabled={disabled} onClick={() => onEdit({ kind: 'collaborator', baseline })}>
            新增協作對象
          </Button>
        </div>
      </Stack>
    </Paper>
  );
}
