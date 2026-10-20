# Portable backend typing

The stubs here allow the full project to be type-checked without installing
every optional inference runtime. They are never imported at runtime.

- The MLX-LM model and DeepSeek chat-template declarations added for Windows
  were checked against the fork revision
  `6a3df6cd6b00a347ee40f12d97a182aaf86ea599` in `uv.lock`. They describe the
  model attributes and entry points used by exo, not the complete upstream API.
- `exo_rs` includes both networking and the Unix-only PID-file API so checking
  Unix code does not depend on which OS generated `rust/exo_rs/exo_rs.pyi`.
  Keep it aligned with `rust/exo_rs/src/networking.rs` and `pidfile.rs`.
- `onnxruntime_genai.models.builder` describes the conversion entry point used
  by `exo.worker.engines.onnx.convert`; the native runtime stays optional.
- Pillow is a development dependency because image types appear in both exo
  and the image-model stubs.

`reportMissingModuleSource` is disabled for stub-only runtimes. Missing imports,
unknown types, `Any`, invalid casts, and unnecessary ignores remain checked.
`pythonPlatform = "Darwin"` deliberately also checks the Unix branches on Windows.

Run `uv run --no-sync basedpyright` after changing the stubs. The regression tests
in `src/wexo/tests/test_optional_backend_typing.py` check valid and invalid API
usage without loading native runtimes.
