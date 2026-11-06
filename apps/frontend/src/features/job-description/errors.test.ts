import { expect, it } from 'vitest';
import { HttpError } from '../../shared/api/http';
import { requiresWriteVerification } from './errors';

it('只有已驗證的 not_committed 才能確定未保存；不以 HTTP 狀態猜提交結果', () => {
  expect(
    requiresWriteVerification(
      new HttpError(500, {
        detail: { code: 'jd_persistence_error', commit_status: 'not_committed' },
      }),
    ),
  ).toBe(false);
  for (const commitStatus of ['unknown', 'committed', undefined]) {
    expect(
      requiresWriteVerification(
        new HttpError(409, {
          detail: {
            code: 'conflict',
            ...(commitStatus ? { commit_status: commitStatus } : {}),
          },
        }),
      ),
    ).toBe(true);
  }
  expect(requiresWriteVerification(new TypeError('network'))).toBe(true);
});
