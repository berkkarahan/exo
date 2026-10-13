# Solution: Tinygrad Progress Deadlines

## Approach

The TCP handshake payload is a `PipelineHandshakeIdentity`. Each rank sends its identity and accepts the neighbour only when the instance, model, world size, protocol, and adjacent rank agree.

`TinygradProgressBudgets` holds the four limits. The engine reads an injected clock before and after compile, prefill, and decode. Both pipeline transports raise `TinygradProgressDeadlineError` from the receive loop when the transport budget elapses. The exception message is the line the diagnostic collector matches.

The runner already calls `step` before it submits the next queued task. `step` applies cancel-all, and `submit` drops that flag so the following task is not cancelled with the previous one.

## Files

- `src/exo/backends/tinygrad_progress.py` — budgets, the deadline exception, and the overdue check.
- `src/exo/backends/tinygrad_pipeline.py` — handshake identity and the transport deadline.
- `src/exo/backends/tinygrad_engine.py` — compile, prefill, and decode checks, and the identity passed to `connect`.
- `src/exo/worker/runner/diagnostics.py` — classify the deadline line.
- Tests beside those modules.
