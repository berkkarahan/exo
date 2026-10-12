---
unit: wc1
feature: Windows Tensor/Array Abstraction (Weight Conversion)
priority: P0
---
# Supported architecture model instance becomes ready on a single Windows node

## Scenario
On a Windows machine running exo, create a single-node instance for a Must-Have-architecture model (a Llama-family dense text model, e.g. `mlx-community/Llama-3.2-1B-Instruct-4bit`) via `POST /instance`, then poll `curl -N "http://localhost:52415/instance/await?model_id=<model_id>"`.

## Expected
The await stream eventually emits a message with `"type": "ready"` and the matching instance.
No error is reported during model loading.
A subsequent `curl -X POST http://localhost:52415/v1/chat/completions` against this instance returns generated tokens.
