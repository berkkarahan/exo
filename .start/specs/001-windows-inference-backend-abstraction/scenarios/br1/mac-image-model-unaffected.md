---
unit: br1
feature: Backend Registry
priority: P1
---
# macOS image-generation instance is unaffected by the registry refactor

## Scenario
On a macOS machine with image models enabled (`EXO_ENABLE_IMAGE_MODELS=true uv run exo`), create a single-node instance for an image-generation model and send an image generation request through the API.

## Expected
The request returns a correctly generated image, with identical behavior to before this change (registry dispatch selects `MfluxBuilder` for `is_image_model=True` exactly as the old hardcoded branch did).
