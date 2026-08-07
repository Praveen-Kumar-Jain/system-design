# Question 4

What is your strategy for optimizing PostgreSQL query execution plans when the query planner consistently chooses nested loops over hash joins for large dataset aggregations?

## Summary
**The Problem:** When PostgreSQL chooses nested loop joins for large dataset aggregations, the query can become very slow.
**The Solution:** Improve planner statistics, give PostgreSQL enough memory, and shape the query and indexes so a hash join becomes the better choice.

## Why it matters
Nested loops are fine for small or highly selective joins, but they are not good for large datasets. When the inner table is scanned many times, the query can become much slower than a hash join.

## Key Concepts
- **Planner statistics:** PostgreSQL chooses join types using table and index statistics.
- **Hash join memory:** `work_mem` must be large enough for the hash table to stay in RAM.
- **Early filtering:** applying filters before the join reduces the rows that need to be joined.
- **Deterministic indexes:** proper indexes on join keys and filters help the planner compare plans accurately.

## How to do it
1. Run `ANALYZE` on the tables and indexes so the planner has accurate row counts and selectivity estimates.
2. Raise `work_mem` enough for hash joins to build hash tables in memory.
3. Add or improve indexes on the join keys and the columns used in filter conditions.
4. Push filters down before the join so the planner works on smaller inputs.
5. Use `SET enable_nestloop = off;` to test whether a hash join is faster.
6. Review estimated row counts and use `CREATE STATISTICS` for correlated columns if needed.

## Example
```sql
EXPLAIN ANALYZE
SELECT c.customer_id,
       SUM(o.amount) AS total
FROM customers c
JOIN orders o ON c.customer_id = o.customer_id
WHERE c.active = true
  AND o.order_date >= '2026-01-01'
GROUP BY c.customer_id;
```

If this query uses nested loops and is slow:
- run `ANALYZE customers; ANALYZE orders;`
- set `work_mem = '128MB'` for the session
- ensure `orders.customer_id` is indexed
- compare plans with `SET enable_nestloop = off;`
- use `EXPLAIN (ANALYZE, BUFFERS)` to verify where time is spent
- check whether the hash join is spilling to disk

## Additional details
- Nested loops join each row from one side to matching rows on the other side, so they are best when one input is small.
- Hash joins build a hash table from one input and probe it with the other, which usually performs better for large joins when memory is available.
- The planner relies on statistics, so stale or inaccurate stats can make it choose a bad plan.
- If estimated row counts are wrong, PostgreSQL may choose nested loops even when a hash join would be faster.
- Filtering early reduces the number of rows that enter the join.
- `work_mem` is per operation, so increasing it helps only if the server has enough memory for concurrent queries.
- If join keys are skewed or correlated, `CREATE STATISTICS` can improve planner estimates.
- `SET enable_mergejoin = off;` and `SET enable_hashjoin = off;` are useful for testing, but do not use them as a permanent fix.

## Why this helps
- Better statistics make the planner choose the right join type.
- More memory lets hash joins stay in RAM and avoid disk I/O.
- Better indexes and earlier filtering reduce the amount of data the query must process.
- Testing alternative plans confirms whether the current nested loop choice is the real problem.

## Trade-offs
- **Higher `work_mem`:** improves performance, but uses more RAM per query.
- **Disabling nested loops:** useful for testing, but not a long-term solution.
- **More indexes:** speed joins and filters but increase write cost and storage.
- **Frequent ANALYZE:** helps the planner, but adds maintenance overhead.
- **Planner tuning:** may require review as data and query shapes change.

## Why this helps
- Better statistics make the planner choose the right join type.
- More memory lets hash joins stay in RAM and avoid disk I/O.
- Better indexes and earlier filtering reduce the amount of data the query must process.
- Testing alternative plans confirms whether the current nested loop choice is the real problem.

## Trade-offs
- **Higher `work_mem`:** improves performance, but uses more RAM per query.
- **Disabling nested loops:** useful for testing, but not a long-term solution.
- **More indexes:** speed joins and filters but increase write cost and storage.
- **Frequent ANALYZE:** helps the planner, but adds maintenance overhead.
- **Planner tuning:** may require review as data and query shapes change.

## References
- PostgreSQL documentation: Query Planner and Optimizer
- PostgreSQL documentation: Join Types
- PostgreSQL configuration: work_mem
