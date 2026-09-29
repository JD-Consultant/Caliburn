/** One pending manual collection command per file/tab. This is not a second JD owner. */
import { useRef, useState } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { ApiError } from '../../shared/api/http';
import { jdProfileQuery } from './jd-profile-api';
import { editJdWork, isWorkCommand, jdWorkQuery } from './jd-work-api';
import type { WorkCommand } from './jd-work-api';

function restoreCommand(key: string): {
  pending: WorkCommand | null;
  message: string | null;
  blocked: boolean;
} {
  try {
    const raw = sessionStorage.getItem(key);
    if (raw === null) return { pending: null, message: null, blocked: false };
    const value: unknown = JSON.parse(raw);
    if (!isWorkCommand(value)) throw new Error('Invalid pending command');
    return {
      pending: value,
      message: '有尚未確認的 JD 集合修改，請先取得原結果。',
      blocked: false,
    };
  } catch {
    return {
      pending: null,
      message: '無法讀取待確認修改。請確認瀏覽器儲存權限，勿重複送出。',
      blocked: true,
    };
  }
}

export function useWorkCommand(jobFileId: string, onSaved: () => void) {
  const key = `caliburn.pending-jd-work.${jobFileId}`;
  const [state, setState] = useState(() => restoreCommand(key));
  const [isSending, setIsSending] = useState(false);
  const inFlight = useRef(false);
  const queryClient = useQueryClient();

  function refresh(): void {
    void queryClient.invalidateQueries({ queryKey: jdWorkQuery(jobFileId).queryKey });
    void queryClient.invalidateQueries({ queryKey: jdProfileQuery(jobFileId).queryKey });
  }

  async function send(command: WorkCommand): Promise<void> {
    if (inFlight.current || state.blocked) return;
    if (state.pending && JSON.stringify(state.pending) !== JSON.stringify(command)) return;
    if (!isWorkCommand(command)) {
      setState({
        ...state,
        message: '名稱或內容至少填一項，欄位不能只有空白或包含無法儲存的字元。',
      });
      return;
    }
    try {
      sessionStorage.setItem(key, JSON.stringify(command));
    } catch {
      setState({ ...state, message: '瀏覽器無法保留本次修改識別，尚未送出。請確認儲存權限。' });
      return;
    }
    inFlight.current = true;
    setIsSending(true);
    setState({ pending: command, message: null, blocked: false });
    try {
      await editJdWork(jobFileId, command);
      try {
        sessionStorage.removeItem(key);
      } catch {
        // The server result is known. A local cleanup failure must not turn it into unknown.
        setState({
          pending: command,
          blocked: false,
          message:
            '修改已保存，但本分頁暫存未能清除。請確認瀏覽器儲存權限後重新確認原結果，不會重複寫入。',
        });
        refresh();
        onSaved();
        return;
      }
      setState({ pending: null, message: null, blocked: false });
      refresh();
      onSaved();
    } catch (error) {
      if (error instanceof ApiError && [400, 404, 409, 422].includes(error.status ?? 0)) {
        try {
          sessionStorage.removeItem(key);
          setState({
            pending: null,
            blocked: true,
            message:
              '修改未被接受，可能已有其他修改或顧問正在處理。請先讀取目前 JD 再決定，不會自動覆蓋。',
          });
        } catch {
          setState({
            pending: command,
            blocked: true,
            message: '修改未被接受，且待確認紀錄無法清除。請確認瀏覽器儲存權限。',
          });
        }
      } else {
        setState({
          pending: command,
          blocked: false,
          message: 'JD 修改結果尚未確認。重新確認會使用原請求，不會重複寫入。',
        });
      }
    } finally {
      inFlight.current = false;
      setIsSending(false);
    }
  }

  function reload(): void {
    const restored = restoreCommand(key);
    setState(restored);
    refresh();
    if (!restored.pending && !restored.blocked) onSaved();
  }

  return {
    ...state,
    isSending,
    send,
    reload,
    locked: isSending || state.pending !== null || state.blocked,
  };
}
