import { QueryClient } from '@tanstack/react-query';

/** 正式入口與整合測試共用相同的查詢及命令政策。 */
export function createAppQueryClient(): QueryClient {
  return new QueryClient({
    defaultOptions: {
      // 瀏覽器斷網不代表 loopback API 不可用；依實際回應判斷，重連也不暗中重送。
      queries: { retry: false, networkMode: 'always', refetchOnReconnect: false },
      mutations: { retry: false, networkMode: 'always' },
    },
  });
}
