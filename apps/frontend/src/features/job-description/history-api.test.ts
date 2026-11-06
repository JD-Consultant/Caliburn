import { describe, expect, it, vi } from 'vitest';
import { jobDescription, workspaceId } from '../../../tests/fixtures';
import { InvalidRequestError, InvalidResponseError } from '../../shared/api/http';
import { listHistory, getSnapshot, compareVersions, restoreVersion } from './history-api';

const jdId = jobDescription.job_description_id;
const otherId = '22112233-4455-6677-8899-aabbccddeeff';
const base = `/api/workspaces/${workspaceId}/job-descriptions/${jdId}`;
const entry = {
  job_description_id: jdId,
  version: 1,
  kind: 'created',
  recorded_at: '2026-10-27T04:00:00Z',
  correlation_id: null,
  reverts_correlation_id: null,
  restored_from_version: null,
};
const content = Object.fromEntries(
  Object.entries(jobDescription).filter(([key]) => key !== 'version'),
);
const snapshot = { content, entry };

describe('JD歷史查詢與恢復', () => {
  it('分頁token及來源篩選依正式query編碼，保留取消signal', async () => {
    const response = {
      items: [{ ...entry, correlation_id: 'edit A', reverts_correlation_id: 'edit B' }],
      next_page_token: 'next/token+=',
    };
    const fetch = vi
      .fn<typeof globalThis.fetch>()
      .mockResolvedValue(Response.json(response));
    vi.stubGlobal('fetch', fetch);
    const abort = new AbortController();
    await expect(
      listHistory(
        workspaceId,
        jdId,
        {
          page_size: '20',
          page_token: 'old/token+=',
          correlation_id: 'edit A',
          reverts_correlation_id: 'edit B',
        },
        abort.signal,
      ),
    ).resolves.toEqual(response);
    expect(fetch.mock.calls[0]?.[0]).toBe(
      base +
        '/history?page_size=20&page_token=old%2Ftoken%2B%3D&correlation_id=edit+A&reverts_correlation_id=edit+B',
    );
    const sent = fetch.mock.calls[0]?.[1];
    expect(sent?.signal).toBeInstanceOf(AbortSignal);
    abort.abort();
    expect(sent?.signal?.aborted).toBe(true);
  });

  it('未指定分頁時不另造offset或空字串參數', async () => {
    const fetch = vi
      .fn()
      .mockResolvedValue(Response.json({ items: [], next_page_token: null }));
    vi.stubGlobal('fetch', fetch);
    await listHistory(workspaceId, jdId);
    expect(fetch.mock.calls[0]?.[0]).toBe(base + '/history');
  });

  it('按版本讀完整快照', async () => {
    const fetch = vi.fn().mockResolvedValue(Response.json(snapshot));
    vi.stubGlobal('fetch', fetch);
    await expect(getSnapshot(workspaceId, jdId, 1)).resolves.toEqual(snapshot);
    expect(fetch.mock.calls[0]?.[0]).toBe(base + '/history/1');
  });

  it('任意兩版比較保留方向，回傳結構差異', async () => {
    const response = {
      job_description_id: jdId,
      before_version: 9,
      after_version: 1,
      items: [],
      collections: [],
    };
    const fetch = vi.fn().mockResolvedValue(Response.json(response));
    vi.stubGlobal('fetch', fetch);
    await expect(compareVersions(workspaceId, jdId, 9, 1)).resolves.toEqual(response);
    expect(fetch.mock.calls[0]?.[0]).toBe(
      base + '/history:compare?before_version=9&after_version=1',
    );
  });

  it('恢復以目前前置版本送出，回覆保存後完整新版本', async () => {
    const body = { expected_version: 9, target_version: 1, correlation_id: 'restore A' };
    const response = { ...jobDescription, version: 10 };
    const fetch = vi.fn().mockResolvedValue(Response.json(response));
    vi.stubGlobal('fetch', fetch);
    await expect(restoreVersion(workspaceId, jdId, body)).resolves.toEqual(response);
    expect(fetch).toHaveBeenCalledWith(
      base + ':restore',
      expect.objectContaining({ method: 'POST', body: JSON.stringify(body) }),
    );
  });

  it.each([
    { content: { ...content, workspace_id: otherId }, entry },
    { content: { ...content, job_description_id: otherId }, entry },
    { content, entry: { ...entry, job_description_id: otherId } },
    { content, entry: { ...entry, version: 2 } },
    { content, entry: { ...entry, kind: 'unknown' } },
  ])('快照的雙方scope、指定版本與schema都必須相符', async (response) => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(Response.json(response)));
    await expect(getSnapshot(workspaceId, jdId, 1)).rejects.toBeInstanceOf(
      InvalidResponseError,
    );
  });

  it.each([
    { items: [{ ...entry, job_description_id: otherId }], next_page_token: null },
    { items: [entry], next_page_token: 123 },
  ])('歷史列表拒絕其他JD或錯誤分頁格式', async (response) => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(Response.json(response)));
    await expect(listHistory(workspaceId, jdId)).rejects.toBeInstanceOf(
      InvalidResponseError,
    );
  });

  it('有來源篩選時不接受其他來源的歷史紀錄', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(Response.json({ items: [entry], next_page_token: null })),
    );
    await expect(
      listHistory(workspaceId, jdId, { correlation_id: 'edit A' }),
    ).rejects.toBeInstanceOf(InvalidResponseError);
  });

  it.each([
    {
      job_description_id: otherId,
      before_version: 1,
      after_version: 2,
      items: [],
      collections: [],
    },
    {
      job_description_id: jdId,
      before_version: 2,
      after_version: 1,
      items: [],
      collections: [],
    },
    {
      job_description_id: jdId,
      before_version: 1,
      after_version: 2,
      items: null,
      collections: [],
    },
  ])('Diff拒絕錯誤JD、反轉版本或不合法內容', async (response) => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(Response.json(response)));
    await expect(compareVersions(workspaceId, jdId, 1, 2)).rejects.toBeInstanceOf(
      InvalidResponseError,
    );
  });

  it('不合法恢復版本在送出前拒絕', async () => {
    const fetch = vi.fn();
    vi.stubGlobal('fetch', fetch);
    await expect(
      restoreVersion(workspaceId, jdId, { expected_version: 9, target_version: 0 }),
    ).rejects.toBeInstanceOf(InvalidRequestError);
    expect(fetch).not.toHaveBeenCalled();
  });

  it('恢復失聯不可重新POST', async () => {
    const fetch = vi.fn().mockRejectedValue(new TypeError('network'));
    vi.stubGlobal('fetch', fetch);
    await expect(
      restoreVersion(workspaceId, jdId, { expected_version: 9, target_version: 1 }),
    ).rejects.toThrow();
    expect(fetch).toHaveBeenCalledTimes(1);
  });
});
