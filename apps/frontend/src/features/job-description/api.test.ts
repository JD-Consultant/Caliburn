import { expect, it, vi } from 'vitest';
import { jobDescription, workspaceId } from '../../../tests/fixtures';
import { createJobDescription, getJobDescription, lookupJobDescription } from './api';
import { HttpError, InvalidResponseError } from '../../shared/api/http';

it('只有 JD 尚不存在可成為空白入口，其他404仍是錯誤', async () => {
  vi.stubGlobal(
    'fetch',
    vi
      .fn()
      .mockResolvedValueOnce(
        Response.json({ detail: { code: 'jd_not_found' } }, { status: 404 }),
      )
      .mockResolvedValueOnce(
        Response.json({ detail: { code: 'workspace_not_found' } }, { status: 404 }),
      ),
  );
  await expect(lookupJobDescription(workspaceId)).resolves.toBeNull();
  await expect(lookupJobDescription(workspaceId)).rejects.toBeInstanceOf(HttpError);
});
it('競爭建立後查回既有 JD，不再送第二次建立', async () => {
  const fetch = vi
    .fn()
    .mockResolvedValueOnce(
      Response.json(
        { detail: { code: 'jd_already_exists', commit_status: 'not_committed' } },
        { status: 409 },
      ),
    )
    .mockResolvedValueOnce(Response.json(jobDescription));
  vi.stubGlobal('fetch', fetch);
  await expect(createJobDescription(workspaceId)).resolves.toEqual(jobDescription);
  expect(fetch).toHaveBeenCalledTimes(2);
  expect(
    fetch.mock.calls.map((call) => (call[1] as RequestInit).method ?? 'GET'),
  ).toEqual(['POST', 'GET']);
});
it('不能顯示另一個 Workspace 的 JD', async () => {
  vi.stubGlobal(
    'fetch',
    vi.fn().mockResolvedValue(
      Response.json({
        ...jobDescription,
        workspace_id: '22112233-4455-6677-8899-aabbccddeeff',
      }),
    ),
  );
  await expect(lookupJobDescription(workspaceId)).rejects.toBeInstanceOf(
    InvalidResponseError,
  );
});
it('以已知JD身分讀取時同時核對Workspace與JD', async () => {
  const fetch = vi
    .fn()
    .mockResolvedValueOnce(Response.json(jobDescription))
    .mockResolvedValueOnce(
      Response.json({
        ...jobDescription,
        job_description_id: '22112233-4455-6677-8899-aabbccddeeff',
      }),
    );
  vi.stubGlobal('fetch', fetch);
  await expect(
    getJobDescription(workspaceId, jobDescription.job_description_id),
  ).resolves.toEqual(jobDescription);
  expect(fetch.mock.calls[0]?.[0]).toBe(
    `/api/workspaces/${workspaceId}/job-descriptions/${jobDescription.job_description_id}`,
  );
  await expect(
    getJobDescription(workspaceId, jobDescription.job_description_id),
  ).rejects.toBeInstanceOf(InvalidResponseError);
});
