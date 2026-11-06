import { useMutation, useQueryClient } from '@tanstack/react-query';
import { useEffect, useRef, useState } from 'react';
import { Link, useNavigate } from 'react-router';
import type { JobDescriptionResponse } from '../../../shared/api/generated/types.gen';
import { validateJobDescriptionErrorResponse } from '../../../shared/api/generated/validators';
import { HttpError } from '../../../shared/api/http';
import { Dialog } from '../../../shared/ui/Dialog';
import { ErrorNotice } from '../../../shared/ui/Feedback';
import { Button } from '@mui/material';
import { hasStoredDrafts } from '../editing/drafts';
import { requiresWriteVerification } from '../errors';
import { restoreVersion } from '../history-api';
import { jobDescriptionOptions, synchronizeJobDescription } from '../queries';

function restoreErrorMessage(error: unknown) {
  if (error instanceof HttpError && validateJobDescriptionErrorResponse(error.body)) {
    if (error.body.detail.commit_status === 'committed')
      return '內容已恢復，但未能取得完整回覆。請返回目前 JD 核對。';
    if (error.body.detail.code === 'jd_concurrency_conflict')
      return '目前內容已經變更，本次未恢復。請返回目前 JD 核對，再選擇要恢復的版本。';
  }
  return requiresWriteVerification(error)
    ? '無法確認是否已恢復。請返回目前 JD 核對，避免重複送出。'
    : '本次未恢復內容。請關閉視窗，核對目前內容後再試。';
}

export function RestoreVersionDialog({
  current,
  targetVersion,
  onClose,
  onDraftsFound,
  onVerificationRequired,
  readOnly = false,
}: {
  current: JobDescriptionResponse;
  targetVersion: number;
  onClose: () => void;
  onDraftsFound: () => void;
  onVerificationRequired: () => void;
  readOnly?: boolean;
}) {
  const cache = useQueryClient();
  const navigate = useNavigate();
  const active = useRef(true);
  const cancelButton = useRef<HTMLButtonElement>(null);
  const [localError, setLocalError] = useState<string | null>(null);
  const options = jobDescriptionOptions(current.workspace_id);
  const historyListKey = [
    ...options.queryKey,
    current.job_description_id,
    'history',
    'list',
  ];
  const returnPath = `/workspaces/${encodeURIComponent(current.workspace_id)}/jd`;
  useEffect(() => {
    active.current = true;
    return () => {
      active.current = false;
    };
  }, []);
  const restoration = useMutation({
    mutationFn: () =>
      restoreVersion(current.workspace_id, current.job_description_id, {
        expected_version: current.version,
        target_version: targetVersion,
      }),
    retry: false,
    onError: (error) => {
      if (active.current && requiresWriteVerification(error)) onVerificationRequired();
      // 返回編輯頁核對時必須讀伺服器；舊快取不能當作未知結果的證據。
      void (async () => {
        await cache.cancelQueries({ queryKey: options.queryKey, exact: true });
        await cache.cancelQueries({ queryKey: historyListKey, exact: true });
        await cache.invalidateQueries({
          queryKey: options.queryKey,
          exact: true,
          refetchType: 'active',
        });
        await cache.invalidateQueries({
          queryKey: historyListKey,
          exact: true,
          refetchType: 'none',
        });
      })().catch(() => {
        if (active.current)
          setLocalError('未能準備最新內容。請返回目前 JD 重新讀取後核對。');
      });
    },
    onSuccess: (result) => {
      if (active.current) onVerificationRequired();
      // 寫入已確認；畫面更新若失敗，只提供重新讀取，不重新送出恢復。
      void (async () => {
        await synchronizeJobDescription(cache, result);
        if (!active.current) return;
        await navigate(returnPath);
      })().catch(() => {
        if (active.current)
          setLocalError('內容已恢復，但畫面更新失敗。請返回目前 JD 重新讀取。');
      });
    },
  });
  const close = () => {
    if (!restoration.isPending) onClose();
  };
  return (
    <Dialog
      title={`恢復版本 ${String(targetVersion)}`}
      onClose={close}
      initialFocusRef={cancelButton}
    >
      <p className="dialog-description">
        將以版本 {targetVersion} 的完整內容建立新版本，取代目前版本 {current.version}{' '}
        的內容。原有歷史仍會保留。
      </p>
      {restoration.isError && (
        <ErrorNotice message={restoreErrorMessage(restoration.error)} />
      )}
      {localError && <ErrorNotice message={localError} />}
      {(restoration.isError || localError) && (
        <Link className="text-button" to={returnPath}>
          返回目前 JD 核對
        </Link>
      )}
      <div className="dialog-actions">
        <Button
          ref={cancelButton}
          className="secondary-button"
          disabled={restoration.isPending}
          onClick={close}
        >
          取消
        </Button>
        <Button
          className="primary-button"
          disabled={
            readOnly ||
            restoration.isPending ||
            restoration.isError ||
            restoration.isSuccess
          }
          onClick={() => {
            if (hasStoredDrafts(current.workspace_id, current.job_description_id)) {
              onDraftsFound();
              return;
            }
            restoration.mutate();
          }}
        >
          {restoration.isPending ? '恢復中…' : '確認恢復'}
        </Button>
      </div>
    </Dialog>
  );
}
