import { expect, it, vi } from 'vitest';
import { jobDescription, workspaceId } from '../../../tests/fixtures';
import { InvalidResponseError } from '../../shared/api/http';
import { getTurnChanges, restoreTurnChanges } from './turn-history-api';

const jdId = jobDescription.job_description_id;
const turnId = '55112233-4455-6677-8899-aabbccddeeff';
const content = { ...jobDescription, version: undefined };
const response = {
  workspace_id: workspaceId,
  job_description_id: jdId,
  turn_id: turnId,
  before_version: 9,
  after_version: 3,
  before: content,
  after: content,
  difference: {
    job_description_id: jdId,
    before_version: 9,
    after_version: 3,
    items: [],
    collections: [],
  },
};

it('輪前與模型已見版本依權威回覆保留方向，後版可較小', async () => {
  const fetch = vi.fn().mockResolvedValue(Response.json(response));
  vi.stubGlobal('fetch', fetch);
  await expect(getTurnChanges(workspaceId, jdId, turnId)).resolves.toEqual(response);
  expect(fetch.mock.calls[0]?.[0]).toBe(
    `/api/workspaces/${workspaceId}/job-descriptions/${jdId}/turns/${turnId}/changes`,
  );
});

it.each([
  { ...response, turn_id: workspaceId },
  { ...response, before: { ...content, workspace_id: jdId } },
  { ...response, after: { ...content, job_description_id: workspaceId } },
  { ...response, difference: { ...response.difference, after_version: 9 } },
])('拒絕不同輪次、前後scope或差異版本錯配', async (body) => {
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue(Response.json(body)));
  await expect(getTurnChanges(workspaceId, jdId, turnId)).rejects.toBeInstanceOf(
    InvalidResponseError,
  );
});

it('單輪撤銷使用正式無body端點，不冒用一般版本恢復', async () => {
  const fetch = vi.fn().mockResolvedValue(Response.json(jobDescription));
  vi.stubGlobal('fetch', fetch);
  await restoreTurnChanges(workspaceId, jdId, turnId);
  expect(fetch).toHaveBeenCalledWith(
    `/api/workspaces/${workspaceId}/job-descriptions/${jdId}/turns/${turnId}:restore`,
    expect.objectContaining({ method: 'POST' }),
  );
  expect(fetch.mock.calls[0]?.[1]).not.toHaveProperty('body');
});
