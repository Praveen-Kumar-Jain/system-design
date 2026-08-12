# Question 12

What are the security pitfalls of handling Apple Sign-In identity tokens on the backend, and how do you validate them securely?

## Summary
**The Problem:** An Apple identity token is a signed OIDC assertion, not proof merely because it decodes as JWT. Accepting it without full signature and claim validation enables forged, replayed, wrong-client, or wrong-issuer logins.

**The Solution:** Verify the JWS against Apple's current JWKS, allow only the expected algorithm, and validate issuer, audience, expiration, nonce, and authorization transaction. Use `(issuer, sub)` as the stable identity key and treat profile fields cautiously.

## Why it matters
JWT payloads are readable by anyone. Security comes from verifying the signature and binding claims to the exact application and login transaction. Apple may provide a private relay email, and the user's name is normally returned only during the first authorization.

## Key Concepts
- **Signature/JWKS:** select Apple's public key by `kid`; never trust a key supplied inside the token.
- **Issuer and audience:** require Apple's issuer and this app's Services ID or bundle identifier.
- **Nonce/state:** nonce binds the ID token to the initiated login; state binds the callback to the browser transaction.
- **Subject:** `sub` scoped to the developer/app grouping is the primary external identifier.
- **Authorization code:** exchange server-side and validate once; do not use the ID token as an Apple API access token.

## How to do it
1. Generate unpredictable `state` and `nonce` values before redirecting to Apple and store them in a one-time server-side login transaction.
2. Receive callbacks only on pre-registered HTTPS redirect URIs.
3. Atomically consume the state record and reject mismatches or expiration.
4. Verify the identity token using Apple's HTTPS JWKS and an allowlist such as `ES256`/Apple's documented algorithm—not the header alone.
5. Validate exact `iss`, allowed `aud`, `exp`, and `iat`; validate the expected nonce when used.
6. Exchange the single-use authorization code with Apple using authenticated server credentials.
7. Find or create the account using `{ issuer, sub }`, not email alone.
8. Store first-login name data immediately if needed, and process Apple account-change/revocation notifications.

## Example
```js
import * as jose from 'jose';

const appleJwks = jose.createRemoteJWKSet(
  new URL('https://appleid.apple.com/auth/keys'),
);

async function verifyAppleIdentityToken(idToken, expectedNonce) {
  const { payload } = await jose.jwtVerify(idToken, appleJwks, {
    issuer: 'https://appleid.apple.com',
    audience: [process.env.APPLE_SERVICES_ID],
    algorithms: ['RS256'],
    clockTolerance: 60,
  });

  if (!payload.sub || payload.nonce !== expectedNonce) {
    throw new Error('Invalid Apple identity token');
  }
  return payload;
}
```

Use the exact algorithm and claims currently documented for the integration. The verifier must reject `alg: none`, symmetric/asymmetric confusion, unknown audiences, and keys that do not come from Apple's trusted JWKS URL.

## Additional details
- Do not fetch an arbitrary `jku` or `x5u` URL from the JWT header; that creates SSRF and attacker-key risks.
- Cache Apple keys, but refresh on an unknown `kid` with rate limiting and keep last-known-good keys during transient outages.
- Email may be a relay address and may change; it is not a safe cross-provider account key.
- Do not overwrite an existing account merely because an asserted email matches; require an authenticated linking flow.
- Never log identity tokens, authorization codes, Apple client secrets, or refresh tokens.

## Why this helps
- Signature and claim validation prevents forged and cross-client tokens.
- Nonce and one-time state prevent replay and login CSRF.
- `(iss, sub)` avoids duplicate or incorrectly merged identities.
- Server-side exchange keeps Apple client credentials out of browsers.

## Trade-offs
| Aspect | Impact | Description |
|---|---|---|
| Remote JWKS | Positive | Supports key rotation but needs resilient caching. |
| Nonce/state store | Positive | Prevents replay but adds short-lived shared state. |
| Subject identity | Positive | Stable for the integration but not a global Apple identifier. |
| Account linking | Cost | Prevents takeover but requires explicit user experience. |

## References
- [Apple: Authenticating users with Sign in with Apple](https://developer.apple.com/documentation/signinwithapple/authenticating-users-with-sign-in-with-apple)
- [Apple: Fetch Apple's public keys](https://appleid.apple.com/auth/keys)
- [OpenID Connect Core 1.0](https://openid.net/specs/openid-connect-core-1_0.html)
