# Question 15

What is the recommended strategy for handling asymmetric public key rotation (JWKS) in Node.js token verification middleware?

## Summary
**The Problem:** JWT issuers rotate signing keys. Fetching JWKS for every request is slow and fragile, while caching forever rejects new keys or trusts retired ones indefinitely.

**The Solution:** Cache keys per trusted issuer and `kid`, honor HTTP caching, refresh in the background, and perform one rate-limited refresh when a token has an unknown `kid`. Keep last-known-good keys briefly for overlap, and never fetch a key URL supplied by the token.

## Why it matters
Rotation must work without an outage and without turning the verifier into an SSRF or denial-of-service target. `kid` selects among keys; it does not establish trust.

## Key Concepts
- **Trusted issuer configuration:** maps an allowlisted issuer to a fixed JWKS URI and audiences.
- **Positive cache:** retains validated public keys using bounded TTL and size.
- **Unknown-`kid` refresh:** controlled refresh supports newly published keys.
- **Rotation overlap:** issuers publish new and old keys long enough for outstanding tokens.
- **Algorithm pinning:** validation accepts only configured asymmetric algorithms.

## How to do it
1. Configure issuer, audience, JWKS URI, and algorithm allowlist outside the token.
2. Parse only enough protected header to obtain `kid` and `alg`; do not trust claims yet.
3. Resolve the key from an in-memory cache keyed by issuer and `kid`.
4. On cache miss, allow one coalesced, rate-limited JWKS refresh; reject if the key remains unknown.
5. Respect `Cache-Control`/ETag when supported and use connect/read timeouts.
6. Retain last-known-good keys during temporary issuer failure, but never beyond a bounded security policy.
7. Reject missing/duplicate `kid`, unexpected key type/use, wrong algorithm, issuer, audience, or time claims.
8. Monitor refresh failures, unknown-key rates, cache age, and verification failures.

## Example
```js
import * as jose from 'jose';

const issuer = 'https://auth.example.com/';
const jwks = jose.createRemoteJWKSet(
  new URL('https://auth.example.com/.well-known/jwks.json'),
  { cooldownDuration: 30_000, cacheMaxAge: 10 * 60_000, timeoutDuration: 3_000 },
);

export async function verifyAccessToken(token) {
  const { payload } = await jose.jwtVerify(token, jwks, {
    issuer,
    audience: 'payments-api',
    algorithms: ['RS256'],
    clockTolerance: 30,
  });
  return payload;
}
```

## Additional details
- Pin the HTTPS host or use discovery only from an allowlisted issuer; never follow arbitrary token-header URLs.
- Prevent a random-`kid` flood from forcing repeated upstream JWKS requests using cooldowns, request coalescing, and negative caching.
- Publish the new key before signing with it; retain the old public key until all tokens it signed have expired plus allowed skew.
- Emergency compromise rotation may intentionally invalidate outstanding tokens.
- Share JWKS through a local cache per process or trusted sidecar, but avoid making a central cache a hard dependency on every request.

## Why this helps
- Normal verification performs no network call.
- Controlled cache misses support rotation without request storms.
- Last-known-good data tolerates short issuer outages.
- Fixed trust configuration prevents attacker-controlled key retrieval.

## Trade-offs
| Aspect | Impact | Description |
|---|---|---|
| Long cache TTL | Mixed | Better resilience but slower retirement. |
| Short cache TTL | Mixed | Faster updates but more network dependence. |
| Unknown-key refresh | Positive | Enables rotation but needs DoS protection. |
| Last-known-good keys | Positive | Improve availability but extend trust briefly. |
| Emergency rotation | Security-first | May cause user-visible reauthentication. |

## References
- [JSON Web Key (RFC 7517)](https://www.rfc-editor.org/rfc/rfc7517.html)
- [JSON Web Algorithms (RFC 7518)](https://www.rfc-editor.org/rfc/rfc7518.html)
- [OpenID Connect Discovery 1.0](https://openid.net/specs/openid-connect-discovery-1_0.html)
