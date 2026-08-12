# Question 7

How do you design an Express middleware pipeline to guarantee atomic context propagation across asynchronous execution hooks?

## Summary
**The Problem:** Request IDs, tenant identity, trace metadata, and transaction state can be lost or mixed when control crosses callbacks and Promise chains. Storing them in global variables creates cross-request data leakage.

**The Solution:** Create one immutable request context at the outermost middleware boundary and run the complete downstream chain inside `AsyncLocalStorage.run()`. Read context through a small accessor, prevent mutable shared state, and explicitly bridge libraries or event emitters that break asynchronous context.

## Why it matters
Concurrent requests interleave on the event loop. Correct context propagation is required for trustworthy logs, tracing, authorization, auditing, and tenant isolation. “Atomic” here means each asynchronous execution chain observes one request's context for its entire lifetime; it does not mean a database transaction is automatically created.

## Key Concepts
- **`AsyncLocalStorage`:** stores data associated with an asynchronous execution chain.
- **Boundary initialization:** context must be established before authentication, logging, routing, or other asynchronous work.
- **Immutable identity:** identifiers should not be mutated after middleware begins.
- **`AsyncResource`:** bridges custom callback/event APIs that do not preserve context automatically.
- **Explicit transaction scope:** a database transaction object may be stored in context, but commit and rollback still require structured control flow.

## How to do it
1. Instantiate one application-wide `AsyncLocalStorage`, not one instance per request.
2. Generate or validate the request ID at the first middleware.
3. Call `storage.run(context, () => next())`; do not call `next()` outside the callback.
4. Enrich context by replacing it with a new immutable object or by storing mutable operational state in carefully owned nested objects.
5. Expose `getContext()` that throws when called outside a request, making propagation failures visible.
6. Pass context explicitly across queues, process boundaries, and detached background jobs; AsyncLocalStorage cannot cross them.
7. Wrap custom event/callback integrations with `AsyncResource` when tests show lost context.
8. Verify propagation with many overlapping requests and delayed callbacks.

## Flow
```mermaid
flowchart LR
    A[Incoming request] --> B[Create immutable base context]
    B --> C[AsyncLocalStorage.run]
    C --> D[Authentication]
    D --> E[Route handler]
    E --> F[Database / HTTP calls]
    F --> G[Logs and traces read same context]
```

## Example
```js
import { AsyncLocalStorage } from 'node:async_hooks';
import { randomUUID } from 'node:crypto';

const requestContext = new AsyncLocalStorage();

export function contextMiddleware(req, res, next) {
  const context = Object.freeze({
    requestId: validRequestId(req.get('x-request-id')) ?? randomUUID(),
    startedAt: Date.now(),
  });

  requestContext.run(context, () => next());
}

export function getContext() {
  const context = requestContext.getStore();
  if (!context) throw new Error('No active request context');
  return context;
}

app.use(contextMiddleware); // Must be mounted before async middleware.

app.use(async (req, _res, next) => {
  try {
    const user = await authenticate(req);
    const current = getContext();

    // enterWith changes the context for the current synchronous execution.
    // Prefer an additional run boundary when practical to limit its scope.
    requestContext.enterWith(Object.freeze({
      ...current,
      userId: user.id,
      tenantId: user.tenantId,
    }));
    next();
  } catch (error) {
    next(error);
  }
});

app.get('/accounts/:id', async (req, res) => {
  logger.info(getContext(), 'loading account');
  const account = await repository.find(req.params.id);
  res.json(account);
});
```

For strict control, authentication can run the remaining route pipeline inside a nested `run()` instead of using `enterWith()`. Also attach the request ID directly to logs at ingress as a fallback for integrations that execute outside the context.

## Additional details
- Do not use `async_hooks.createHook()` directly unless `AsyncLocalStorage` cannot solve the problem; it is lower-level and easier to misuse.
- Context does not propagate across Worker Threads, child processes, message queues, or HTTP calls. Serialize approved fields into the message or trace headers.
- Avoid storing entire `req`/`res` objects or large payloads in the context because they extend retention and complicate testing.
- Do not call `disable()` per request; it disables the storage instance globally.
- Keep authorization decisions explicit. Context transports identity but does not prove it is authorized.

## Why this helps
- Concurrent requests cannot overwrite a process-global correlation ID.
- Deep services can produce correlated logs without adding context parameters to every function.
- One ingress boundary makes missing context detectable and testable.
- Immutable identifiers reduce accidental tenant or trace mutation.

## Trade-offs
| Aspect | Impact | Description |
|---|---|---|
| AsyncLocalStorage | Positive | Automatic in-process propagation with modest runtime overhead. |
| Implicit access | Mixed | Cleaner signatures but dependencies become less visible. |
| Immutable context | Positive | Safer identity, but enrichment requires a new scoped context. |
| AsyncResource bridging | Cost | Handles unusual integrations but adds low-level complexity. |
| Explicit cross-process headers | Necessary | More plumbing, but process-local context cannot cross boundaries itself. |

## References
- [Node.js Async Context documentation](https://nodejs.org/api/async_context.html)
- [Node.js Async Hooks documentation](https://nodejs.org/api/async_hooks.html)
- [Express middleware guide](https://expressjs.com/en/guide/using-middleware.html)

