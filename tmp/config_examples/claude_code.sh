#!/bin/bash
# Run Claude Code against a local exo cluster! (Here, GPT OSS 120B)
ANTHROPIC_BASE_URL="http://localhost:52416/" \
  ANTHROPIC_AUTH_TOKEN="dummy" \
  ANTHROPIC_MODEL="ggml-org/gpt-oss-120b-GGUF" \
  ANTHROPIC_SMALL_FAST_MODEL="ggml-org/gpt-oss-120b-GGUF" \
  CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC=1 \
  claude
