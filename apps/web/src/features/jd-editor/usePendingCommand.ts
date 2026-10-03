/**
 * One unconfirmed command per file and kind, kept across reloads and replayed unchanged until its result
 * is known. This is the whole rule for every manual JD write (collections and profile alike); it is not a
 * second JD owner, and it never turns a lost answer into a new command.
 */
import { useRef, useState } from 'react';
import { ApiError } from '../../shared/api/http';

export interface PendingCommandPort<C> {
  /** Where this file's one unconfirmed command of this kind waits, so a reload can find it. */
  storageKey: string;
  isCommand: (value: unknown) => value is C;
  post: (command: C) => Promise<unknown>;
  /** Reads the formal JD again once a result is known, whatever it was. */
  refresh: () => void;
  /** Said when the change is not a command the App can send. */
  invalidMessage: string;
  /** Said when a command from an earlier visit is still waiting for its result. */
  restoredMessage: string;
}

interface PendingState<C> {
  pending: C | null;
  message: string | null;
  blocked: boolean;
}

function restoreCommand<C>(port: PendingCommandPort<C>): PendingState<C> {
  try {
    const raw = sessionStorage.getItem(port.storageKey);
    if (raw === null) return { pending: null, message: null, blocked: false };
    const value: unknown = JSON.parse(raw);
    if (!port.isCommand(value)) throw new Error('Invalid pending command');
    return { pending: value, message: port.restoredMessage, blocked: false };
  } catch {
    return {
      pending: null,
      message: '無法讀取待確認修改。請確認瀏覽器儲存權限，勿重複送出。',
      blocked: true,
    };
  }
}

export function usePendingCommand<C>(port: PendingCommandPort<C>, onSaved: () => void) {
  const key = port.storageKey;
  const [state, setState] = useState(() => restoreCommand(port));
  const [isSending, setIsSending] = useState(false);
  const inFlight = useRef(false);

  async function send(command: C): Promise<void> {
    if (inFlight.current || state.blocked) return;
    if (state.pending && JSON.stringify(state.pending) !== JSON.stringify(command)) return;
    if (!port.isCommand(command)) {
      setState({ ...state, message: port.invalidMessage });
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
      await port.post(command);
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
        port.refresh();
        onSaved();
        return;
      }
      setState({ pending: null, message: null, blocked: false });
      port.refresh();
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
    const restored = restoreCommand(port);
    setState(restored);
    port.refresh();
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
