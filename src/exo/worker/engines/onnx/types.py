"""Shared types for ONNX Runtime GenAI-related functionality.

Thin typed wrapper over ``onnxruntime_genai``'s ``Model``/``Generator``
classes, which are not strongly typed. This module never imports
``onnxruntime_genai`` at module scope so it can be imported cleanly on any
platform (the package is Windows-only and heavy).
"""

from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    import numpy as np


class GeneratorParams(Protocol):
    def set_search_options(self, **options: float | int | bool) -> None: ...
    def try_use_cuda_graph_with_max_batch_size(self, max_batch_size: int) -> None: ...


class Generator(Protocol):
    def append_tokens(self, tokens: "np.ndarray[tuple[int, ...], np.dtype[np.int64]]") -> None: ...
    def generate_next_token(self) -> None: ...
    def is_done(self) -> bool: ...
    def get_next_tokens(self) -> "np.ndarray[tuple[int, ...], np.dtype[np.int64]]": ...


class Model(Protocol):
    def create_generator_params(self) -> GeneratorParams: ...
    def create_generator(self, params: GeneratorParams) -> Generator: ...
