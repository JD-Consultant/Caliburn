import { HttpError } from '../../shared/api/http';
import {
  validateErrorResponse,
  validateWorkspaceConflictResponse,
} from '../../shared/api/generated/validators';

export function requiresWriteVerification(error: unknown): boolean {
  if (!(error instanceof HttpError)) return true;
  if (error.status === 409) return !validateWorkspaceConflictResponse(error.body);
  if (!validateErrorResponse(error.body)) return true;
  return !(
    (error.status === 404 && error.body.detail.code === 'workspace_not_found') ||
    ([400, 422].includes(error.status) && error.body.detail.code === 'invalid_request')
  );
}

export function workspaceErrorMessage(error: unknown, writing = false): string {
  if (writing && requiresWriteVerification(error))
    return '無法確認是否已保存。請先關閉視窗、重新讀取清單核對，不要再次送出。';
  if (error instanceof HttpError) {
    if (error.status === 404) return '這份工作區已不存在，請返回清單。';
    if (error.status === 409)
      return '工作區正在處理其他變更，本次操作未完成。請稍後再試。';
    if (error.status === 400 || error.status === 422)
      return '輸入內容不符合要求，請檢查後再試。';
  }
  return '暫時無法讀取工作區，請確認後端連線後重新讀取。';
}
