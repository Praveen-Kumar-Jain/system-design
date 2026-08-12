# Question 17

What are the exact steps to implement Proof Key for Code Exchange (PKCE) flow for backend-to-backend authorization?

## Summary
**The Problem:** PKCE is often misapplied to pure machine-to-machine authentication. PKCE protects an OAuth authorization code as it travels through a user agent; it does not authenticate an autonomous backend service.

**The Solution:** For an authorization-code flow handled by a backend, use PKCE with `S256` in addition to confidential-client authentication. For true backend-to-backend access with no user interaction, use client credentials, private-key JWT, mTLS, or workload identity instead.

## Why it matters
PKCE stops a party that steals or injects an authorization code from redeeming it without the transaction-specific verifier. It does not prove service identity and cannot replace confidential-client authentication where that is required.

## Exact PKCE steps
1. Generate a cryptographically random `code_verifier` containing 43–128 unreserved characters.
2. Calculate `BASE64URL(SHA256(ASCII(code_verifier)))` as the `code_challenge`.
3. Generate one-time `state`; for OIDC also generate `nonce`.
4. Store verifier, state, nonce, issuer, client ID, redirect URI, and expiry in a server-side transaction bound to the initiating browser.
5. Redirect the user agent to the authorization endpoint with `response_type=code`, exact `redirect_uri`, scope, state, `code_challenge`, and `code_challenge_method=S256`.
6. At the callback, atomically consume and compare state; verify returned issuer when supported.
7. Send the code, original redirect URI, client ID, and `code_verifier` to the token endpoint over TLS. A confidential client also authenticates itself.
8. Verify the OIDC ID token signature, issuer, audience, nonce, and time claims.
9. Delete the transaction whether exchange succeeds or fails; never reuse the verifier or code.
10. For no-browser service authorization, skip this flow and use an appropriate machine credential.

## Example
```js
import { createHash, randomBytes } from 'node:crypto';

const base64url = (buffer) => buffer.toString('base64url');
const verifier = base64url(randomBytes(32));
const challenge = base64url(createHash('sha256').update(verifier, 'ascii').digest());

const authorizeUrl = new URL(provider.authorization_endpoint);
authorizeUrl.search = new URLSearchParams({
  response_type: 'code', client_id: CLIENT_ID,
  redirect_uri: REDIRECT_URI, scope: 'openid profile',
  state, nonce, code_challenge: challenge,
  code_challenge_method: 'S256',
}).toString();
```

```js
const response = await fetch(provider.token_endpoint, {
  method: 'POST',
  headers: { 'content-type': 'application/x-www-form-urlencoded' },
  body: new URLSearchParams({
    grant_type: 'authorization_code', code,
    redirect_uri: REDIRECT_URI, client_id: CLIENT_ID,
    code_verifier: storedTransaction.verifier,
    client_secret: CLIENT_SECRET,
  }),
});
```

## Additional details
- Use only `S256`; do not fall back to `plain` after an error.
- PKCE values must be transaction-specific and bound to the same user-agent session.
- The authorization server must reject a verifier when no challenge was present, preventing downgrade.
- Never send the verifier in the authorization request or log it.
- For service-to-service flows, prefer short-lived workload credentials over static shared secrets.

## Why this helps
- A stolen authorization code cannot be redeemed without the verifier.
- State/nonce and issuer binding prevent callback and mix-up attacks.
- Confidential-client authentication and PKCE protect different boundaries.
- Correct M2M credentials avoid an unnecessary browser flow.

## Trade-offs
| Aspect | Impact | Description |
|---|---|---|
| PKCE `S256` | Positive | Strong code binding with small implementation cost. |
| Server transaction | Necessary | Protects verifier but requires temporary shared state. |
| Client credentials | M2M fit | Simple, but represents the service rather than a user. |
| Workload identity | Positive | Short-lived credentials but requires platform integration. |

## References
- [Proof Key for Code Exchange (RFC 7636)](https://www.rfc-editor.org/rfc/rfc7636.html)
- [OAuth 2.0 Security Best Current Practice (RFC 9700)](https://www.rfc-editor.org/rfc/rfc9700.html)
- [OAuth 2.0 Client Credentials Grant (RFC 6749)](https://www.rfc-editor.org/rfc/rfc6749.html#section-4.4)

