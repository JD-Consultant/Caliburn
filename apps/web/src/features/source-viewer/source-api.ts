/** Read-only scoped projections from the generated HTTP operations. */
import { queryOptions } from '@tanstack/react-query';

import type {
  JdSourcesView,
  JdSourceContentView,
  JdSourceChangesView,
} from '../../shared/api/generated/http/types.gen';

import { ApiError, describeReadError, scope as checkScope } from '../../shared/api/http';
import {
  readJdSources,
  readJdSourceContent,
  readJdSourceChanges,
} from '../../shared/api/generated/http/sdk.gen';

export interface SourceScope {
  jobFileId: string;
  revisionId: string;
  citationId: string;
}

function hasIdentity(view: JdSourceContentView | JdSourceChangesView, scope: SourceScope): boolean {
  return view.revision_id === scope.revisionId && view.citation_id === scope.citationId;
}

export function describeSourceError(error: unknown): string {
  if (error instanceof ApiError) {
    if (error.code === 'jd_review_baseline_not_available')
      return '無法取得此引用的核對基準，尚不能比較 JD 變更。';
    if (error.status === 404) return '此來源目前無法讀取，請重新讀取來源列表。';
    if (error.status === 503) return '來源服務暫時無法使用，請稍後重新讀取來源列表。';
    if (error.status === 422) return '此來源無法比較差異，請重新讀取來源列表。';
  }
  return describeReadError(error);
}

export function jdSourcesQuery(jobFileId: string): ReturnType<typeof queryOptions<JdSourcesView>> {
  return queryOptions<JdSourcesView>({
    queryKey: ['jd-sources', jobFileId],
    queryFn: ({ signal }) =>
      readJdSources({
        path: { job_file_id: jobFileId },
        signal,
        throwOnError: true,
        meta: { correlation: { jobFileId } },
      }).then(({ data }) => data),
    retry: false,
    refetchOnWindowFocus: false,
  });
}

export function jdSourceContentQuery(scope: SourceScope, sourceRef: string | null) {
  return queryOptions({
    queryKey: ['jd-source-content', scope.jobFileId, scope.revisionId, scope.citationId, sourceRef],
    queryFn: ({ signal }) => {
      return readJdSourceContent({
        path: { job_file_id: scope.jobFileId, citation_id: scope.citationId },
        query: {
          revision_id: scope.revisionId,
          ...(sourceRef === null ? {} : { source_ref: sourceRef }),
        },
        signal,
        throwOnError: true,
        meta: {
          correlation: { jobFileId: scope.jobFileId },
          scope: checkScope<JdSourceContentView>((value) => hasIdentity(value, scope)),
        },
      }).then(({ data }) => data);
    },
    retry: false,
    refetchOnWindowFocus: false,
  });
}

export function jdSourceChangesQuery(scope: SourceScope) {
  return queryOptions({
    queryKey: ['jd-source-changes', scope.jobFileId, scope.revisionId, scope.citationId],
    queryFn: ({ signal }) => {
      return readJdSourceChanges({
        path: { job_file_id: scope.jobFileId, citation_id: scope.citationId },
        query: { revision_id: scope.revisionId },
        signal,
        throwOnError: true,
        meta: {
          correlation: { jobFileId: scope.jobFileId },
          scope: checkScope<JdSourceChangesView>((value) => hasIdentity(value, scope)),
        },
      }).then(({ data }) => data);
    },
    retry: false,
    refetchOnWindowFocus: false,
  });
}
