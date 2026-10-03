/** Lazy historical net comparison, independent of current JD and undo eligibility. */
import { useId, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Alert, Button, Dialog, DialogActions, DialogContent, DialogTitle } from '@mui/material';
import { describeReadError } from '../../shared/api/http';
import { SafeMarkdown } from '../../shared/ui/SafeMarkdown';
import { turnJdChangesQuery } from './turn-jd-changes-api';

export function TurnJdChanges({
  jobFileId,
  executionId,
}: {
  jobFileId: string;
  executionId: string;
}) {
  const [open, setOpen] = useState(false);
  const titleId = useId();
  const changes = useQuery({ ...turnJdChangesQuery(jobFileId, executionId), enabled: open });
  return (
    <>
      <Button size="small" onClick={() => setOpen(true)}>
        查看這輪 JD 變更
      </Button>
      <Dialog
        open={open}
        onClose={() => setOpen(false)}
        aria-labelledby={titleId}
        fullWidth
        maxWidth="md"
      >
        <DialogTitle id={titleId}>這輪 JD 變更</DialogTitle>
        <DialogContent>
          {changes.isPending && <p role="status">正在讀取這輪保存的 JD 變更…</p>}
          {changes.isError ? (
            <Alert
              severity="error"
              action={
                <Button
                  color="inherit"
                  onClick={() => {
                    void changes.refetch();
                  }}
                >
                  重新讀取變更
                </Button>
              }
            >
              {describeReadError(changes.error)}
            </Alert>
          ) : (
            changes.data && <SafeMarkdown markdown={changes.data.markdown} />
          )}
        </DialogContent>
        <DialogActions>
          <Button variant="outlined" onClick={() => setOpen(false)}>
            關閉
          </Button>
        </DialogActions>
      </Dialog>
    </>
  );
}
