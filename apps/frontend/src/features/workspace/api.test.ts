import { expect, it, vi } from 'vitest';
import { getWorkspace } from './api';
import { InvalidResponseError } from '../../shared/api/http';

it('同形狀但屬於其他 Workspace 的回覆不可交給當前頁', async () => {
  vi.stubGlobal(
    'fetch',
    vi.fn().mockResolvedValue(
      Response.json({
        workspace_id: '00112233-4455-6677-8899-aabbccddeeff',
        interviewee_name: '其他受訪者',
      }),
    ),
  );
  await expect(
    getWorkspace('11112233-4455-6677-8899-aabbccddeeff'),
  ).rejects.toBeInstanceOf(InvalidResponseError);
});
