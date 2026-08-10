# Question 16

How do you architect multi-tenant authentication where each tenant enforces unique identity providers via OAuth2/OIDC?

## Summary
**The Problem:** Each tenant may use a different issuer, client registration, claims mapping, and access policy. Dynamically trusting issuer data supplied by a login request can enable mix-up attacks, SSRF, account confusion, and cross-tenant access.

**The Solution:** Maintain an allowlisted tenant-to-provider registry. Resolve the tenant before redirecting, snapshot its provider configuration into a signed one-time transaction, validate the callback against that exact issuer/client, then issue an internal token containing an authoritative tenant ID.

## Why it matters
External provider claims are not automatically application authorization. The same `sub` can mean different users under different issuers, and one email can exist across several tenants.

## Key Concepts
- **Provider registry:** validated issuer, client ID, secret reference, redirect URI, and claim mapping per tenant.
- **Login transaction:** binds tenant, issuer, state, nonce, PKCE verifier, and safe return path.
- **Composite identity:** external account key is normally `(tenant, issuer, subject)`.
- **Mix-up protection:** callback must match the issuer selected when login started.
- **Internal authorization:** application roles and tenant membership come from local policy.

## How to do it
1. Discover tenants from a verified domain, invitation, or tenant slug—not untrusted token claims.
2. Load only active, administrator-approved provider configuration.
3. Validate discovery/JWKS URLs and require HTTPS; prevent private-network SSRF.
4. Store a one-time transaction with tenant ID, exact issuer, client ID, state, nonce, PKCE verifier, and expiry.
5. On callback, atomically consume state and exchange the code only with the bound provider.
6. Verify signature, issuer, audience, nonce, time claims, and optionally authorization-response `iss`.
7. Map `(tenantId, issuer, sub)` to a local identity and evaluate membership/status.
8. Issue an internal access token with immutable `tenant_id` and application scopes.

## Example
```js
async function beginLogin(tenantSlug, returnTo) {
  const tenant = await tenants.findActiveBySlug(tenantSlug);
  const provider = await providerRegistry.get(tenant.providerId);
  const transaction = await loginTransactions.create({
    tenantId: tenant.id,
    issuer: provider.issuer,
    clientId: provider.clientId,
    state: randomSecret(), nonce: randomSecret(),
    verifier: createPkceVerifier(),
    returnTo: validateInternalPath(returnTo),
    expiresInSeconds: 300,
  });
  return buildAuthorizationUrl(provider, transaction);
}

async function finishLogin({ state, code, responseIssuer }) {
  const tx = await loginTransactions.consumeOnce(state);
  if (!tx || responseIssuer !== tx.issuer) throw new UnauthorizedError();
  const provider = await providerRegistry.getExact(tx.issuer, tx.clientId);
  const tokens = await provider.exchange(code, tx.verifier);
  const claims = await provider.verifyIdToken(tokens.id_token, tx.nonce);
  return identities.login({ tenantId: tx.tenantId, issuer: claims.iss, sub: claims.sub });
}
```

## Additional details
- Use separate redirect URIs per provider when feasible; otherwise require issuer-bound transaction state.
- Encrypt provider secrets with a managed secret store and audit configuration changes.
- Normalize claims through provider-specific adapters, but never infer tenant from email domain alone.
- Support multiple providers per tenant with explicit account-linking rules.
- Cache discovery/JWKS per issuer with bounded refresh and key-rotation handling.

## Why this helps
- An attacker cannot substitute their provider during callback handling.
- External identities remain correctly scoped to issuer and tenant.
- Local policy remains the authority for roles and resource access.
- Provider configurations can change independently without changing API authorization logic.

## Trade-offs
| Aspect | Impact | Description |
|---|---|---|
| Provider registry | Positive | Central trust control but adds configuration lifecycle. |
| Per-login state | Positive | Prevents mix-up/replay but requires shared temporary storage. |
| Claim adapters | Mixed | Support provider variation but add testing burden. |
| Tenant-specific clients | Positive | Strong isolation but more IdP registrations and secrets. |
| Shared client registration | Simpler | Lower setup cost but larger blast radius. |

## References
- [OAuth 2.0 Security Best Current Practice (RFC 9700)](https://www.rfc-editor.org/rfc/rfc9700.html)
- [OAuth Authorization Server Issuer Identification (RFC 9207)](https://www.rfc-editor.org/rfc/rfc9207.html)
- [OpenID Connect Discovery 1.0](https://openid.net/specs/openid-connect-discovery-1_0.html)

