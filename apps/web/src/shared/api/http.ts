/** 同源 SDK 政策：遠端形狀與操作 scope 驗證先於消費端。 */
import { reportDiagnostic } from '../diagnostics';
import type { DiagnosticScope, FailureKind } from '../diagnostics';
import { client } from './generated/http/client.gen';
import type { ResolvedRequestOptions } from './generated/http/client';
import type { ClientMeta } from './generated/http/core/types.gen';
import { responsePolicies } from './generated/http/validators.js';
import { isCanonicalUuid } from './uuid';

type ApiFailureKind = Extract<
  FailureKind,
  'http' | 'network' | 'timeout' | 'cancelled' | 'invalid_json' | 'invalid_response'
>;
interface ApiFailure {
  status?: number | undefined;
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

/** 僅在生成的操作驗證器已確認回應形狀後使用。 */
export function scope<T>(predicate: (value: T) => boolean): (value: unknown) => boolean {
  return (value) => predicate(value as T);
}
type HttpOptions = ResolvedRequestOptions & { meta?: ClientMeta };

declare module './generated/http/core/types.gen' {
  interface ClientMeta {
    correlation?: DiagnosticScope;
    scope?: (value: unknown) => boolean;
  }
}

const invalidMessage = '服務回傳的資料格式不符，尚未採用這份結果。';
const connectionMessage = '連線未完成，請確認本機服務後重試。';

client.setConfig({
  baseUrl: globalThis.location?.origin ?? 'http://localhost',
  credentials: 'same-origin',
  throwOnError: true,
  fetch: (input, init) => globalThis.fetch(input, init),
});
client.interceptors.request.use(
  (request, options) =>
    new Request(request, {
      signal: options.signal
        ? AbortSignal.any([options.signal, AbortSignal.timeout(15_000)])
        : AbortSignal.timeout(15_000),
    }),
);
client.interceptors.response.use(async (response, _request, options: HttpOptions) => {
  if (!response.ok) return response;
  const policies = responsePolicies[`${options.method} ${options.url}`];
  if (policies) {
    const policy = policies[response.status];
    if (!policy) throw new Error('Unexpected response status');
    if (policy.kind === 'empty') {
      // 真瀏覽器的 204 也可能提供空串流；依實際正文判斷，不依物件是否存在。
      if ((await response.clone().arrayBuffer()).byteLength !== 0)
        throw new Error('Unexpected response body');
      return response;
    }
    if (policy.kind === 'media') {
      const mediaType = response.headers.get('Content-Type')?.split(';')[0]?.trim().toLowerCase();
      if (!mediaType || !policy.mediaTypes.includes(mediaType))
        throw new Error('Unexpected response media type');
      return response;
    }
    // JSON operation 依正式契約解析，不能被錯置的 text/html 繞過驗證。
    options.parseAs = 'json';
    if (response.headers.get('Content-Length') === '0')
      throw new Error('Invalid empty JSON response');
    options.responseValidator = (value) => {
      if (!policy.validate(value) || (options.meta?.scope && !options.meta.scope(value)))
        throw new Error('Invalid response');
      return Promise.resolve(value);
    };
  }
  return response;
});
client.interceptors.error.use((error, response, request, options: HttpOptions) => {
  const kind: ApiFailureKind = options.signal?.aborted
    ? 'cancelled'
    : request?.signal.aborted
      ? 'timeout'
      : response?.ok
        ? error instanceof SyntaxError
          ? 'invalid_json'
          : 'invalid_response'
        : response
          ? 'http'
          : 'network';
  const header = response?.headers.get('X-Request-ID');
  const requestId = isCanonicalUuid(header) ? header : undefined;
  let code: string | undefined;
  if (typeof error === 'object' && error !== null && 'detail' in error) {
    const detail = error.detail;
    if (
      typeof detail === 'object' &&
      detail !== null &&
      'code' in detail &&
      typeof detail.code === 'string' &&
      /^[a-z][a-z0-9_]{0,63}$/.test(detail.code)
    )
      code = detail.code;
  }
  const message =
    kind === 'http'
      ? response?.status === 404
        ? '找不到這項資料或服務。請重新讀取；若持續發生，請確認本機服務。'
        : '暫時無法取得服務結果，請稍後再試。'
      : kind === 'invalid_json' || kind === 'invalid_response'
        ? invalidMessage
        : connectionMessage;
  const failure = new ApiError(message, { kind, status: response?.status, code, requestId });
  reportDiagnostic({
    ...options.meta?.correlation,
    event: 'http_failure',
    kind,
    status: failure.status,
    requestId,
  });
  return failure;
});

export function describeReadError(error: unknown): string {
  return error instanceof ApiError ? error.message : connectionMessage;
}
