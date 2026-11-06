import { expect, it } from 'vitest';
import { HttpError } from '../../shared/api/http';
import { requiresWriteVerification } from './errors';

it('只有正式拒絕契約可以允許再次送出，未知 409 仍需核對', () => {
  expect(requiresWriteVerification(new HttpError(409, 'proxy error'))).toBe(true);
  expect(
    requiresWriteVerification(new HttpError(409, { detail: { code: 'unexpected' } })),
  ).toBe(true);
  expect(
    requiresWriteVerification(
      new HttpError(422, { detail: { code: 'invalid_request' } }),
    ),
  ).toBe(false);
  expect(requiresWriteVerification(new TypeError('network'))).toBe(true);
});
