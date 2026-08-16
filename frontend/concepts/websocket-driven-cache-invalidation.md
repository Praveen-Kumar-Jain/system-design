# Question 93

How do you design a robust frontend caching layer that automatically and selectively invalidates based on incoming WebSocket events?

## Summary
**The Problem:** Polling the server to keep data fresh wastes bandwidth and still leaves gaps, while blindly trusting a client-side cache leaves the UI stale once other clients mutate shared data. Invalidating the entire cache on every change is wasteful and causes unnecessary refetches and re-renders across unrelated parts of the UI.

**The Solution:** Keep a centralized, keyed cache (React Query, RTK Query, Apollo, SWR) as the client-side source of truth, and drive invalidation from structured server-pushed WebSocket events that identify exactly which entities changed — invalidating or patching only the matching cache keys, with the server remaining the ultimate source of truth.

## Why it matters
Real-time apps like Slack, Notion, or TradingView need both low network overhead and up-to-date UI. A cache with no invalidation strategy goes stale; a cache invalidated wholesale on every event causes redundant refetches, wasted bandwidth, and flicker in components that didn't actually change. Selective invalidation, driven by well-defined event types and stable query keys, gets both correctness and performance.

## Key Concepts
- **Cache keys:** predictable, hierarchical keys (`["project", id]`, `["tasks", projectId]`) that let a single event target exactly the affected query.
- **Selective invalidation:** only the queries named by the event refetch; everything else stays cached untouched.
- **Invalidate-and-refetch vs. direct update:** refetch when the object is complex/relational or permission-sensitive; write the payload directly into cache when it's small and self-contained (chat messages, presence, counters).
- **Optimistic updates:** apply a mutation to the cache immediately, then roll back if the server rejects it, for a faster perceived experience.
- **Event ordering and idempotency:** version numbers, timestamps, or event IDs prevent stale/duplicate events from overwriting newer cache state.

## How to do it
1. Fetch initial data over REST/GraphQL into a centralized cache with stable, structured query keys.
2. Open a WebSocket connection and define a fixed set of typed events (`PROJECT_UPDATED`, `TASK_DELETED`, `MESSAGE_SENT`, …).
3. On each event, map its payload to the query key(s) it affects — never invalidate the whole cache for a single entity change.
4. For complex/relational objects, call `invalidateQueries` on the specific key and let the cache refetch from the server.
5. For small, trustworthy, self-contained payloads, write the data directly into the cache instead of refetching.
6. Debounce/batch bursts of rapid events for the same key into a single refetch or update.
7. On reconnect after a dropped socket, ask the server "what changed since timestamp X" to backfill missed events.
8. Validate event payloads (permissions, structure, event ID for duplicates) before applying them — never trust WebSocket data blindly.

## Example
```js
socket.on("TASK_UPDATED", (event) => {
  if (isStale(event)) return; // version/timestamp check

  if (event.task) {
    // small, self-contained payload — update directly
    queryClient.setQueryData(["task", event.taskId], event.task);
  } else {
    // complex/relational — let the server be the source of truth
    queryClient.invalidateQueries({ queryKey: ["task", event.taskId] });
  }
});
```

## Additional details
- Normalize the cache (entities keyed by ID, referenced rather than duplicated) so one update touches one place instead of every list that embeds the entity.
- Reconnection handling matters as much as the live event stream — a client offline for even a few seconds can otherwise silently miss updates.
- Event versioning (`version`/`sequence` fields) protects against out-of-order delivery, which WebSockets do not guarantee across reconnects or multiple server instances.
- Keep optimistic updates reversible: store the pre-mutation cache value so a server rejection can roll back cleanly.

## Why this helps
- Network traffic drops to only the requests actually needed, instead of constant polling.
- UI updates reflect server state within the latency of a single WebSocket push.
- Unrelated components don't re-render or refetch when unrelated data changes.
- The system degrades gracefully across reconnects instead of silently going stale.

## Trade-offs
| Aspect | Impact | Description |
|---|---|---|
| Invalidate-and-refetch | Positive | Always correct, server stays source of truth, but adds an extra round trip. |
| Direct cache update | Positive | Instant, no extra request, but requires trusting the event payload's completeness. |
| Normalized cache | Positive | Single update point per entity, but adds selector/denormalization complexity. |
| Event debouncing | Mixed | Reduces refetch churn under rapid updates, but adds latency to the last event in a burst. |
| Reconnect reconciliation | Necessary cost | Prevents missed updates, but requires the server to support "changes since" queries. |

## References
- [TanStack Query: Query Invalidation](https://tanstack.com/query/latest/docs/framework/react/guides/query-invalidation)
- [MDN: WebSockets API](https://developer.mozilla.org/en-US/docs/Web/API/WebSockets_API)
- [Apollo Client: Reactive cache updates](https://www.apollographql.com/docs/react/caching/cache-interaction)
