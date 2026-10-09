import { expect, test } from 'vitest';
import { canonicalUuid, isCanonicalUuid } from './uuid';

const lower = 'abcdefab-cdef-4abc-8def-abcdefabcdef';

test('only the lower-case spelling is an owned identity', () => {
  expect(isCanonicalUuid(lower)).toBe(true);
  expect(isCanonicalUuid(lower.toUpperCase())).toBe(false);
  expect(isCanonicalUuid(`${lower.slice(0, 8)}${lower.slice(8).toUpperCase()}`)).toBe(false);
  expect(isCanonicalUuid(undefined)).toBe(false);
});

test('an outside spelling maps to one canonical identity, or to none', () => {
  expect(canonicalUuid(lower)).toBe(lower);
  expect(canonicalUuid(lower.toUpperCase())).toBe(lower);
  expect(canonicalUuid('AbCdEfAb-CdEf-4aBc-8DeF-aBcDeFaBcDeF')).toBe(lower);
  for (const invalid of [
    undefined,
    null,
    7,
    '',
    ' ' + lower,
    lower + ' ',
    lower.slice(1),
    'g'.repeat(36),
  ])
    expect(canonicalUuid(invalid)).toBeNull();
});
