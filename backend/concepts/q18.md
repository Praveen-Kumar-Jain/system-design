# Question 18

How do you safely isolate tenant context in stateless APIs to strictly prevent cross-tenant data leakage across requests?

## Summary
**The Problem:** Reused Node.js processes handle many tenants concurrently. Global mutable tenant state, client-supplied tenant IDs, incomplete query filters, and pooled database connections can leak data across requests.

**The Solution:** Derive tenant identity from a verified token and authorized membership, place it in immutable request context, require it in every service/repository API, and enforce tenant boundaries again in the database with row-level security or physical isolation.

## Why it matters
Application filters are easy to omit. Strict isolation uses multiple independent controls so one missing predicate does not become a breach.

## Key Concepts
- **Authoritative tenant:** derived from verified identity and server-side membership, never trusted from a header/body alone.
- **Request-scoped context:** isolated with explicit parameters or `AsyncLocalStorage`, never process globals.
- **Mandatory query scope:** repositories cannot execute tenant-owned queries without tenant ID.
- **Database enforcement:** row-level security (RLS), tenant schema, or separate database.
- **Pool hygiene:** transaction-local tenant settings must reset before a connection is reused.

## How to do it
1. Verify token signature, issuer, audience, and expiry.
2. Resolve requested tenant against server-side membership and token grants.
3. create an immutable context containing tenant, subject, scopes, and request ID.
4. Pass context explicitly to domain/repository functions or use a guarded `AsyncLocalStorage` accessor.
5. Enforce tenant predicates in centralized repositories and compound keys/unique constraints.
6. Enable PostgreSQL RLS or equivalent database policy as defense-in-depth.
7. Set database tenant context with `SET LOCAL` inside a transaction, never persistent session state.
8. Partition cache keys, object paths, queue messages, metrics, and idempotency keys by tenant.
9. Test malicious tenant-ID substitution and concurrent cross-tenant requests.

## Example
```sql
ALTER TABLE invoices ENABLE ROW LEVEL SECURITY;
ALTER TABLE invoices FORCE ROW LEVEL SECURITY;

CREATE POLICY invoice_tenant_isolation ON invoices
USING (tenant_id = current_setting('app.tenant_id', true)::uuid)
WITH CHECK (tenant_id = current_setting('app.tenant_id', true)::uuid);
```

```js
async function withTenantTransaction(context, work) {
  return db.transaction(async (tx) => {
    await tx.query('SELECT set_config($1, $2, true)', [
      'app.tenant_id', context.tenantId,
    ]); // true = transaction-local; safe for pooled connections.
    return work(tx);
  });
}

app.get('/tenants/:tenantId/invoices', async (req, res) => {
  const identity = await authenticate(req);
  const context = await authorizeTenant(identity, req.params.tenantId);
  const rows = await withTenantTransaction(context, (tx) =>
    tx.query('SELECT * FROM invoices ORDER BY created_at DESC'));
  res.json(rows);
});
```

## Additional details
- Database owners and roles with `BYPASSRLS` can bypass policies; use a constrained runtime role.
- Include tenant ID in foreign keys so cross-tenant references cannot be created accidentally.
- Never reuse tenant-scoped ORM objects or DataLoaders across requests.
- Redact logs and ensure support/admin impersonation is explicit, time-limited, and audited.
- Background jobs must carry a signed/validated tenant ID and establish a fresh scope before processing.

## Why this helps
- Verified identity prevents tenant-header spoofing.
- Request isolation prevents concurrent state contamination.
- RLS catches missing application predicates.
- Namespaced infrastructure prevents indirect leakage through caches and jobs.

## Trade-offs
| Aspect | Impact | Description |
|---|---|---|
| Explicit context parameters | Positive | Visible dependencies but more function plumbing. |
| AsyncLocalStorage | Mixed | Convenient propagation but implicit and process-local. |
| RLS | Positive | Strong defense but requires policy and role discipline. |
| Separate databases | Strongest isolation | Highest provisioning and operational cost. |
| Shared tables | Efficient | Require flawless tenant-aware indexes and policies. |

## References
- [PostgreSQL Row Security Policies](https://www.postgresql.org/docs/current/ddl-rowsecurity.html)
- [Node.js AsyncLocalStorage](https://nodejs.org/api/async_context.html)
- [OWASP Authorization Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Authorization_Cheat_Sheet.html)

