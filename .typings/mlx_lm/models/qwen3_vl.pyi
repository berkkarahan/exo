import mlx.core as mx
import mlx.nn as nn

from . import qwen3
from .cache import KVCache

class Model(nn.Module):
    model_type: str
    language_model: qwen3.Model
    def __call__(
        self,
        inputs: mx.array,
        cache: list[KVCache] | None = None,
        input_embeddings: mx.array | None = None,
    ) -> mx.array: ...
    @property
    def layers(self) -> list[qwen3.TransformerBlock]: ...
