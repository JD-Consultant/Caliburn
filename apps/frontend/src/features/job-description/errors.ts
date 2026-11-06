import { validateJobDescriptionErrorResponse } from '../../shared/api/generated/validators';
import { HttpError } from '../../shared/api/http';

export function requiresWriteVerification(error: unknown): boolean {
  return !(
    error instanceof HttpError &&
    validateJobDescriptionErrorResponse(error.body) &&
    error.body.detail.commit_status === 'not_committed'
  );
}

export function creationErrorMessage(error: unknown): string {
  if (
    error instanceof HttpError &&
    validateJobDescriptionErrorResponse(error.body) &&
    error.body.detail.commit_status === 'committed'
  ) {
    return '職務說明書已建立，但未能取得完整回覆。請重新讀取。';
  }
  return requiresWriteVerification(error)
    ? '無法確認是否已建立。請重新讀取，核對目前狀態。'
    : '本次未建立職務說明書，請稍後再試。';
}
