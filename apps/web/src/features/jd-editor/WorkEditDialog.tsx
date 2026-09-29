import { useRef, useState } from 'react';
import { Alert, Button, Dialog, DialogActions, DialogContent, DialogTitle } from '@mui/material';
import type { Area, JdWorkView, WorkTask } from '../../shared/api/generated/jd-work-view';
import type { WorkCommand } from './jd-work-api';
import { AreaFields } from './AreaFields';
import { TaskFields } from './TaskFields';
import { focusDialogInput } from './dialog-focus';

export type WorkEditing =
  | { kind: 'area'; baseline: JdWorkView; area?: Area }
  | { kind: 'task'; baseline: JdWorkView; task?: WorkTask; areaId: string | null }
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
  return editing.title;
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
      </DialogContent>
      <DialogActions sx={{ flexWrap: 'wrap', px: 3, pb: 2 }}>
        <Button disabled={isSending} onClick={onClose}>
          返回 JD
        </Button>
        {editing.kind !== 'confirm' && !pending && (
          <Button
            type="submit"
            form={editing.kind === 'area' ? 'jd-area-form' : 'jd-task-form'}
            variant="contained"
            disabled={locked}
          >
            {editing.kind === 'area' ? '儲存職責' : '儲存任務'}
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
