/**
 * The dialog for creating a JD item and for confirming a delete. Existing text is edited in place (InlineText),
 * so there is no "edit" form: Linear keeps creation apart from in-place editing the same way.
 */
import { useRef, useState } from 'react';
import { Alert, Button, Dialog, DialogActions, DialogContent, DialogTitle } from '@mui/material';
import type { Capability, JdWorkView } from '../../shared/api/generated/jd-work-view';
import { focusDialogInput } from '../../shared/ui/dialog-focus';
import type { WorkCommand } from './jd-work-api';
import { TaskFields } from './TaskFields';
import { CapabilityFields } from './CapabilityFields';
import { CollaboratorFields } from './CollaboratorFields';
import { ConditionFields } from './ConditionFields';

export type WorkDialogContent =
  | { kind: 'task'; baseline: JdWorkView; areaId: string | null }
  | { kind: 'capability'; baseline: JdWorkView; capabilityKind: Capability['kind'] }
  | { kind: 'collaborator'; baseline: JdWorkView }
  | { kind: 'condition'; baseline: JdWorkView }
  | { kind: 'confirm'; title: string; description: string; command: WorkCommand };

interface Props {
  content: WorkDialogContent;
  locked: boolean;
  readOnly?: boolean;
  isSending: boolean;
  canRetry: boolean;
  message: string | null;
  pending: WorkCommand | null;
  onSubmit: (command: WorkCommand) => Promise<void>;
  onClose: () => void;
  onReload: () => void;
}

function dialogTitle(content: WorkDialogContent): string {
  switch (content.kind) {
    case 'task':
      return '新增任務';
    case 'capability':
      return content.capabilityKind === 'knowledge' ? '新增知識' : '新增技能';
    case 'collaborator':
      return '新增協作對象';
    case 'condition':
      return '新增條件';
    case 'confirm':
      return content.title;
  }
}

function formAction(content: WorkDialogContent): { id: string; label: string } | null {
  switch (content.kind) {
    case 'task':
      return { id: 'jd-task-form', label: '儲存任務' };
    case 'capability':
      return {
        id: 'jd-capability-form',
        label: content.capabilityKind === 'knowledge' ? '儲存知識' : '儲存技能',
      };
    case 'confirm':
      return null;
    case 'collaborator':
      return { id: 'jd-collaborator-form', label: '儲存協作對象' };
    case 'condition':
      return { id: 'jd-condition-form', label: '儲存條件' };
  }
}

export function WorkDialog({
  content,
  locked,
  readOnly = false,
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
  const title = dialogTitle(content);
  const action = formAction(content);
  const editingDisabled = locked || readOnly;
  return (
    <Dialog
      open
      fullWidth
      maxWidth="sm"
      onClose={isSending ? undefined : onClose}
      aria-labelledby="work-dialog-title"
      slotProps={{ transition: { onEntered: () => focusDialogInput(titleInput.current) } }}
    >
      <DialogTitle id="work-dialog-title">{title}</DialogTitle>
      <DialogContent>
        {(message ?? localError) && <Alert severity="warning">{message ?? localError}</Alert>}
        {content.kind === 'task' && (
          <TaskFields
            titleInput={titleInput}
            baseline={content.baseline}
            areaId={content.areaId}
            disabled={editingDisabled}
            onSubmit={onSubmit}
            onError={setLocalError}
          />
        )}
        {content.kind === 'confirm' && <p>{content.description}</p>}
        {content.kind === 'capability' && (
          <CapabilityFields
            titleInput={titleInput}
            revisionId={content.baseline.revision_id}
            kind={content.capabilityKind}
            disabled={editingDisabled}
            onSubmit={onSubmit}
            onError={setLocalError}
          />
        )}
        {content.kind === 'collaborator' && (
          <CollaboratorFields
            titleInput={titleInput}
            revisionId={content.baseline.revision_id}
            disabled={editingDisabled}
            onSubmit={onSubmit}
            onError={setLocalError}
          />
        )}
        {content.kind === 'condition' && (
          <ConditionFields
            titleInput={titleInput}
            revisionId={content.baseline.revision_id}
            disabled={editingDisabled}
            onSubmit={onSubmit}
            onError={setLocalError}
          />
        )}
      </DialogContent>
      <DialogActions sx={{ flexWrap: 'wrap', px: 3, pb: 2 }}>
        <Button variant="outlined" disabled={isSending} onClick={onClose}>
          返回 JD
        </Button>
        {action && !pending && (
          <Button type="submit" form={action.id} variant="contained" disabled={editingDisabled}>
            {action.label}
          </Button>
        )}
        {/* Cancel, then the destructive action on the right in red (Primer, shadcn, Cloudscape). */}
        {content.kind === 'confirm' && !pending && (
          <Button
            variant="contained"
            color="error"
            disabled={editingDisabled}
            onClick={() => {
              void onSubmit(content.command);
            }}
          >
            確認{title}
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
