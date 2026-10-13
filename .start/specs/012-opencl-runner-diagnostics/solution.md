# Solution: OpenCL Runner Diagnostics

## Approach

`RunnerDiagnosticCollector` already keeps a stderr tail and emits a diagnostic per line. Add three known variants and match them before the unknown fallback. The names come from tinygrad's `check()` and `CLCompiler.compile` in version 0.14.

Known diagnostics are the ones included in the shutdown `ErrorChunk`. These variants join that union, so a classified OpenCL line is reported when the runner stops.

## Files

- `src/exo/worker/runner/diagnostics.py` — variants and matchers.
- `src/exo/worker/tests/unittests/test_runner/test_diagnostics.py` — the five acceptance cases.
