/** JD command slots and the shared revision's refresh policy; drafts stay in their editors. */
import type { JdProfileView } from '../../shared/api/generated/jd-profile-view';
import type { ReviseJdProfileRequest } from '../../shared/api/generated/revise-jd-profile-request';
import { ApiError } from '../../shared/api/http';
import { isReviseJdProfileRequest } from '../../shared/api/validation';
import { createPendingCommandStore } from '../../shared/commands/pending-command';
import type { PendingCommandStore } from '../../shared/commands/pending-command';
import type { StoredCommand, StoredCommandState } from '../../shared/commands/use-stored-command';
import { reviseJdProfile } from './jd-profile-api';
import { editJdWork, isWorkCommand } from './jd-work-api';
import type { WorkCommand } from './jd-work-api';

export function pendingProfile(jobFileId: string): PendingCommandStore<ReviseJdProfileRequest> {
  return createPendingCommandStore<ReviseJdProfileRequest>({
    key: `caliburn.pending-jd-profile.${jobFileId}`,
    isCommand: isReviseJdProfileRequest,
    matches: (left, right) => JSON.stringify(left) === JSON.stringify(right),
  });
}

export function pendingWork(jobFileId: string): PendingCommandStore<WorkCommand> {
  return createPendingCommandStore<WorkCommand>({
    key: `caliburn.pending-jd-work.${jobFileId}`,
    isCommand: isWorkCommand,
    matches: (left, right) => JSON.stringify(left) === JSON.stringify(right),
  });
}

function isRejection(error: unknown): boolean {
  // Only errors emitted after original-command lookup prove this payload was rejected.
  return (
    error instanceof ApiError &&
    error.status === 409 &&
    ['jd_command_conflict', 'jd_revision_stale', 'consultant_turn_active'].includes(
      error.code ?? '',
    )
  );
}

export function profileCommand(
  jobFileId: string,
  refresh: () => Promise<void>,
): JdCommand<ReviseJdProfileRequest, JdProfileView> {
  return {
    store: pendingProfile(jobFileId),
    execute: (command: ReviseJdProfileRequest) => reviseJdProfile(jobFileId, command),
    classifyRejection: (error) => (isRejection(error) ? { reason: 'refused' } : null),
    refresh,
    invalidMessage: '欄位不能只有空白或包含無法儲存的字元；若要清空，請刪除全部文字。',
    restoredMessage: '有尚未確認的 JD 修改，請先取得原結果。',
  };
}

export function workCommand(
  jobFileId: string,
  refresh: () => Promise<void>,
): JdCommand<WorkCommand, void> {
  return {
    store: pendingWork(jobFileId),
    execute: (command: WorkCommand) => editJdWork(jobFileId, command),
    classifyRejection: (error, command) => {
      if (isRejection(error)) return { reason: 'refused' };
      if (!(error instanceof ApiError)) return null;
      // These resource checks run in apply, after the workflow's original-result lookup.
      const missingTarget = {
        areas: 'jd_area_not_found',
        tasks: 'jd_task_target_not_found',
        capabilities: 'jd_capability_target_not_found',
        collaborators: 'jd_collaborator_not_found',
        conditions: 'jd_condition_not_found',
      };
      return (error.status === 404 && error.code === missingTarget[command.collection]) ||
        (command.collection === 'capabilities' &&
          error.status === 409 &&
          error.code === 'capability_in_use')
        ? { reason: 'refused' }
        : null;
    },
    refresh,
    invalidMessage: '名稱或內容至少填一項，欄位不能只有空白或包含無法儲存的字元。',
    restoredMessage: '有尚未確認的 JD 集合修改，請先取得原結果。',
  };
}

interface JdCommand<C, R> extends StoredCommand<C, R> {
  invalidMessage: string;
  restoredMessage: string;
}

function messageOf<C, R>(command: StoredCommandState<C, R>, definition: JdCommand<C, R>) {
  switch (command.issue) {
    case null:
      break;
    case 'display':
      return '修改已保存，但畫面未能更新。請重新讀取目前 JD。';
    case 'restore':
      return '無法讀取待確認修改。請確認瀏覽器儲存權限，勿重複送出。';
    case 'invalid':
      return definition.invalidMessage;
    case 'retain':
      return '瀏覽器無法保留本次修改識別，尚未送出。請確認儲存權限。';
  }
  const outcome = command.outcome;
  if (!outcome) return !command.isSending && command.pending ? definition.restoredMessage : null;
  if (outcome.status === 'unknown')
    return 'JD 修改結果尚未確認。重新確認會使用原請求，不會重複寫入。';
  if (outcome.acknowledgement === 'changed')
    return outcome.status === 'accepted'
      ? '修改已保存，但本分頁待確認紀錄已變更。請讀取目前 JD 再決定。'
      : '修改未被接受，但本分頁待確認紀錄已變更。請讀取目前 JD 再決定。';
  if (outcome.status === 'accepted') {
    if (outcome.acknowledgement === 'unavailable')
      return '修改已保存，但本分頁暫存未能清除。請確認瀏覽器儲存權限後重新確認原結果，不會重複寫入。';
    return outcome.refreshFailed ? '修改已保存，但目前 JD 未能重新讀取。請重新讀取目前 JD。' : null;
  }
  return outcome.acknowledgement === 'unavailable'
    ? '修改未被接受，且待確認紀錄無法清除。請確認瀏覽器儲存權限。'
    : '修改未被接受，可能已有其他修改或顧問正在處理。請先讀取目前 JD 再決定，不會自動覆蓋。';
}

/** JD rejection requires an explicit re-read; file creation intentionally has a different policy. */
interface JdCommandState<C, R> extends Omit<StoredCommandState<C, R>, 'reload'> {
  message: string | null;
  reload: () => void;
}

export function jdCommandView<C, R>(
  command: StoredCommandState<C, R>,
  definition: JdCommand<C, R>,
  closeEditor: () => void,
): JdCommandState<C, R> {
  const blocked =
    command.blocked ||
    command.outcome?.status === 'rejected' ||
    (command.outcome?.status === 'accepted' && command.outcome.refreshFailed);
  return {
    ...command,
    blocked,
    locked: command.locked || blocked,
    message: messageOf(command, definition),
    send: (next: C) => (blocked ? Promise.resolve() : command.send(next)),
    reload: () => {
      const empty = command.reload();
      // Query's read error stays visible in the JD; it does not resurrect a settled command.
      void Promise.resolve()
        .then(() => definition.refresh())
        .catch(() => {});
      if (empty) closeEditor();
    },
  };
}
