# Question 19

How do you handle clock skew issues between distributed authentication servers and API gateways enforcing JWT expiration?

## Summary
**The Problem:** Small clock differences can cause gateways to reject newly issued tokens (`nbf`/`iat`) or expire tokens slightly earlier than clients expect.

**The Solution:** Synchronize every host with reliable time sources, use a small consistent verifier leeway, keep token lifetimes explicit, refresh before expiry, and alert on clock offset. Leeway handles network and clock jitter; it must not hide broken synchronization.

## Why it matters
JWT time claims are NumericDate seconds since the Unix epoch. Distributed validators make independent decisions, so inconsistent skew policies create intermittent authentication failures and can unintentionally extend token validity.

## Key Concepts
- **`exp`:** token must not be accepted at or after expiration, apart from configured leeway.
- **`nbf`:** token must not be accepted before this time, apart from leeway.
- **Clock tolerance:** small symmetric allowance for expected skew and transit delay.
- **Time synchronization:** NTP/chrony/cloud time service keeps nodes within policy.
- **Early refresh:** clients renew before expiry instead of at the final second.

## How to do it
1. Synchronize authorization servers, gateways, containers, and databases to trusted redundant time sources.
2. Monitor clock offset and synchronization health at the host level.
3. Define one organization-wide tolerance, commonly tens of seconds based on measured offset—not arbitrary minutes.
4. Configure the same tolerance in every JWT verifier.
5. Keep access tokens short but materially longer than maximum expected skew and request transit time.
6. Refresh proactively before `exp`, with randomized jitter to avoid a refresh stampede.
7. Do not use `iat` as the sole validity control; apply explicit maximum token age when required.
8. Reject tokens whose timestamps are implausibly far in the future even within other claim logic.

## Example
```js
import { jwtVerify } from 'jose';

export async function verifyGatewayToken(token) {
  return jwtVerify(token, jwks, {
    issuer: 'https://auth.example.com/',
    audience: 'payments-api',
    algorithms: ['ES256'],
    clockTolerance: 30,
    maxTokenAge: '10m',
  });
}
```

```js
// Refresh 60 seconds early plus jitter, never after actual expiration.
const refreshAt = (claims.exp * 1000) - 60_000 - Math.random() * 15_000;
```

## Additional details
- Leeway extends the effective acceptance window for `exp` and advances it for `nbf`; account for that in risk analysis.
- Do not manually compare formatted date strings; use a mature JOSE library.
- Container clocks normally come from the host, so fix the host time service rather than each container.
- Record validator time, issuer `iat`, `nbf`, and `exp` safely in diagnostics without logging the raw token.
- For long requests, define whether authorization is checked only at admission or again before sensitive commit.

## Why this helps
- Synchronized clocks remove the root cause of most time-claim failures.
- Uniform tolerance produces consistent decisions across gateways.
- Early refresh prevents user-visible failures near expiration.
- Offset alerts detect infrastructure issues before authentication breaks.

## Trade-offs
| Aspect | Impact | Description |
|---|---|---|
| Larger tolerance | Availability | Fewer false rejects but longer attacker-use window. |
| Smaller tolerance | Security | Tighter validity but demands excellent synchronization. |
| Early refresh | Positive | Smooth sessions but adds refresh traffic. |
| Short token TTL | Positive | Limits exposure but makes skew proportionally more important. |

## References
- [JSON Web Token time claims (RFC 7519)](https://www.rfc-editor.org/rfc/rfc7519.html#section-4.1)
- [JOSE JWT verification documentation](https://github.com/panva/jose/blob/main/docs/jwt/verify/functions/jwtVerify.md)
- [NIST Internet Time Service](https://www.nist.gov/pml/time-and-frequency-division/time-distribution/internet-time-service-its)

