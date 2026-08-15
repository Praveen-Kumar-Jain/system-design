# Question 2

What specific PostgreSQL indexing strategies, such as BRIN or partial indexes, do you use to optimize query performance on massive, append-only audit logs?

## Summary
**The Problem:** Massive append-only audit logs can become slow to query if indexes are too large or too many.
**The Solution:** Use BRIN for time-range scans and partial indexes for rare, high-value rows such as errors or security events.

## Why it matters
Audit logs can grow to billions of rows quickly. A full B-tree index on every field slows inserts, increases storage, and makes maintenance harder.

## Key Concepts
- **BRIN indexes:** small summary indexes that work well on time-ordered data.
- **Partial indexes:** narrow indexes for rare but important rows, like errors or login failures.
- **Index selectivity:** keep only the indexes that support actual query patterns.
- **Query planning:** use `EXPLAIN` to make sure PostgreSQL chooses the right index path.

## How to do it
1. Keep the audit log table narrow and index only the columns your queries use.
2. Use a BRIN index on `created_at` or `event_time` when rows are inserted in roughly time order.
3. Add partial indexes for rare but important rows, such as `severity = 'ERROR'` or `event_type = 'LOGIN_FAILED'`.
4. Partition the table by date if the log grows very large, and maintain BRIN indexes on each partition.
5. Avoid indexing large JSONB payloads unless you need frequent exact path searches.
6. Check `pg_stat_all_indexes` or `pg_stat_user_indexes` to verify index use and remove unused indexes.
7. Test query plans with `EXPLAIN` and `EXPLAIN ANALYZE` to confirm the planner is using the right index path.

## Example
```sql
CREATE TABLE audit_logs (
    id BIGSERIAL PRIMARY KEY,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    tenant_id UUID NOT NULL,
    severity VARCHAR(10) NOT NULL,
    event_type VARCHAR(50) NOT NULL,
    payload JSONB
);

CREATE INDEX idx_audit_logs_created_at_brin
    ON audit_logs USING BRIN (created_at);

CREATE INDEX idx_audit_logs_errors
    ON audit_logs (event_type, tenant_id)
    WHERE severity = 'ERROR';

CREATE INDEX idx_audit_logs_failed_logins
    ON audit_logs (tenant_id, event_type)
    WHERE event_type = 'LOGIN_FAILED' AND severity = 'ERROR';
```

For a query like this:

```sql
SELECT *
FROM audit_logs
WHERE created_at >= now() - interval '7 days'
  AND severity = 'ERROR'
  AND event_type = 'LOGIN_FAILED';
```

- The BRIN index narrows the time window to recent blocks.
- The partial index finds only the error login events.
- That combination avoids scanning the whole table and keeps the query fast.

## Additional details
- BRIN indexes store a summary per block range, not one entry per row. That makes them very small and cheap to maintain.
- When data is inserted in time order, BRIN can skip entire old blocks quickly.
- Partial indexes contain only rows that match their condition, so they stay small even as the table grows.
- Use a full B-tree index only for exact-match queries that need it, such as precise tenant lookups.
- If the table is partitioned by day or month, each partition can have its own BRIN index and partial index.
- Use `pg_stat_all_indexes` to see how many index scans happen and which indexes are unused.
- If you use JSONB payloads, prefer GIN indexes only for the specific queries you need.
- Keep insert paths simple: avoid too many indexes, wide rows, or complex expressions on the hot table.

## Why this helps
- Smaller indexes reduce insert overhead and disk writes.
- BRIN lets PostgreSQL skip old data cheaply instead of scanning row by row.
- Partial indexes keep rare-event queries fast by focusing only on the important rows.
- A focused index strategy keeps audit logs usable even when they grow very large.

## Trade-offs
- **BRIN:** excellent for time-range filtering, but not good for exact value lookups.
- **Partial indexes:** only help when the query matches the filter condition.
- **More indexes:** improve some reads but still slow inserts and use more disk.
- **Index tuning:** requires review and may need adjustments as query patterns change.

## References
- PostgreSQL BRIN index documentation
- PostgreSQL partial index documentation
- PostgreSQL time-series indexing best practices
