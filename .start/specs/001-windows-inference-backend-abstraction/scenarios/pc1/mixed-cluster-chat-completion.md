---
unit: pc1
feature: Windows Distributed-Collectives Abstraction & Placement Integration
priority: P0
---
# Chat completion against a Windows+Mac pipeline instance returns correct tokens

## Scenario
Using the `OnnxPipeline` placement from `GET /instance/previews` (Windows + macOS/Linux nodes), `POST` it to `/instance`, wait for `/instance/await` to report ready, then send `POST /v1/chat/completions` with a simple prompt.

## Expected
The response streams correctly generated, coherent tokens.
No error or hang occurs during the rank-to-rank activation hand-off between the Windows and macOS/Linux ranks.
