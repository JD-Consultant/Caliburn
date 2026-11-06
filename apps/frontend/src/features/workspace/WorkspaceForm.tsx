import { useRef, useState } from 'react';
import type { FormEvent } from 'react';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import {
  Alert,
  Button,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  Stack,
  TextField,
} from '@mui/material';
import type { WorkspaceResponse } from '../../shared/api/generated/types.gen';
import {
  validateCreateWorkspaceRequest,
  validateRenameWorkspaceRequest,
} from '../../shared/api/generated/validators';
import { focusDialogInput } from '../../shared/ui/dialog-focus';
import { createWorkspace, renameWorkspace } from './api';
import { workspaceErrorMessage, requiresWriteVerification } from './errors';
import { workspaceListKey, workspaceOptions } from './queries';

export function WorkspaceForm({
  workspace,
  onClose,
  onSaved,
}: {
  workspace?: WorkspaceResponse;
  onClose: () => void;
  onSaved: (workspace: WorkspaceResponse) => void;
}) {
  const [name, setName] = useState(workspace?.interviewee_name ?? '');
  const [inputError, setInputError] = useState('');
  const nameInput = useRef<HTMLInputElement>(null);
  const cache = useQueryClient();
  const save = useMutation({
    mutationFn: (intervieweeName: string) =>
      workspace
        ? renameWorkspace(workspace.workspace_id, { interviewee_name: intervieweeName })
        : createWorkspace({ interviewee_name: intervieweeName }),
    onSuccess: async (result) => {
      await Promise.all([
        cache.invalidateQueries({
          queryKey: workspaceOptions(result.workspace_id).queryKey,
          exact: true,
        }),
        cache.invalidateQueries({ queryKey: workspaceListKey }),
      ]);
    },
  });
  const blocked =
    save.isPending || (save.isError && requiresWriteVerification(save.error));
  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (blocked) return;
    const validate = workspace
      ? validateRenameWorkspaceRequest
      : validateCreateWorkspaceRequest;
    if (!validate({ interviewee_name: name })) {
      setInputError('請輸入受訪者姓名，不能只有空白。');
      return;
    }
    setInputError('');
    save.mutate(name, { onSuccess: onSaved });
  }
  return (
    <Dialog
      open
      onClose={save.isPending ? undefined : onClose}
      fullWidth
      maxWidth="sm"
      aria-labelledby="workspace-form-title"
      slotProps={{ transition: { onEntered: () => focusDialogInput(nameInput.current) } }}
    >
      <form onSubmit={submit} noValidate>
        <DialogTitle id="workspace-form-title">
          {workspace ? '變更受訪者姓名' : '建立工作區'}
        </DialogTitle>
        <DialogContent>
          <Stack spacing={2} sx={{ pt: 1 }}>
            <p>
              {workspace
                ? '只修改受訪者姓名，保留工作區的訪談、JD 與歷史。'
                : '一位受訪者、一份獨立工作記錄。建立後即可開始訪談與編修 JD。'}
            </p>
            {save.isError && (
              <Alert severity="warning">{workspaceErrorMessage(save.error, true)}</Alert>
            )}
            <TextField
              inputRef={nameInput}
              label="受訪者姓名"
              name="interviewee_name"
              autoComplete="off"
              value={name}
              onChange={(event) => setName(event.target.value)}
              required
              disabled={blocked}
              error={Boolean(inputError)}
              helperText={inputError || undefined}
            />
          </Stack>
        </DialogContent>
        <DialogActions>
          <Button variant="outlined" onClick={onClose} disabled={save.isPending}>
            取消
          </Button>
          <Button type="submit" variant="contained" disabled={blocked}>
            {save.isPending ? '處理中…' : workspace ? '確認' : '建立並開啟'}
          </Button>
        </DialogActions>
      </form>
    </Dialog>
  );
}
