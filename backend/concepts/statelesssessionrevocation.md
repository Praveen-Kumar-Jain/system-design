# Question 13

How do you design a stateless user session architecture that supports instant revocation across a horizontally scaled cluster?

## Summary
**The Problem:** A self-contained JWT remains valid until it expires. Purely stateless validation therefore cannot guarantee instant revocation after logout, compromise, or privilege change.

**The Solution:** Use short-lived signed JWTs for local verification plus a small shared revocation control plane. APIs check a cached session/user version or revoked `jti` for sensitive requests, with invalidations distributed through a low-latency pub/sub channel.

## Why it matters
Instant revocation and zero shared state are mutually incompatible for already-issued bearer tokens unless every resource server receives another trusted signal. The architecture must choose a consistency boundary rather than claim both properties absolutely.

## Key Concepts
- **Session version:** monotonically increasing value embedded in tokens and stored centrally.
- **Denylist:** revoked token `jti` entries retained only until token expiration.
- **Local cache:** reduces shared-store reads but defines a bounded staleness window.
- **Invalidation event:** pushes revocation to every replica immediately.
- **Short TTL:** limits damage if an invalidation is missed.

## How to do it
1. Put `sid`, `jti`, user/session version, `iat`, and short `exp` in each access token.
2. Store authoritative session status/version in a highly available shared store.
3. On logout or compromise, atomically mark the session revoked or increment its version.
4. Publish an invalidation event and update gateway/API caches.
5. Check central state for high-risk operations; permit bounded cache checks for lower-risk reads.
6. Retain denylist entries only until the corresponding JWT expires.
7. Rotate and revoke refresh-token families independently.
8. Fail closed for sensitive endpoints when revocation state is unavailable.

## Example
```js
async function authorize(req, requiredScope) {
  const claims = await verifyJwt(req.token);
  const key = `session:${claims.sid}`;
  let state = localRevocationCache.get(key);

  if (!state || isHighRisk(req)) {
    state = await sessionStore.get(key);
    if (state) localRevocationCache.set(key, state, 5_000);
  }

  if (!state || state.revoked || claims.sver !== state.version) {
    throw new UnauthorizedError();
  }
  requireScope(claims, requiredScope);
  return claims;
}
```

## Additional details
- For mathematically immediate enforcement, perform an authoritative lookup on every request or use token introspection; caches introduce bounded delay.
- Revoke one `sid` for device logout and bump a user-wide version for “log out everywhere.”
- Protect invalidation topics against spoofing and replay.
- Persist authoritative state; pub/sub alone may lose messages while replicas restart.
- Use circuit breakers and explicit fail-open/fail-closed policy per endpoint.

## Why this helps
- Normal verification remains mostly local and horizontally scalable.
- Security events propagate rapidly across replicas.
- Version checks compactly revoke many outstanding tokens.
- Short token lifetime bounds failure if cache invalidation is delayed.

## Trade-offs
| Aspect | Impact | Description |
|---|---|---|
| Shared revocation state | Necessary | Enables instant control but is no longer purely stateless. |
| Local cache | Positive | Reduces latency but introduces a staleness window. |
| Per-request lookup | Strong consistency | Immediate enforcement at availability and latency cost. |
| Short JWT TTL | Positive | Limits exposure but increases token renewal traffic. |
| Pub/sub invalidation | Positive | Fast propagation but requires durable recovery logic. |

## References
- [OAuth Token Revocation (RFC 7009)](https://www.rfc-editor.org/rfc/rfc7009.html)
- [OAuth Token Introspection (RFC 7662)](https://www.rfc-editor.org/rfc/rfc7662.html)
- [JSON Web Token (RFC 7519)](https://www.rfc-editor.org/rfc/rfc7519.html)

