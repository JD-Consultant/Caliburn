import { Alert, Box, Button, Collapse, Typography } from '@mui/material';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useState } from 'react';
import { HttpError } from '../../shared/api/http';
import { validateJobDescriptionErrorResponse } from '../../shared/api/generated/validators';
import { hasStoredDrafts } from './editing/drafts';
import { JobDescriptionDifference } from './history/JobDescriptionDifference';
import { jobDescriptionOptions, synchronizeJobDescription } from './queries';
import { getTurnChanges, restoreTurnChanges } from './turn-history-api';
import './history/history.css';

export function TurnJobDescriptionChanges(props: {
  workspaceId: string;
  turnId: string;
  readOnly?: boolean;
  onChanged: () => void | Promise<void>;
}) {
  return <TurnChanges key={`${props.workspaceId}/${props.turnId}`} {...props} />;
}

function TurnChanges({
  workspaceId,
  turnId,
  readOnly = false,
  onChanged,
}: {
  workspaceId: string;
  turnId: string;
  readOnly?: boolean;
  onChanged: () => void | Promise<void>;
}) {
  const [open, setOpen] = useState(false);
  const [confirming, setConfirming] = useState(false);
  const [localError, setLocalError] = useState<string | null>(null);
  const cache = useQueryClient();
  const current = useQuery(jobDescriptionOptions(workspaceId));
  const jdId = current.data?.job_description_id;
  const changes = useQuery({
    queryKey: [
      ...jobDescriptionOptions(workspaceId).queryKey,
      jdId,
      'turn-changes',
      turnId,
    ],
    enabled: open && jdId !== undefined,
    queryFn: ({ signal }) => {
      if (!jdId) throw new Error('JD 尚未載入');
      return getTurnChanges(workspaceId, jdId, turnId, signal);
    },
    staleTime: Infinity,
  });
  const restore = useMutation({
    mutationFn: () => {
      if (!jdId) throw new Error('JD 尚未載入');
      return restoreTurnChanges(workspaceId, jdId, turnId);
    },
    retry: false,
    onSuccess: async (result) => {
      setConfirming(false);
      try {
        await synchronizeJobDescription(cache, result);
        await onChanged();
      } catch {
        setLocalError('撤銷已保存，但畫面更新失敗。請重新讀取目前 JD 核對。');
      }
    },
    onError: () => {
      void cache.invalidateQueries({
        queryKey: jobDescriptionOptions(workspaceId).queryKey,
        exact: true,
      });
    },
  });
  const blocked = readOnly || restore.isPending || restore.isSuccess || restore.isError;
  return (
    <Box className="turn-jd-changes" sx={{ mt: 1 }}>
      <Button size="small" aria-expanded={open} onClick={() => setOpen(!open)}>
        該輪 JD 變更
      </Button>
      <Collapse in={open}>
        <Box sx={{ py: 1 }}>
          {isMissingTurnChanges(changes.error) ? (
            <Typography role="status">此輪沒有可回看的 JD 保存點。</Typography>
          ) : (current.isError && !current.data) || changes.isError ? (
            <Alert
              severity="error"
              action={
                <Button
                  color="inherit"
                  onClick={() => {
                    void current.refetch();
                    if (jdId) void changes.refetch();
                  }}
                >
                  重新讀取
                </Button>
              }
            >
              無法讀取該輪固定 JD 比較。現有內容不會被替換。
            </Alert>
          ) : changes.data ? (
            <>
              <Typography variant="body2" color="text.secondary">
                輪前版本 {changes.data.before_version} → 模型完成時已見版本{' '}
                {changes.data.after_version}。這是固定歷史比較。
              </Typography>
              <JobDescriptionDifference
                difference={changes.data.difference}
                before={changes.data.before}
                after={changes.data.after}
              />
              {restore.isSuccess && (
                <Alert severity="success">此輪 JD 撤銷已完成，其他訪談資料保留。</Alert>
              )}
              {restore.isError && (
                <Alert severity="error">{turnRestoreError(restore.error)}</Alert>
              )}
              {localError && <Alert severity="error">{localError}</Alert>}
              {confirming ? (
                <Box sx={{ mt: 1 }}>
                  <Typography variant="body2">
                    只撤銷此輪 JD 改動，訪談、Plan、Memory 與 Agent
                    紀錄保留。若已有後續或交錯修改，系統會拒絕覆蓋。
                  </Typography>
                  <Button
                    color="error"
                    disabled={blocked}
                    onClick={() => {
                      if (!jdId || hasStoredDrafts(workspaceId, jdId)) {
                        setLocalError(
                          'JD 還有未確認輸入。請先處理草稿，再撤銷此輪改動。',
                        );
                        return;
                      }
                      restore.mutate();
                    }}
                  >
                    {restore.isPending ? '撤銷中…' : '確認撤銷此輪 JD 改動'}
                  </Button>
                  <Button
                    disabled={restore.isPending}
                    onClick={() => setConfirming(false)}
                  >
                    保留改動
                  </Button>
                </Box>
              ) : (
                <Button
                  size="small"
                  color="error"
                  disabled={blocked}
                  onClick={() => {
                    setLocalError(null);
                    setConfirming(true);
                  }}
                >
                  撤銷此輪 JD 改動
                </Button>
              )}
            </>
          ) : (
            <Typography role="status">正在讀取該輪 JD 變更…</Typography>
          )}
        </Box>
      </Collapse>
    </Box>
  );
}

function isMissingTurnChanges(error: unknown): boolean {
  return (
    error instanceof HttpError &&
    error.status === 404 &&
    validateJobDescriptionErrorResponse(error.body) &&
    error.body.detail.code === 'jd_turn_not_found'
  );
}

function turnRestoreError(error: unknown): string {
  if (error instanceof HttpError && validateJobDescriptionErrorResponse(error.body)) {
    if (error.body.detail.commit_status === 'committed')
      return '撤銷已保存，但未能取得完整回覆。請重新讀取目前 JD 核對。';
    if (error.body.detail.commit_status === 'not_committed')
      return error.status === 409
        ? '目前 JD 有後續或交錯修改，這次未撤銷。已保留目前 JD 與原比較。'
        : '這次未撤銷 JD。請核對目前內容與輪次狀態。';
  }
  return '無法確認撤銷是否已保存。請重新讀取目前 JD 核對；系統不會自動重送。';
}
