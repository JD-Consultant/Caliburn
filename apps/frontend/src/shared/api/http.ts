import type { ValidateFunction } from 'ajv';

export class HttpError extends Error {
  constructor(
    public readonly status: number,
    public readonly body: unknown,
  ) {
    super('HTTP request failed');
  }
}
export class InvalidResponseError extends Error {
  constructor() {
    super('API response does not match its contract or scope');
  }
}
export class InvalidRequestError extends Error {
  constructor() {
    super('API request does not match its contract');
  }
}

async function send(
  path: string,
  options: RequestInit,
  accept = 'application/json',
  timeoutMs = 15_000,
): Promise<Response> {
  const headers = new Headers(options.headers);
  headers.set('Accept', accept);
  if (options.body !== undefined) headers.set('Content-Type', 'application/json');
  const timeout = AbortSignal.timeout(timeoutMs);
  const signal = options.signal ? AbortSignal.any([options.signal, timeout]) : timeout;
  const response = await fetch('/api' + path, {
    ...options,
    headers,
    signal,
    credentials: 'same-origin',
  });
  if (!response.ok) {
    let body: unknown;
    try {
      body = await response.json();
    } catch {
      body = undefined;
    }
    throw new HttpError(response.status, body);
  }
  return response;
}

export async function requestJson<T>(
  path: string,
  options: RequestInit,
  validate: ValidateFunction<T>,
  expectedStatus: number | readonly number[] = 200,
): Promise<T> {
  const response = await send(path, options);
  const accepted =
    typeof expectedStatus === 'number'
      ? response.status === expectedStatus
      : expectedStatus.includes(response.status);
  if (!accepted) throw new InvalidResponseError();
  let body: unknown;
  try {
    body = await response.json();
  } catch {
    throw new InvalidResponseError();
  }
  if (!validate(body)) throw new InvalidResponseError();
  return body;
}

export async function requestEmpty(path: string, options: RequestInit): Promise<void> {
  const response = await send(path, options);
  if (response.status !== 204) throw new InvalidResponseError();
}

function requireMediaResponse(response: Response, mediaType: string): void {
  const contentType = response.headers
    .get('Content-Type')
    ?.split(';')[0]
    ?.trim()
    .toLowerCase();
  if (response.status !== 200 || contentType !== mediaType)
    throw new InvalidResponseError();
}

export async function requestBlob(path: string, options: RequestInit): Promise<Blob> {
  // 後端列印允許 60 秒；保留傳輸餘裕，讓正式 504 能帶回原因。
  const response = await send(path, options, 'application/pdf', 75_000);
  requireMediaResponse(response, 'application/pdf');
  return response.blob();
}
