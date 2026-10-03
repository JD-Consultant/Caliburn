/**
 * What an editor tells the person about its command, as two small pure rules the basic-data editor and the
 * collections editor share: the status of the command in flight, and the notice an open draft carries.
 */
import type { WorkStatusProps } from './WorkStatus';

interface CommandView<C> {
  pending: C | null;
  message: string | null;
  blocked: boolean;
  isSending: boolean;
  send: (command: C) => Promise<void>;
  reload: () => void;
}

export function statusOf<C>(command: CommandView<C>): WorkStatusProps {
  return {
    message: command.message,
    isSending: command.isSending,
    canConfirm: command.pending !== null,
    confirmDisabled: command.isSending || command.blocked,
    onConfirm: () => {
      if (command.pending) void command.send(command.pending);
    },
    canReload: command.blocked,
    onReload: command.reload,
  };
}

/** The command's own message wins; otherwise a draft kept while a Turn owns the JD says why it cannot be saved yet. */
export function draftNoticeOf(commandMessage: string | null, readOnly: boolean): string | null {
  return commandMessage ?? (readOnly ? 'JD 暫時唯讀，草稿仍保留；待處理狀態確認後再儲存。' : null);
}
