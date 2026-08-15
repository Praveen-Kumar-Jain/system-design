# Question 1

How do you design a PostgreSQL schema to efficiently handle high-frequency, multi-tenant financial transaction inserts without severe lock contention?

## Summary
**The Problem:** High-frequency multi-tenant financial inserts can cause lock contention, slow writes, and resource pressure if the transaction table is too hot.
**The Solution:** Use a narrow append-only table, partition by time/tenant, and keep indexes small so writes stay fast and the system stays stable.

## Key Concepts
- **Append-only writes:** keep the main transaction table mostly inserts and avoid frequent updates.
- **Partitioning:** divide data by time or tenant so each operation touches a smaller part of the table.
- **Narrow indexes:** use only the indexes needed for common queries to reduce insert cost.
- **Tenant isolation:** separate customer data logically to limit lock contention and make scaling easier.

## Why it matters
If rows are inserted thousands of times per second, the database should do as little work as possible for each insert.

- **Keep writes simple:** insert rows once, and avoid updating rows in the hot transaction table.
- **Separate tenants:** isolate tenant data so one tenant does not slow down another tenant's writes.
- **Avoid large indexes:** every index slows down inserts. Only add indexes that support your main query paths.
- **Use partitioning:** split data by time and tenant so the database works on smaller pieces.
- **Avoid hot row contention:** do not update the same account row from every transaction. Use event writes instead.


## How to do it
1. Build a main transaction table for append-only inserts.
2. Partition it by date, and optionally by tenant or tenant bucket.
3. Use a simple sequential key like `BIGSERIAL`.
4. Add only the smallest indexes needed for your common filters.
5. Keep tenant metadata in separate lookup tables, not inside every transaction row.
6. Avoid foreign keys on the hot insert table if they would make inserts slower.

## Example
```sql
CREATE TABLE transaction_events (
  transaction_id BIGSERIAL PRIMARY KEY,
  tenant_id UUID NOT NULL,
  account_id UUID NOT NULL,
  amount NUMERIC(18,4) NOT NULL,
  currency CHAR(3) NOT NULL,
  transaction_ts TIMESTAMPTZ NOT NULL DEFAULT now(),
  transaction_type TEXT NOT NULL,
  metadata JSONB,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
) PARTITION BY RANGE (transaction_ts);

CREATE TABLE transaction_events_2026_07 PARTITION OF transaction_events
  FOR VALUES FROM ('2026-07-01') TO ('2026-08-01');

CREATE TABLE transaction_events_2026_08 PARTITION OF transaction_events
  FOR VALUES FROM ('2026-08-01') TO ('2026-09-01');

CREATE INDEX ON transaction_events (tenant_id, transaction_ts);
CREATE INDEX ON transaction_events (account_id, transaction_ts);
CREATE INDEX ON transaction_events (transaction_ts) USING BRIN;
```

## Additional details
- **Tenant isolation:** If you have a few large tenants, consider additional partitioning or even separate tables for the biggest tenants.
- **Write locality:** `BIGSERIAL` is good because new inserts go to the right end of the table and index. That reduces page splits.
- **BRIN indexes:** they are cheap and great for time-range queries like "last 30 days". They do not help exact lookups, but they keep index cost low.
- **Partial indexes:** consider partial indexes for rare, important cases such as failed transactions or high-risk events.
- **Event-based balance calculations:** instead of updating account balances on every insert, use background workers or summary tables to compute balances later.
- **Batch inserts:** if possible, insert multiple rows at once. Small batches reduce overhead compared to one row at a time.
- **Autovacuum:** keep autovacuum tuned for this table, because high insert rates can create many dead row versions in partitions.
- **No locking on write path:** avoid `SELECT FOR UPDATE` or `UPDATE` on a hot table unless it is absolutely necessary.

## Why this helps
- `BIGSERIAL` keeps new inserts sequential and reduces random index writes.
- Partitioning keeps the active part of the table smaller, so vacuum and queries are cheaper.
- A BRIN index on the timestamp is small and helps time-range scans without heavy maintenance.
- Small, useful indexes keep insert cost low and prevent the write path from slowing down.
- Separating tenant metadata avoids adding large, repeated values to every row.

## Trade-offs
- **Good:**
  - Faster inserts.
  - Less lock contention between tenants.
  - Easier cleanup of old data.
  - Better insert throughput for high-volume workloads.
- **Not so good:**
  - Partition management takes more work.
  - Cross-partition queries can be harder.
  - More careful index planning is needed.
  - Background or summary processing may be required for some reads.

## References
- PostgreSQL partitioning documentation
- PostgreSQL BRIN index documentation
- PostgreSQL performance tuning for insert-heavy workloads
