import { expect, it, vi } from 'vitest';
import { jobDescription, workspaceId } from '../../../../tests/fixtures';
import { InvalidResponseError } from '../../../shared/api/http';
import { getCitation } from './source-api';
import { citation, citationDetail } from './source-fixtures';

const scope = {
  workspaceId,
  jobDescriptionId: jobDescription.job_description_id,
  citation,
};
const base = `/api/workspaces/${workspaceId}/job-descriptions/${jobDescription.job_description_id}`;

it('固定歷史 JD 版放在路徑，Memory 比較發布版獨立放在 query', async () => {
  const fetch = vi.fn().mockResolvedValue(Response.json(citationDetail));
  vi.stubGlobal('fetch', fetch);
  await expect(
    getCitation({ ...scope, version: 8, comparisonPublishedVersion: 5 }),
  ).resolves.toEqual(citationDetail);
  expect(fetch.mock.calls[0]?.[0]).toBe(
    `${base}/history/8/citations/${citation.id}?published_version=5`,
  );
});

it('目前來源不冒用歷史端點，保留未知核對狀態', async () => {
  const fetch = vi.fn().mockResolvedValue(Response.json(citationDetail));
  vi.stubGlobal('fetch', fetch);
  expect((await getCitation(scope)).needs_recheck).toBeNull();
  expect(fetch.mock.calls[0]?.[0]).toBe(`${base}/citations/${citation.id}`);
});

it.each([
  { ...citationDetail, citation: { ...citation, id: workspaceId } },
  { ...citationDetail, citation: { ...citation, target_id: workspaceId } },
  {
    ...citationDetail,
    source: {
      ...citationDetail.source,
      source: { ...citation.source, workspace_id: jobDescription.job_description_id },
    },
  },
  {
    ...citationDetail,
    source: {
      ...citationDetail.source,
      source: { ...citation.source, published_version: 99 },
    },
  },
])('拒絕回應引用或來源座標不符', async (response) => {
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue(Response.json(response)));
  await expect(getCitation(scope)).rejects.toBeInstanceOf(InvalidResponseError);
});
