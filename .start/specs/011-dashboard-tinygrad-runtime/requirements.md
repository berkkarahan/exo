# Requirements: Dashboard Tinygrad Runtime

## User Stories

### Story: Launch a GGUF model from the dashboard on Windows

A person running exo on a Windows machine opens the dashboard, selects the curated GGUF model, and launches it. The request uses the Tinygrad runtime. The running instance is labeled Tinygrad in the dashboard.

## Acceptance Criteria

1. [x] Placement previews for a model include a Tinygrad Pipeline placement when the cluster can run it.
2. [x] The launch controls offer Tinygrad next to MLX Ring and MLX RDMA.
3. [x] Choosing Tinygrad sends a Tinygrad placement. Tensor sharding is not offered for that runtime.
4. [x] On a cluster with no MLX backend, the dashboard defaults the runtime to Tinygrad and Pipeline, including the single-node onboarding launch.
5. [x] An instance tagged `TinygradInstance` is labeled Tinygrad on the instance list. The chat sidebar and the prefill/decode list read that same tag.
6. [x] Automatic chat launch prefers a valid MLX Pipeline preview when one exists, and otherwise uses a valid Tinygrad Pipeline preview.

## Out of Scope

- Quantization picking inside the model browser.
- Diagnostics for OpenCL compile, allocation, and device-loss failures.
- Launcher stop, restart, and accelerator status.
