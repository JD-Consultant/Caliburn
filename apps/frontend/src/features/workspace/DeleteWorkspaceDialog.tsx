import { useMutation, useQueryClient } from '@tanstack/react-query';
import {
  Alert,
  Button,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  Stack,
  Typography,
} from '@mui/material';
import type { WorkspaceResponse } from '../../shared/api/generated/types.gen';
import { deleteWorkspace } from './api';
import { workspaceErrorMessage, requiresWriteVerification } from './errors';
import { workspaceListKey, workspaceOptions } from './queries';

export function DeleteWorkspaceDialog({
  workspace,
  onClose,
  onDeleted,
}: {
  workspace: WorkspaceResponse;
  onClose: () => void;
  /** App removes all feature caches after the server confirms deletion. */
  onDeleted?: ((workspaceId: string) => Promise<void>) | undefined;
}) {
  const cache = useQueryClient();
  const deletion = useMutation({
    mutationFn: () => deleteWorkspace(workspace.workspace_id),
    onSuccess: async () => {
      if (onDeleted) await onDeleted(workspace.workspace_id);
      else {
        const queryKey = workspaceOptions(workspace.workspace_id).queryKey;
        await cache.cancelQueries({ queryKey });
        cache.removeQueries({ queryKey });
      }
      await cache.invalidateQueries({ queryKey: workspaceListKey });
    },
  });
  return (
    <Dialog
      open
      onClose={deletion.isPending ? undefined : onClose}
      fullWidth
      maxWidth="sm"
      aria-labelledby="delete-workspace-title"
      aria-describedby="delete-workspace-description"
    >
      <DialogTitle id="delete-workspace-title">刪除工作區</DialogTitle>
      <DialogContent>
        <Stack spacing={2} id="delete-workspace-description">
          <Typography component="p">
            確定永久刪除「{workspace.interviewee_name}」的工作區？
          </Typography>
          <Typography component="p">
            所有訪談、職務說明書（JD）、Plan、Memory、執行紀錄與歷史都將永久刪除，且不可復原。
          </Typography>
          {deletion.isError && (
            <Alert severity="warning">
              {workspaceErrorMessage(deletion.error, true)}
            </Alert>
          )}
        </Stack>
      </DialogContent>
      <DialogActions>
        <Button autoFocus onClick={onClose} disabled={deletion.isPending}>
          取消
        </Button>
        <Button
          variant="contained"
          color="error"
          disabled={
            deletion.isPending ||
            (deletion.isError && requiresWriteVerification(deletion.error))
          }
          onClick={() => deletion.mutate(undefined, { onSuccess: onClose })}
        >
          {deletion.isPending ? '刪除中…' : '永久刪除'}
        </Button>
      </DialogActions>
    </Dialog>
  );
}
