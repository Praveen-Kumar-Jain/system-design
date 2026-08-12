# Question 20

What is the most resilient approach for storing temporary state during third-party social logins like Apple or Google Sign-In?

## Summary
**The Problem:** OAuth/OIDC login needs temporary `state`, nonce, PKCE verifier, tenant/provider binding, and return destination. Process memory fails across replicas and restarts; putting secrets directly in browser parameters exposes them to theft and tampering.

**The Solution:** Store one-time, short-lived login transactions in a shared durable-enough store such as Redis or a database. Give the browser only an opaque high-entropy state handle in a Secure, HttpOnly, SameSite cookie or authorization request, and atomically consume the record at callback.

## Why it matters
Temporary state prevents login CSRF, code injection, provider mix-up, replay, and open redirects. It must work regardless of which replica receives the callback, so sticky sessions are unnecessary and undesirable.

## Key Concepts
- **Opaque state handle:** random lookup key with no sensitive embedded data.
- **Server-side transaction:** contains nonce, PKCE verifier, provider, tenant, redirect URI, and safe return path.
- **Atomic consume:** get-and-delete prevents callback replay.
- **Short TTL:** limits exposure and automatically cleans abandoned flows.
- **Browser binding:** signed cookie or hashed browser secret prevents state fixation.

## How to do it
1. Generate at least 128 bits of randomness for `state`, plus independent nonce and PKCE verifier.
2. Validate the return path as a same-origin internal path before storage.
3. Store a record keyed by a hash of state with a 5–10 minute TTL.
4. Include tenant, issuer, client ID, redirect URI, nonce, PKCE verifier, return path, creation time, and browser-binding hash.
5. Send only the opaque state to the authorization server; store a binding cookie with Secure, HttpOnly, and suitable SameSite attributes.
6. On callback, atomically retrieve-and-delete the record.
7. Compare browser binding, callback issuer, redirect URI, and state before exchanging the code.
8. Delete state on success or any terminal failure and rate-limit attempts.

## Example
```js
import { createHash, randomBytes } from 'node:crypto';

const hash = (value) => createHash('sha256').update(value).digest('base64url');

async function createLoginTransaction(res, details) {
  const state = randomBytes(32).toString('base64url');
  const browserSecret = randomBytes(32).toString('base64url');

  await redis.set(`oauth:${hash(state)}`, JSON.stringify({
    ...details,
    returnTo: validateInternalPath(details.returnTo),
    browserHash: hash(browserSecret),
  }), { EX: 300, NX: true });

  res.cookie('__Host-oauth-bind', browserSecret, {
    secure: true, httpOnly: true, sameSite: 'lax', path: '/', maxAge: 300_000,
  });
  return state;
}
```

```js
// Implement GETDEL atomically (or equivalent transaction/Lua on older stores).
async function consumeLoginTransaction(state, browserSecret) {
  const raw = await redis.getDel(`oauth:${hash(state)}`);
  if (!raw) throw new UnauthorizedError('Expired or replayed login');
  const tx = JSON.parse(raw);
  if (!safeEqual(tx.browserHash, hash(browserSecret))) throw new UnauthorizedError();
  return tx;
}
```

## Additional details
- A signed/encrypted self-contained state token avoids storage but is harder to make strictly single-use; replay prevention then needs state anyway.
- Redis is fast, but configure appropriate replication/persistence for the desired resilience. A database may be simpler when login volume is modest.
- Do not store transactions only in local memory in a horizontal deployment.
- Never put PKCE verifier, nonce secrets, client secret, tokens, or arbitrary return URLs directly in state.
- Use issuer identification or distinct callbacks to prevent multi-provider mix-up attacks.

## Why this helps
- Any healthy replica can finish the login.
- Atomic consumption blocks replay.
- Browser binding prevents an attacker from injecting their transaction into a victim's browser.
- TTL cleanup limits storage and exposure.
- Server-side validation prevents open redirects and provider substitution.

## Trade-offs
| Aspect | Impact | Description |
|---|---|---|
| Shared Redis/database | Positive | Reliable cross-replica flow but adds a dependency. |
| Opaque state | Positive | Minimal browser exposure but requires lookup. |
| Self-contained state | Mixed | Avoids lookup but needs encryption, key rotation, and replay controls. |
| Atomic one-time use | Positive | Strong replay protection but prevents callback retry after partial failure. |
| Short TTL | Positive | Limits risk but users may need to restart slow login flows. |

## References
- [OAuth 2.0 Security Best Current Practice (RFC 9700)](https://www.rfc-editor.org/rfc/rfc9700.html)
- [Proof Key for Code Exchange (RFC 7636)](https://www.rfc-editor.org/rfc/rfc7636.html)
- [OpenID Connect Core: nonce and state](https://openid.net/specs/openid-connect-core-1_0.html)
