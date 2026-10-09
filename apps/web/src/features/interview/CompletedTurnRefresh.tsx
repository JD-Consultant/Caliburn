import { useEffect, useState } from 'react';
import { Alert, Button } from '@mui/material';

/** 由完成的 execution 作為 key；正式保存與這次畫面重讀各自確認成功。 */
export function CompletedTurnRefresh({ refresh }: { refresh: () => Promise<void> }) {
  const [status, setStatus] = useState<'refreshing' | 'refreshed' | 'failed'>('refreshing');
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    let disposed = false;
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
  }, [refresh, attempt]);

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
