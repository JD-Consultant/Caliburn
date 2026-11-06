/** Reading a missing publication is distinct from a failed or unavailable source read. */
import { HttpError, InvalidResponseError } from '../../shared/api/http';

export function describeMemoryError(error: unknown): string {
  if (error instanceof InvalidResponseError)
    return '讀取結果與所選內容不符，尚未採用這份結果。請重新讀取。';
  if (error instanceof HttpError && error.status === 404)
    return '這份內容已無法查讀，可能已被移除。';
  if (error instanceof HttpError && error.status === 503)
    return '目前無法讀取這份內容，請稍後重試。';
  return '讀取失敗，請確認連線後重新讀取。';
}
