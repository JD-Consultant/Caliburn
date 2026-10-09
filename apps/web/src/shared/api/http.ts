/** Same-origin transport. Validation, not a type assertion, admits remote data. */
import { reportDiagnostic } from '../diagnostics';
import type { DiagnosticScope, FailureKind } from '../diagnostics';
import { isCanonicalUuid } from './uuid';

type ApiFailureKind = Extract<
  FailureKind,
  'http' | 'network' | 'timeout' | 'cancelled' | 'invalid_json' | 'invalid_response'
>;
interface ApiFailure {
  status?: number;
  code?: string | undefined;
  kind?: ApiFailureKind;
  requestId?: string | undefined;
}
export class ApiError extends Error {
  readonly status: number | undefined;
  readonly code: string | undefined;
  readonly kind: ApiFailureKind;
  readonly requestId: string | undefined;

  constructor(message: string, failure: ApiFailure = {}) {
    super(message);
    this.status = failure.status;
    this.code = failure.code;
    this.kind = failure.kind ?? 'invalid_response';
    this.requestId = failure.requestId;
  }
}

/** Untrusted classification token. Features recognize their codes; never display or log it. */
async function readErrorCode(response: Response): Promise<string | undefined> {
  try {
    const value: unknown = await response.json();
    if (typeof value !== 'object' || value === null || !('detail' in value)) return;
    const detail = value.detail;
    if (typeof detail !== 'object' || detail === null || !('code' in detail)) return;
    if (typeof detail.code === 'string' && /^[a-z][a-z0-9_]{0,63}$/.test(detail.code))
      return detail.code;
  } catch {
    // A malformed/unreadable error remains unconfirmed, not an explicit rejection.
  }
}

function failRequest(
  message: string,
  failure: ApiFailure,
  correlation: DiagnosticScope | undefined,
): never {
  const error = new ApiError(message, failure);
  reportDiagnostic({
    ...correlation,
    event: 'http_failure',
    kind: error.kind,
    status: error.status,
    requestId: error.requestId,
  });
  throw error;
}

export async function requestJson<T>(
  path: string,
  validate: (value: unknown) => value is T,
  options: RequestInit & { correlation?: DiagnosticScope } = {},
): Promise<T> {
  const { correlation, ...request } = options;
  const timeout = AbortSignal.timeout(15_000);
  const signal = request.signal ? AbortSignal.any([request.signal, timeout]) : timeout;
  let response: Response;
  try {
    response = await fetch(path, {
      ...request,
      credentials: 'same-origin',
      signal,
    });
  } catch {
    const kind = request.signal?.aborted ? 'cancelled' : timeout.aborted ? 'timeout' : 'network';
    failRequest('連線未完成，請確認本機服務後重試。', { kind }, correlation);
  }
  const header = response.headers.get('X-Request-ID');
  const requestId = isCanonicalUuid(header) ? header : undefined;
  if (!response.ok) {
    // Do not render arbitrary server/debug bodies or private input echoed by an error.
    const code = await readErrorCode(response);
    if (signal.aborted) {
      failRequest(
        '連線未完成，請確認本機服務後重試。',
        {
          kind: request.signal?.aborted ? 'cancelled' : 'timeout',
          status: response.status,
          requestId,
        },
        correlation,
      );
    }
    failRequest(
      response.status === 404
        ? '找不到這項資料或服務。請重新讀取；若持續發生，請確認本機服務。'
        : '暫時無法取得服務結果，請稍後再試。',
      { status: response.status, code, kind: 'http', requestId },
      correlation,
    );
  }
  let value: unknown;
  try {
    value = response.status === 204 ? undefined : await response.json();
  } catch {
    const kind = request.signal?.aborted
      ? 'cancelled'
      : timeout.aborted
        ? 'timeout'
        : 'invalid_json';
    failRequest(
      '服務回傳的資料格式不符，尚未採用這份結果。',
      {
        status: response.status,
        kind,
        requestId,
      },
      correlation,
    );
  }
  if (!validate(value)) {
    failRequest(
      '服務回傳的資料格式不符，尚未採用這份結果。',
      {
        status: response.status,
        kind: 'invalid_response',
        requestId,
      },
      correlation,
    );
  }
  return value;
}

export function describeReadError(error: unknown): string {
  return error instanceof ApiError ? error.message : '連線未完成，請確認本機服務後重試。';
}
