import { expect, it, vi } from 'vitest';
import { cancelTurn, getTurn, listTurns } from './api';
import { InvalidResponseError } from '../../shared/api/http';

const workspaceId = '00000000-0000-4000-8000-000000000001';
const turnId = '00000000-0000-4000-8000-000000000002';
const turn = {
  workspace_id: workspaceId,
  turn_id: turnId,
  status: 'completed',
  input: '原話',
  output: '結果',
  interrupts: [],
  usage: null,
  compactions: [],
  created_at: '2026-11-06T00:00:00Z',
  updated_at: '2026-11-06T00:00:00Z',
};
it('turn與workspace scope不符拒絕回覆', async () => {
  vi.stubGlobal(
    'fetch',
    vi.fn().mockResolvedValue(Response.json({ ...turn, turn_id: workspaceId })),
  );
  await expect(getTurn(workspaceId, turnId)).rejects.toBeInstanceOf(InvalidResponseError);
});
it('輪列表不允許混入別的workspace', async () => {
  vi.stubGlobal(
    'fetch',
    vi.fn().mockResolvedValue(Response.json([{ ...turn, workspace_id: turnId }])),
  );
  await expect(listTurns(workspaceId)).rejects.toBeInstanceOf(InvalidResponseError);
});
it('cancel僅204可確認，200空物件不是成功', async () => {
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue(Response.json({})));
  await expect(cancelTurn(workspaceId, turnId)).rejects.toBeInstanceOf(
    InvalidResponseError,
  );
});
