# Question 5

How do you implement efficient keyset pagination (cursor-based) in PostgreSQL for a complex financial grid sorted by non-unique, nullable columns?

## Summary
**The Problem:** Offset pagination gets slow and inconsistent for deep pages, especially with non-unique or nullable sort columns.
**The Solution:** Use keyset pagination with a stable cursor based on sort columns and a unique tie-breaker. Handle NULLs explicitly and support the ordering with a matching index.

## Why it matters
Offset pagination becomes slow as the page number grows because PostgreSQL has to skip many rows. In financial dashboards with sorting on non-unique or nullable columns, a cursor-based approach keeps page queries quick and avoids repeated work.

## Key Concepts
- **Cursor-based paging:** uses the last row values from the current page to fetch the next page.
- **Deterministic ordering:** include a unique tie-breaker like `transaction_id` to prevent duplicates or missed rows.
- **Tuple comparison:** compare the full sort key tuple to the cursor tuple for correct ordering.
- **NULL handling:** use explicit `NULLS FIRST` or `NULLS LAST` behavior to keep order stable.

## How to do it
1. Choose a stable sort key list that matches the UI order, such as `(created_at DESC, amount DESC, transaction_id DESC)`.
2. Make sure the key list is deterministic by including a unique column like `transaction_id` as the final tie-breaker.
3. Encode the cursor values from the last row on the current page.
4. Use a WHERE clause that compares the sort key tuple to the cursor tuple.
5. Treat NULLs consistently by using `NULLS FIRST` or `NULLS LAST` in the ORDER BY and in the tuple comparison.
6. Build an index that supports the sort order, for example a composite B-tree index on the key columns.

## Example
```sql
CREATE INDEX idx_transactions_pagination
  ON transactions (created_at DESC, amount DESC, transaction_id DESC);

-- Assume the cursor is the last row values from the previous page:
-- last_created_at, last_amount, last_transaction_id

SELECT *
FROM transactions
WHERE (created_at, amount, transaction_id) <
      (:last_created_at, :last_amount, :last_transaction_id)
ORDER BY created_at DESC, amount DESC, transaction_id DESC
LIMIT 50;
```

If some values are NULL, use an expression to normalize them:

```sql
SELECT *
FROM transactions
WHERE (
  created_at, 
  amount, 
  COALESCE(transaction_id, 0)
) < (
  :last_created_at,
  :last_amount,
  COALESCE(:last_transaction_id, 0)
)
ORDER BY created_at DESC, amount DESC, transaction_id DESC
LIMIT 50;
```

## Additional details
- Keep the cursor small and easy to encode, such as a JSON or base64 string of the last row values.
- Include the unique `transaction_id` so pages do not repeat or skip rows when the sort columns are identical.
- If the sort includes nullable columns, explicitly use `NULLS FIRST` or `NULLS LAST` in both `ORDER BY` and comparisons.
- Avoid `OFFSET` on large pages because it still scans skipped rows internally.
- Use the same index order as the sort order for the best performance.
- For descending sorts, tuple comparisons work naturally when the index matches the direction.
- If you have multiple sort columns, compare the tuple as a whole rather than several separate conditions.
- In some cases, it is helpful to calculate a stable sort key in the query (for example `COALESCE(amount, -1)`) and use that in the cursor.

## Why this helps
- Cursor-based pagination avoids scanning all skipped rows and keeps queries fast.
- A deterministic sort order with a unique tie-breaker prevents duplicate or missing rows across pages.
- Composite indexes on the sort key let PostgreSQL jump directly to the next page position.
- Handling NULL values explicitly ensures the grid order stays consistent.

## Trade-offs
- **Good:** cursor pagination is much faster for deep paging than offset-based queries.
- **Good:** it avoids repeated row skips and makes page queries stable.
- **Not so good:** cursor values can be harder to encode and manage in the client.
- **Not so good:** jumping directly to an arbitrary page number is not easy with keyset pagination.
- **Not so good:** complex sort orders may require more careful cursor construction and index design.

## References
- PostgreSQL documentation: Indexing and query planning
- PostgreSQL documentation: ORDER BY and NULLS FIRST/LAST
- Keyset pagination best practices
