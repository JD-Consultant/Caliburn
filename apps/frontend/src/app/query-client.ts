import { QueryClient } from '@tanstack/react-query';
import { HttpError, InvalidResponseError } from '../shared/api/http';

export function createQueryClient() {
  return new QueryClient({
    defaultOptions: {
      queries: {
        staleTime: 15_000,
        retry: (failures, error) =>
          failures < 1 &&
          !(error instanceof InvalidResponseError) &&
          (!(error instanceof HttpError) || error.status >= 500),
      },
      mutations: { retry: false, networkMode: 'always' },
    },
  });
}
