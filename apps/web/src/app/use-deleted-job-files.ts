import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { clearDeletedInterview } from '../features/interview/interview-turn-api';
import { clearDeletedJdCommands } from '../features/jd-editor/pending-cleanup';
import { clearDeletedJobFileQueries } from '../features/job-files/deleted-cleanup';
import { jobFilesQuery } from '../features/job-files/job-file-api';
import { pendingRename } from '../features/job-files/job-file-commands';
import { isCanonicalUuid } from '../shared/api/uuid';
import { refreshQueries } from '../shared/api/refresh-queries';

interface FileCleanup {
  // A settled successful promise also deduplicates later confirmations. Failures clear it.
  completion: Promise<void> | null;
  notificationFailed: boolean;
}

/** App composes feature-owned cleanup; messages contain only file identity. */
export function useDeletedJobFiles(): {
  context: { deleted: Set<string>; confirmDeleted: (jobFileId: string) => Promise<void> };
  warning: string | null;
} {
  const cache = useQueryClient();
  const [deleted, setDeleted] = useState(new Set<string>());
  const [warnings, setWarnings] = useState(new Map<string, string>());
  const channel = useRef<BroadcastChannel | null>(null);
  const active = useRef(true);
  const files = useRef(new Map<string, FileCleanup>());
  const reportWarning = useCallback((jobFileId: string, warning: string | null) => {
    if (!active.current) return;
    setWarnings((previous) => {
      const next = new Map(previous);
      if (warning) next.set(jobFileId, warning);
      else next.delete(jobFileId);
      return next;
    });
  }, []);
  const clean = useCallback(
    async (jobFileId: string, broadcast: boolean): Promise<void> => {
      const previous = files.current.get(jobFileId);
      if (previous?.completion) return previous.completion;
      const file = previous ?? { completion: null, notificationFailed: false };
      if (!previous) {
        files.current.set(jobFileId, file);
        if (active.current) setDeleted((deleted) => new Set([...deleted, jobFileId]));
        try {
          if (broadcast)
            channel.current?.postMessage({ type: 'job_file_deleted', job_file_id: jobFileId });
        } catch {
          file.notificationFailed = true;
        }
      }
      const completion = (async () => {
        const results = await Promise.allSettled([
          clearDeletedJobFileQueries(cache, jobFileId),
          clearDeletedInterview(jobFileId),
          Promise.resolve().then(() => clearDeletedJdCommands(jobFileId)),
          Promise.resolve().then(() => pendingRename(jobFileId).clear()),
        ]);
        let retryNeeded = results.some((result) => result.status === 'rejected');
        const messages: string[] = [];
        if (file.notificationFailed || retryNeeded) {
          messages.push('職務檔案已刪除，但瀏覽器資料未能完整清理。請確認儲存權限後重新開啟。');
        }
        try {
          await refreshQueries(cache, [{ queryKey: jobFilesQuery.queryKey, exact: true }]);
        } catch {
          retryNeeded = true;
          messages.push('職務檔案已刪除，但清單未能重新讀取。請重新讀取清單。');
        }
        // Keep the confirmed deletion; only unfinished local work may run again.
        if (retryNeeded) file.completion = null;
        reportWarning(jobFileId, messages.join(' ') || null);
      })();
      file.completion = completion;
      return completion;
    },
    [cache, reportWarning],
  );
  const confirmDeleted = useCallback((jobFileId: string) => clean(jobFileId, true), [clean]);
  useEffect(() => {
    active.current = true;
    if (typeof BroadcastChannel === 'undefined')
      return () => {
        active.current = false;
      };
    const connection = new BroadcastChannel('caliburn:job-file-lifecycle');
    channel.current = connection;
    connection.onmessage = (event: MessageEvent<unknown>) => {
      const value = event.data;
      if (
        typeof value !== 'object' ||
        value === null ||
        !('type' in value) ||
        value.type !== 'job_file_deleted' ||
        !('job_file_id' in value) ||
        !isCanonicalUuid(value.job_file_id)
      )
        return;
      const jobFileId = value.job_file_id;
      void clean(jobFileId, false).catch(() => {
        reportWarning(jobFileId, '職務檔案已刪除，但瀏覽器資料未能完整清理。');
      });
    };
    return () => {
      active.current = false;
      channel.current = null;
      connection.close();
    };
  }, [clean, reportWarning]);
  return {
    context: useMemo(() => ({ deleted, confirmDeleted }), [deleted, confirmDeleted]),
    warning: [...new Set(warnings.values())].join(' ') || null,
  };
}
