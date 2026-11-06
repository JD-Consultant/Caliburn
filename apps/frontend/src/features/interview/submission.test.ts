import { expect, it, vi } from 'vitest';
import { submitAndRecover, UnconfirmedSubmission } from './submission';

const workspaceId = '00000000-0000-4000-8000-000000000001';
const turnId = '00000000-0000-4000-8000-000000000002';
const request = { turn_id: turnId, input: '原話保留\n第二行' };
const turn = {
  workspace_id: workspaceId,
  turn_id: turnId,
  input: request.input,
  output: null,
  status: 'running',
  interrupts: [],
  usage: null,
  compactions: [],
  created_at: '2026-11-06T00:00:00Z',
  updated_at: '2026-11-06T00:00:00Z',
};

it('lost_submit_ack_uses_same_turn: 後端已受理但回覆遺失，查回原 ID 不另 POST', async () => {
  const fetcher = vi
    .fn()
    .mockRejectedValueOnce(new TypeError('offline'))
    .mockResolvedValueOnce(Response.json(turn));
  vi.stubGlobal('fetch', fetcher);
  await expect(submitAndRecover(workspaceId, request)).resolves.toEqual(turn);
  expect(fetcher).toHaveBeenCalledTimes(2);
  expect(fetcher.mock.calls[1]?.[0]).toBe(
    `/api/workspaces/${workspaceId}/agent/turns/${turnId}`,
  );
});
it('查回仍失敗明示未知，不自動新增輪次', async () => {
  const fetcher = vi.fn().mockRejectedValue(new TypeError('offline'));
  vi.stubGlobal('fetch', fetcher);
  await expect(submitAndRecover(workspaceId, request)).rejects.toBeInstanceOf(
    UnconfirmedSubmission,
  );
  expect(fetcher).toHaveBeenCalledTimes(2);
});
