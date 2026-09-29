/** Same-origin transport. Validation, not a type assertion, admits remote data. */
export class ApiError extends Error {
  constructor(
    message: string,
    readonly status?: number,
  ) {
    super(message);
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
    );
  }
  const value: unknown = await response.json();
  if (!validate(value)) throw new ApiError('服務回傳的資料格式不符，尚未採用這份結果。');
  return value;
}

export function describeReadError(error: unknown): string {
  return error instanceof ApiError ? error.message : '連線未完成，請確認本機服務後重試。';
}
