import { useRef, useState } from 'react';
import { Alert, Button, Dialog, DialogActions, DialogContent, DialogTitle } from '@mui/material';
import type {
  Area,
  Capability,
  Collaborator,
  Condition,
  JdWorkView,
  WorkTask,
} from '../../shared/api/generated/jd-work-view';
import type { WorkCommand } from './jd-work-api';
import { AreaFields } from './AreaFields';
import { TaskFields } from './TaskFields';
import { CapabilityFields } from './CapabilityFields';
import { CollaboratorFields } from './CollaboratorFields';
import { ConditionFields } from './ConditionFields';
import { focusDialogInput } from './dialog-focus';

export type WorkEditing =
  | { kind: 'area'; baseline: JdWorkView; area?: Area }
  | { kind: 'task'; baseline: JdWorkView; task?: WorkTask; areaId: string | null }
  | {
      kind: 'capability';
      baseline: JdWorkView;
      capabilityKind: Capability['kind'];
      capability?: Capability;
    }
  | { kind: 'collaborator'; baseline: JdWorkView; collaborator?: Collaborator }
  | { kind: 'condition'; baseline: JdWorkView; condition?: Condition }
  | { kind: 'confirm'; title: string; description: string; command: WorkCommand };

interface Props {
  editing: WorkEditing;
  locked: boolean;
  isSending: boolean;
  canRetry: boolean;
  message: string | null;
  pending: WorkCommand | null;
  onSubmit: (command: WorkCommand) => Promise<void>;
  onClose: () => void;
  onReload: () => void;
}

function dialogTitle(editing: WorkEditing): string {
  if (editing.kind === 'area') return editing.area ? '編輯職責' : '新增職責';
  if (editing.kind === 'task') return editing.task ? '編輯任務' : '新增任務';
  if (editing.kind === 'capability')
    return `${editing.capability ? '編輯' : '新增'}${editing.capabilityKind === 'knowledge' ? '知識' : '技能'}`;
  if (editing.kind === 'collaborator')
    return editing.collaborator ? '編輯協作對象' : '新增協作對象';
  if (editing.kind === 'condition') return editing.condition ? '編輯條件' : '新增條件';
  return editing.title;
}

function formAction(editing: WorkEditing): { id: string; label: string } | null {
  switch (editing.kind) {
    case 'area':
      return { id: 'jd-area-form', label: '儲存職責' };
    case 'task':
      return { id: 'jd-task-form', label: '儲存任務' };
    case 'capability':
      return {
        id: 'jd-capability-form',
        label: editing.capabilityKind === 'knowledge' ? '儲存知識' : '儲存技能',
      };
    case 'confirm':
      return null;
    case 'collaborator':
      return { id: 'jd-collaborator-form', label: '儲存協作對象' };
    case 'condition':
      return { id: 'jd-condition-form', label: '儲存條件' };
  }
}

export function WorkEditDialog({
  editing,
  locked,
  isSending,
  canRetry,
  message,
  pending,
  onSubmit,
  onClose,
  onReload,
}: Props) {
  const [localError, setLocalError] = useState<string | null>(null);
  const titleInput = useRef<HTMLInputElement>(null);
  const title = dialogTitle(editing);
  const action = formAction(editing);
  return (
    <Dialog
      open
      fullWidth
      maxWidth="sm"
      onClose={isSending ? undefined : onClose}
      aria-labelledby="work-edit-title"
      slotProps={{ transition: { onEntered: () => focusDialogInput(titleInput.current) } }}
    >
      <DialogTitle id="work-edit-title">{title}</DialogTitle>
      <DialogContent>
        {(message ?? localError) && <Alert severity="warning">{message ?? localError}</Alert>}
        {editing.kind === 'area' && (
          <AreaFields
            titleInput={titleInput}
            revisionId={editing.baseline.revision_id}
            area={editing.area}
            disabled={locked}
            onSubmit={onSubmit}
            onError={setLocalError}
          />
        )}
        {editing.kind === 'task' && (
          <TaskFields
            titleInput={titleInput}
            baseline={editing.baseline}
            task={editing.task}
            areaId={editing.areaId}
            disabled={locked}
            onSubmit={onSubmit}
            onError={setLocalError}
          />
        )}
        {editing.kind === 'confirm' && (
          <>
            <p>{editing.description}</p>
            <Button
              variant="contained"
              disabled={locked}
              onClick={() => {
                void onSubmit(editing.command);
              }}
            >
              確認{title}
            </Button>
          </>
        )}
        {editing.kind === 'capability' && (
          <CapabilityFields
            titleInput={titleInput}
            revisionId={editing.baseline.revision_id}
            kind={editing.capabilityKind}
            capability={editing.capability}
            disabled={locked}
            onSubmit={onSubmit}
            onError={setLocalError}
          />
        )}
        {editing.kind === 'collaborator' && (
          <CollaboratorFields
            titleInput={titleInput}
            revisionId={editing.baseline.revision_id}
            collaborator={editing.collaborator}
            disabled={locked}
            onSubmit={onSubmit}
            onError={setLocalError}
          />
        )}
        {editing.kind === 'condition' && (
          <ConditionFields
            titleInput={titleInput}
            revisionId={editing.baseline.revision_id}
            condition={editing.condition}
            disabled={locked}
            onSubmit={onSubmit}
            onError={setLocalError}
          />
        )}
      </DialogContent>
      <DialogActions sx={{ flexWrap: 'wrap', px: 3, pb: 2 }}>
        <Button disabled={isSending} onClick={onClose}>
          返回 JD
        </Button>
        {action && !pending && (
          <Button type="submit" form={action.id} variant="contained" disabled={locked}>
            {action.label}
          </Button>
        )}
        {pending && (
          <Button
            disabled={isSending || !canRetry}
            onClick={() => {
              void onSubmit(pending);
            }}
          >
            重新確認修改結果
          </Button>
        )}
        {locked && !pending && !isSending && <Button onClick={onReload}>讀取目前 JD</Button>}
        {isSending && <span role="status">正在確認修改…</span>}
      </DialogActions>
    </Dialog>
  );
}
