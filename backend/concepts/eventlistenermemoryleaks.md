# Question 4

What strategies prevent memory leaks caused by unhandled event listener allocations in high-throughput Express servers?

## Summary
**The Problem:** Request-scoped listeners attached to long-lived emitters can survive after the response ends. They retain request objects, closures, buffers, and user data, so memory grows with traffic and duplicate callbacks accumulate.

**The Solution:** Prefer request lifecycle events already exposed by `req` and `res`, use `.once()` when only one notification is needed, explicitly remove listeners in a single cleanup path, bind cancellation with `AbortSignal`, and monitor listener and heap growth.

## Why it matters
The garbage collector cannot reclaim an object while an emitter still references its listener closure. Raising `setMaxListeners()` only hides the warning; it does not remove the references or fix the leak.

## Key Concepts
- **Listener ownership:** the component that registers a listener must define when it is removed.
- **Emitter lifetime:** attaching per-request callbacks to process-wide emitters is especially risky.
- **Idempotent cleanup:** completion, abort, timeout, and error paths may race, so cleanup must be safe to call repeatedly.
- **One-shot listeners:** `.once()` automatically unregisters after the first event.
- **Cancellation scope:** an `AbortController` can tie downstream work to the request lifetime.

## How to do it
1. Never add per-request listeners to `process`, singleton clients, or shared buses without removing them.
2. Use `.once()` for response completion, socket closure, and one-time acknowledgements.
3. Register all cleanup logic in one function and call it from `finish`, `close`, timeout, and error paths.
4. Abort database, HTTP, stream, and queue work when the client disconnects where those APIs support `AbortSignal`.
5. Avoid closures that capture the full `req`, `res`, uploaded buffers, or large domain objects unnecessarily.
6. Do not suppress `MaxListenersExceededWarning` globally. Investigate it and record warning stacks in staging.
7. Compare heap snapshots and listener counts under repeated load, including aborted requests.

## Example
```js
app.get('/report/:id', async (req, res, next) => {
  const controller = new AbortController();
  let cleaned = false;

  const cleanup = () => {
    if (cleaned) return;
    cleaned = true;
    controller.abort(new Error('Request completed or disconnected'));
    res.off('finish', cleanup);
    res.off('close', cleanup);
  };

  res.once('finish', cleanup);
  res.once('close', cleanup);

  try {
    const report = await loadReport(req.params.id, {
      signal: controller.signal,
    });

    if (!res.headersSent) res.json(report);
  } catch (error) {
    if (!controller.signal.aborted) next(error);
  } finally {
    cleanup();
  }
});
```

For a shared emitter, retain the exact callback reference so it can be removed:

```js
function waitForJob(jobBus, jobId, signal) {
  return new Promise((resolve, reject) => {
    const onResult = (result) => {
      if (result.jobId !== jobId) return;
      dispose();
      resolve(result);
    };

    const onAbort = () => {
      dispose();
      reject(signal.reason);
    };

    const dispose = () => {
      jobBus.off('result', onResult);
      signal.removeEventListener('abort', onAbort);
    };

    jobBus.on('result', onResult);
    signal.addEventListener('abort', onAbort, { once: true });
  });
}
```

## Additional details
- `finish` means the response was handed off for sending; `close` can indicate premature connection termination. Handle both.
- Prefer one shared listener that dispatches by correlation ID over thousands of listeners on one singleton emitter.
- Ensure WebSocket, SSE, database subscription, and message-broker listeners are removed when their owning connection closes.
- Use `events.getEventListeners()` and `emitter.listenerCount()` in diagnostics, not on every hot-path request.
- Heap growth alone is not proof of a leak; inspect retained objects after forcing realistic idle periods in tests.

## Why this helps
- Request data becomes collectible immediately after its lifecycle ends.
- Abandoned work stops consuming CPU, sockets, and memory.
- Listener warnings remain useful signals instead of being hidden.
- Central cleanup handles success and failure consistently.

## Trade-offs
| Aspect | Impact | Description |
|---|---|---|
| Explicit cleanup | Positive | Precise ownership, but every terminal path must invoke it. |
| `.once()` | Positive | Automatic removal, but unsuitable for repeated events. |
| Abort signals | Positive | Compose cancellation across APIs, but library support varies. |
| Shared dispatcher | Mixed | Reduces listener count but adds routing and correlation logic. |
| Heap snapshots | Diagnostic cost | Highly useful, but snapshots can pause and consume memory. |

## References
- [Node.js Events documentation](https://nodejs.org/api/events.html)
- [Node.js HTTP response events](https://nodejs.org/api/http.html#class-httpserverresponse)
- [Express production best practices](https://expressjs.com/en/advanced/best-practice-performance.html)
