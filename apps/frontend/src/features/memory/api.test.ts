import { expect, it, vi } from 'vitest';
import { InvalidResponseError } from '../../shared/api/http';
import { getMemoryItem, getMemoryMap, getMemorySourceMessage } from './api';

const workspaceId = '10000000-0000-4000-8000-000000000001';
const itemId = '20000000-0000-4000-8000-000000000001';
const otherId = '20000000-0000-4000-8000-000000000002';
const item = {
  workspace_id: workspaceId,
  published_version: 3,
  item_id: itemId,
  kind: 'situation',
  title: '盤點存貨',
  description: '每週核對',
  changed_version: 2,
  body: '固定第三版正文',
  source_ids: [],
};

it.each([{ workspace_id: otherId }, { published_version: 4 }, { item_id: otherId }])(
  '拒絕固定發布版項目的身分錯配 %j',
  async (mismatch) => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(Response.json({ ...item, ...mismatch })),
    );
    await expect(getMemoryItem(workspaceId, 3, itemId)).rejects.toBeInstanceOf(
      InvalidResponseError,
    );
  },
);

it('無發布是合法空狀態，同形的其他 Workspace 導覽仍拒絕', async () => {
  const empty = {
    workspace_id: workspaceId,
    published_version: null,
    covered_through_message_id: null,
    items: [],
  };
  vi.stubGlobal(
    'fetch',
    vi
      .fn()
      .mockResolvedValueOnce(Response.json(empty))
      .mockResolvedValueOnce(Response.json({ ...empty, workspace_id: otherId })),
  );
  await expect(getMemoryMap(workspaceId)).resolves.toEqual(empty);
  await expect(getMemoryMap(workspaceId)).rejects.toBeInstanceOf(InvalidResponseError);
});

it('正文只讀指定發布版，不會改讀最新版本', async () => {
  const fetch = vi.fn().mockResolvedValue(Response.json(item));
  vi.stubGlobal('fetch', fetch);
  await expect(getMemoryItem(workspaceId, 3, itemId)).resolves.toEqual(item);
  expect(fetch).toHaveBeenCalledWith(
    `/api/workspaces/${workspaceId}/memory/versions/3/items/${itemId}`,
    expect.anything(),
  );
});

it('拒絕讀取不符所選來源 ID 的訪談訊息', async () => {
  vi.stubGlobal(
    'fetch',
    vi.fn().mockResolvedValue(
      Response.json({
        message_id: otherId,
        turn_id: '30000000-0000-4000-8000-000000000001',
        position: 0,
        speaker: 'employee',
        kind: 'text',
        content: { text: '其他訊息' },
        reply_to_message_id: null,
        created_at: '2026-11-06T00:00:00Z',
      }),
    ),
  );
  await expect(getMemorySourceMessage(workspaceId, itemId)).rejects.toBeInstanceOf(
    InvalidResponseError,
  );
});
