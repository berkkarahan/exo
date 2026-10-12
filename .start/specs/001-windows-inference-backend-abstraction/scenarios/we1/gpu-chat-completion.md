---
unit: we1
feature: Windows Execution Engine (ONNX Runtime GenAI Builder/Engine)
priority: P0
---
# Single-node GPU chat completion returns generated tokens

## Scenario
On a Windows machine with a supported GPU, create a single-node instance for a Must-Have-architecture model, then:
```
curl -N -X POST http://localhost:52415/v1/chat/completions \
  -H 'Content-Type: application/json' \
  -d '{"model": "<model_id>", "messages": [{"role": "user", "content": "Say hello in one word."}], "stream": true}'
```

## Expected
The response is a streamed SSE sequence of chat completion chunks.
The concatenated generated text is non-empty and coherent (a real word/phrase, not garbage tokens).
The `/state` endpoint shows the node's backend as `OnnxDirectMl` or `OnnxCuda` (GPU-accelerated), not `OnnxCpu`.
