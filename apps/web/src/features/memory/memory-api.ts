/** Latest publication navigation and fixed-snapshot body reads have separate cache keys. */
import { queryOptions } from '@tanstack/react-query';

import type { PublishedMemoryObject } from '../../shared/api/generated/http/types.gen';
import { scope } from '../../shared/api/http';
import { readLatestMemory, readMemoryObject } from '../../shared/api/generated/http/sdk.gen';

export function publishedMemoryQuery(jobFileId: string) {
  return queryOptions({
    queryKey: ['published-memory', jobFileId],
    queryFn: ({ signal }) =>
      readLatestMemory({
        path: { job_file_id: jobFileId },
        signal,
        throwOnError: true,
        meta: { correlation: { jobFileId } },
      }).then(({ data }) => data),
    retry: false,
    refetchOnWindowFocus: false,
  });
}

export function memoryObjectQuery(jobFileId: string, snapshotId: string, objectId: string) {
  return queryOptions({
    queryKey: ['memory-object', jobFileId, snapshotId, objectId],
    queryFn: ({ signal }) =>
      readMemoryObject({
        path: { job_file_id: jobFileId, snapshot_id: snapshotId, object_id: objectId },
        signal,
        throwOnError: true,
        meta: {
          correlation: { jobFileId },
          scope: scope<PublishedMemoryObject>(
            (value) => value.snapshot_id === snapshotId && value.object_id === objectId,
          ),
        },
      }).then(({ data }) => data),
    retry: false,
    staleTime: Infinity,
  });
}
