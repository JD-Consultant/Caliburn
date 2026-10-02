/** Read-only HTTP projections; the canonical schemas own the wire contract. */
import { queryOptions } from '@tanstack/react-query';
import { Ajv2020 } from 'ajv/dist/2020.js';
import addFormats from 'ajv-formats';
import sourcesSchema from '../../../../api/contracts/http/jd-sources-view.schema.json' with { type: 'json' };
import contentSchema from '../../../../api/contracts/http/jd-source-content-view.schema.json' with { type: 'json' };
import changesSchema from '../../../../api/contracts/http/jd-source-changes-view.schema.json' with { type: 'json' };
import type { JdSourcesView } from '../../shared/api/generated/jd-sources-view';
import type { JdSourceContentView } from '../../shared/api/generated/jd-source-content-view';
import type { JdSourceChangesView } from '../../shared/api/generated/jd-source-changes-view';
import { ApiError, describeReadError, requestJson } from '../../shared/api/http';

const validator = new Ajv2020();
addFormats(validator);
const isSourcesView = validator.compile<JdSourcesView>(sourcesSchema);
const isContentView = validator.compile<JdSourceContentView>(contentSchema);
const isChangesView = validator.compile<JdSourceChangesView>(changesSchema);

export interface SourceScope {
  jobFileId: string;
  revisionId: string;
  citationId: string;
}

function citationUrl(scope: SourceScope): string {
  return `/api/job-files/${encodeURIComponent(scope.jobFileId)}/jd/sources/${encodeURIComponent(scope.citationId)}`;
}

function requireIdentity(
  view: JdSourceContentView | JdSourceChangesView,
  scope: SourceScope,
): void {
  if (view.revision_id !== scope.revisionId || view.citation_id !== scope.citationId) {
    throw new ApiError('回傳來源不屬於選取的正式修訂與引用，請重新讀取來源列表。');
  }
}

export function describeSourceError(error: unknown): string {
  if (error instanceof ApiError) {
    if (error.code === 'jd_review_baseline_not_available')
      return '無法取得此引用的核對基準，尚不能比較 JD 變更。';
    if (error.status === 409) return '正式 JD 已更新，請重新讀取來源列表。';
    if (error.status === 404) return '此來源目前無法讀取，請重新讀取來源列表。';
    if (error.status === 503) return '來源服務暫時無法使用，請稍後重新讀取來源列表。';
    if (error.status === 422) return '此來源無法比較差異，請重新讀取來源列表。';
  }
  return describeReadError(error);
}

export function jdSourcesQuery(jobFileId: string) {
  return queryOptions({
    // Existing manual edit, A completion and undo invalidate this formal prefix.
    queryKey: ['jd-profile', jobFileId, 'formal', 'sources'],
    queryFn: ({ signal }) =>
      requestJson(`/api/job-files/${encodeURIComponent(jobFileId)}/jd/sources`, isSourcesView, {
        signal,
      }),
    retry: false,
    refetchOnWindowFocus: false,
  });
}

export function jdSourceContentQuery(scope: SourceScope, sourceRef: string | null) {
  return queryOptions({
    queryKey: ['jd-source-content', scope.jobFileId, scope.revisionId, scope.citationId, sourceRef],
    queryFn: async ({ signal }) => {
      const params = new URLSearchParams({ revision_id: scope.revisionId });
      if (sourceRef !== null) params.set('source_ref', sourceRef);
      const view = await requestJson(`${citationUrl(scope)}?${params.toString()}`, isContentView, {
        signal,
      });
      requireIdentity(view, scope);
      return view;
    },
    retry: false,
    refetchOnWindowFocus: false,
  });
}

export function jdSourceChangesQuery(scope: SourceScope) {
  return queryOptions({
    queryKey: ['jd-source-changes', scope.jobFileId, scope.revisionId, scope.citationId],
    queryFn: async ({ signal }) => {
      const params = new URLSearchParams({ revision_id: scope.revisionId });
      const view = await requestJson(
        `${citationUrl(scope)}/changes?${params.toString()}`,
        isChangesView,
        { signal },
      );
      requireIdentity(view, scope);
      return view;
    },
    retry: false,
    refetchOnWindowFocus: false,
  });
}
