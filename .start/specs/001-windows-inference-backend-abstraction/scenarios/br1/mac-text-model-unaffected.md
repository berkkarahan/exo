---
unit: br1
feature: Backend Registry
priority: P1
---
# macOS text-generation instance is unaffected by the registry refactor

## Scenario
On a macOS machine, run `uv run exo`, create a single-node instance for a text-generation model, and send a `POST /v1/chat/completions` request, exactly as documented in `README.md`'s "Using the API" section.

## Expected
The request returns correctly generated tokens, with identical behavior to before this change (registry dispatch selects `MlxBuilder` for this node exactly as the old hardcoded branch did).
