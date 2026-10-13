import { vi } from 'vitest';

/** UI 合成伺服器沿業務 path/body 作答；真 SDK transport 測試直接使用 Request。 */
export function stubHttp(
  handler: (path: string, options?: RequestInit) => Response | Promise<Response>,
): void {
  vi.stubGlobal(
    'fetch',
    vi.fn(async (input: RequestInfo | URL, options?: RequestInit) => {
      if (!(input instanceof Request)) return handler(String(input), options);
      const url = new URL(input.url);
      return handler(url.pathname + url.search, {
        ...(input.method === 'GET' ? {} : { method: input.method }),
        ...(input.body === null ? {} : { body: await input.clone().text() }),
        headers: input.headers,
        signal: input.signal,
        cache: input.cache,
        credentials: input.credentials,
      });
    }),
  );
}
