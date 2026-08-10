# Question 14

How do you protect stateless JWTs against Cross-Site Scripting (XSS) and Cross-Site Request Forgery (CSRF) without relying on sticky sessions?

## Summary
**The Problem:** JavaScript-readable tokens can be stolen by XSS, while cookies are sent automatically and can enable CSRF. Stateless verification and horizontal scaling do not remove either browser threat.

**The Solution:** Keep refresh/session credentials in `Secure`, `HttpOnly`, scoped cookies; use short-lived access tokens and a Backend-for-Frontend where possible; enforce `SameSite`, CSRF tokens, Origin checks, CSP, output encoding, and strict CORS. None requires sticky sessions.

## Why it matters
CSRF protections do not stop XSS, and `HttpOnly` does not stop malicious scripts from issuing same-origin requests as the victim. Defense requires both limiting token theft and preventing unauthorized cross-site requests.

## Key Concepts
- **HttpOnly cookie:** prevents direct JavaScript reads but is still automatically attached to requests.
- **SameSite:** limits cross-site cookie sending; it is defense-in-depth, not the only CSRF control.
- **CSRF token:** unpredictable value bound to the login/session and required on state-changing requests.
- **CSP and encoding:** reduce XSS injection and execution.
- **BFF pattern:** browser holds only a session cookie while the server manages OAuth tokens.

## How to do it
1. Never store long-lived refresh tokens in `localStorage` or expose them to browser JavaScript.
2. Set cookies with `Secure`, `HttpOnly`, restrictive `SameSite`, narrow `Path`, and no broad `Domain`.
3. Use a `__Host-` cookie when possible: Secure, Path `/`, and no Domain attribute.
4. For cookie-authenticated mutations, require a CSRF token and validate `Origin`/Fetch Metadata.
5. Allow only explicit trusted CORS origins and credentials; never combine wildcard origin with credentials.
6. Apply contextual output encoding, sanitization, dependency hygiene, and a nonce/hash-based CSP.
7. Keep access tokens short-lived and audience-restricted; rotate refresh tokens.
8. Do not place tokens in URLs, logs, analytics, or error reports.

## Example
```js
res.cookie('__Host-refresh', refreshToken, {
  httpOnly: true,
  secure: true,
  sameSite: 'strict',
  path: '/',
  maxAge: 7 * 24 * 60 * 60 * 1000,
});

app.use('/api', (req, res, next) => {
  if (!['GET', 'HEAD', 'OPTIONS'].includes(req.method)) {
    if (req.get('origin') !== 'https://app.example.com') {
      return res.sendStatus(403);
    }
    if (!constantTimeEqual(req.get('x-csrf-token'), req.signedCsrfToken)) {
      return res.sendStatus(403);
    }
  }
  next();
});
```

## Additional details
- If cross-site login is required, `SameSite=Lax` may be appropriate; design callback endpoints separately from general mutations.
- A double-submit cookie must be cryptographically bound to the authenticated session to avoid cookie injection weaknesses.
- Authorization headers avoid ambient-cookie CSRF, but a token stored in JavaScript-accessible storage is exposed to XSS.
- Sticky sessions are unrelated: CSRF state can be signed or stored in a shared database/cache.
- Rotate tokens after privilege changes and authentication events.

## Why this helps
- Refresh tokens are harder to exfiltrate through injected JavaScript.
- Cross-origin pages cannot perform authenticated mutations without the CSRF proof.
- CSP and encoding reduce the probability and impact of XSS.
- Any replica can validate the cookie, JWT, and CSRF binding.

## Trade-offs
| Aspect | Impact | Description |
|---|---|---|
| HttpOnly cookies | Positive | Resist token theft but require CSRF protection. |
| BFF | Positive | Strong browser token isolation but adds server endpoints/state. |
| Strict SameSite | Positive | Strong CSRF reduction but can disrupt cross-site flows. |
| CSP | Positive | Limits XSS but requires asset and script discipline. |
| Short token TTL | Mixed | Limits theft window but increases refresh frequency. |

## References
- [OWASP HTML5 Security Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/HTML5_Security_Cheat_Sheet.html)
- [OWASP CSRF Prevention Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Cross-Site_Request_Forgery_Prevention_Cheat_Sheet.html)
- [OWASP XSS Prevention Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Cross_Site_Scripting_Prevention_Cheat_Sheet.html)

