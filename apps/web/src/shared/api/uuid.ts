/**
 * UUID identity shared by routes, recovery storage and cross-tab messages.
 *
 * Inside the app an identity has one spelling: the lower-case form the API emits and
 * `crypto.randomUUID()` produces. A typed or pasted spelling may use capitals (RFC 9562 §4),
 * so only `canonicalUuid` accepts input from outside (the route); everything it returns, and
 * every value this app stores or broadcasts, is compared and used as a scope key as-is.
 */
const CANONICAL_UUID = /^[0-9a-f]{8}-(?:[0-9a-f]{4}-){3}[0-9a-f]{12}$/;

/** True only for the canonical (lower-case) spelling; the guard for values this app owns. */
export function isCanonicalUuid(value: unknown): value is string {
  return typeof value === 'string' && CANONICAL_UUID.test(value);
}

/** The single place an outside spelling becomes an identity; null when it is not a UUID. */
export function canonicalUuid(value: unknown): string | null {
  if (typeof value !== 'string') return null;
  const canonical = value.toLowerCase();
  return CANONICAL_UUID.test(canonical) ? canonical : null;
}
