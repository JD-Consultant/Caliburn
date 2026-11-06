import type {
  CitationDetailsResponse,
  CitationResponse,
} from '../../../shared/api/generated/types.gen';
import { validateCitationDetailsResponse } from '../../../shared/api/generated/validators';
import { InvalidResponseError, requestJson } from '../../../shared/api/http';
import { jobDescriptionPath, requireVersion } from '../api-transport';

export type CitationScope = {
  workspaceId: string;
  jobDescriptionId: string;
  citation: CitationResponse;
  version?: number | undefined;
  comparisonPublishedVersion?: number | undefined;
};

function sameSource(
  left: CitationResponse['source'],
  right: CitationResponse['source'],
): boolean {
  if (left.workspace_id.toLowerCase() !== right.workspace_id.toLowerCase()) return false;
  if (left.kind === 'interview' && right.kind === 'interview')
    return left.message_id.toLowerCase() === right.message_id.toLowerCase();
  if (left.kind === 'memory' && right.kind === 'memory')
    return (
      left.item_id.toLowerCase() === right.item_id.toLowerCase() &&
      left.published_version === right.published_version
    );
  return false;
}

/** Historical JD versions and Memory comparison versions are independent coordinates. */
export async function getCitation(
  scope: CitationScope,
  signal?: AbortSignal,
): Promise<CitationDetailsResponse> {
  const { workspaceId, jobDescriptionId, citation, version, comparisonPublishedVersion } =
    scope;
  if (version !== undefined) requireVersion(version);
  if (comparisonPublishedVersion !== undefined)
    requireVersion(comparisonPublishedVersion);
  const query =
    comparisonPublishedVersion === undefined
      ? ''
      : `?published_version=${String(comparisonPublishedVersion)}`;
  const historical = version === undefined ? '' : `/history/${String(version)}`;
  const result = await requestJson(
    jobDescriptionPath(workspaceId, jobDescriptionId) +
      historical +
      `/citations/${encodeURIComponent(citation.id)}` +
      query,
    { signal: signal ?? null },
    validateCitationDetailsResponse,
  );
  if (
    result.citation.id.toLowerCase() !== citation.id.toLowerCase() ||
    result.citation.target_kind !== citation.target_kind ||
    result.citation.target_id.toLowerCase() !== citation.target_id.toLowerCase() ||
    result.citation.source.workspace_id.toLowerCase() !== workspaceId.toLowerCase() ||
    !sameSource(result.citation.source, citation.source) ||
    !sameSource(result.source.source, citation.source)
  )
    throw new InvalidResponseError();
  const comparison = result.comparison;
  if (comparison) {
    const contents = [comparison.before, ...(comparison.after ? [comparison.after] : [])];
    if (
      citation.source.kind !== 'memory' ||
      contents.some(
        (content) =>
          content.item.id.toLowerCase() !==
            (citation.source.kind === 'memory'
              ? citation.source.item_id.toLowerCase()
              : '') ||
          [content.item, ...content.situations].some(
            (item) => item.workspace_id.toLowerCase() !== workspaceId.toLowerCase(),
          ),
      )
    )
      throw new InvalidResponseError();
  }
  return result;
}
