import { afterEach, expect, test, vi } from 'vitest';
import { requestJson } from './http';

afterEach(() => vi.unstubAllGlobals());

test.each([
  { body: { detail: { code: 'not_found' } }, name: 'unknown resource' },
  { body: { detail: { code: 'consultant_turn_not_found' } }, name: 'missing turn' },
  { body: { detail: 'private diagnostic' }, name: 'unstructured error' },
])('a 404 for $name does not claim that the job file is missing', async ({ body }) => {
  vi.stubGlobal('fetch', () => Promise.resolve(Response.json(body, { status: 404 })));
  await expect(
    requestJson('/api/example/reasoning-summaries', Array.isArray),
  ).rejects.toMatchObject({
    status: 404,
    message: '找不到這項資料或服務。請重新讀取；若持續發生，請確認本機服務。',
  });
});

test('an explicit missing-job-file error retains the file-selection guidance', async () => {
  vi.stubGlobal('fetch', () =>
    Promise.resolve(
      Response.json(
        {
          detail: { code: 'job_file_not_found', debug: 'private diagnostic' },
        },
        { status: 404 },
      ),
    ),
  );
  await expect(requestJson('/api/example', Array.isArray)).rejects.toMatchObject({
    status: 404,
    code: 'job_file_not_found',
    message: '找不到這份職務檔案。請回清單重新選取。',
  });
});
