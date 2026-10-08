import { useEffect, useState } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { Alert, Button } from '@mui/material';

/** 由完成的 execution 作為 key；正式保存與這次畫面重讀各自確認成功。 */
export function CompletedTurnRefresh({ jobFileId }: { jobFileId: string }) {
  const queryClient = useQueryClient();
  const [status, setStatus] = useState<'refreshing' | 'refreshed' | 'failed'>('refreshing');
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    let disposed = false;
    const keys = [
      ['job-file', jobFileId, 'formal-interviews'],
      ['jd-profile', jobFileId],
      ['jd-work', jobFileId],
    ];
    async function refresh(): Promise<void> {
      // 首次 GET 尚無資料時，單獨 invalidate 會沿用舊請求，必須先取消。
      await Promise.all(keys.map((queryKey) => queryClient.cancelQueries({ queryKey })));
      if (disposed) return;
      await Promise.all(
        keys.map((queryKey) => queryClient.invalidateQueries({ queryKey }, { throwOnError: true })),
      );
    }
    void refresh().then(
      () => {
        if (!disposed) setStatus('refreshed');
      },
      () => {
        if (!disposed) setStatus('failed');
      },
    );
    return () => {
      disposed = true;
    };
  }, [jobFileId, queryClient, attempt]);

  if (status === 'refreshed') return null;
  if (status === 'refreshing') return <p className="dock-note">正在更新訪談與 JD…</p>;
  return (
    <Alert
      severity="warning"
      action={
        <Button
          color="inherit"
          onClick={() => {
            setStatus('refreshing');
            setAttempt((previous) => previous + 1);
          }}
        >
          重新更新訪談與 JD
        </Button>
      }
    >
      訪談已保存，但畫面尚未更新。請重新更新訪談與 JD。
    </Alert>
  );
}
