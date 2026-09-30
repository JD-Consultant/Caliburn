/** Same-origin transport. Validation, not a type assertion, admits remote data. */
export class ApiError extends Error {
  constructor(
    message: string,
    readonly status?: number,
    readonly code?: string,
  ) {
    super(message);
  }
}

// Only public transport codes needed for explicit input rejection are retained.
// Never keep arbitrary error bodies, echoed input, or provider diagnostics.
const publicErrorCodes = new Set([
  'database_not_configured',
  'model_not_configured',
  'consultant_unavailable',
  'job_file_not_found',
]);

async function readPublicErrorCode(response: Response): Promise<string | undefined> {
  try {
    const value: unknown = await response.json();
    if (typeof value !== 'object' || value === null || !('detail' in value)) return;
    const detail = value.detail;
    if (typeof detail !== 'object' || detail === null || !('code' in detail)) return;
    if (typeof detail.code === 'string' && publicErrorCodes.has(detail.code)) return detail.code;
  } catch {
    // A malformed/unreadable error remains unconfirmed, not an explicit rejection.
  }
}

export async function requestJson<T>(
  path: string,
  validate: (value: unknown) => value is T,
  options: RequestInit = {},
): Promise<T> {
  const timeout = AbortSignal.timeout(15_000);
  const response = await fetch(path, {
    ...options,
    credentials: 'same-origin',
    signal: options.signal ? AbortSignal.any([options.signal, timeout]) : timeout,
  });
  if (!response.ok) {
    // Do not render arbitrary server/debug bodies or private input echoed by an error.
    throw new ApiError(
      response.status === 404
        ? '找不到這份職務檔案。請回清單重新選取。'
        : '暫時無法取得服務結果，請稍後再試。',
      response.status,
      await readPublicErrorCode(response),
    );
  }
  const value: unknown = await response.json();
  if (!validate(value)) throw new ApiError('服務回傳的資料格式不符，尚未採用這份結果。');
  return value;
}

export function describeReadError(error: unknown): string {
  return error instanceof ApiError ? error.message : '連線未完成，請確認本機服務後重試。';
}
