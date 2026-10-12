---
unit: br1
feature: Backend Registry
priority: P2
---
# Unregistered backend combination fails clearly, not silently

## Scenario
Force a runner to start with a bound instance whose detected `Backend` has no registered builder (e.g. via a test harness that constructs a `BoundInstance` with an unrecognized/unsupported backend value) and observe the runner process's startup behavior.

## Expected
The runner process exits with a clear, typed error identifying the unsupported backend, surfaced through the existing `RunnerTerminationError` mechanism, rather than hanging indefinitely or raising an unrelated `AttributeError`/`KeyError` deep in unrelated code.
