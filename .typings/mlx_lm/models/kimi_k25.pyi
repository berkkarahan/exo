import mlx.core as mx
import mlx.nn as nn

from .cache import KVCache
from .deepseek_v3 import DeepseekV3DecoderLayer, DeepseekV3Model

class LanguageModel(nn.Module):
    model: DeepseekV3Model
    lm_head: nn.Linear

class Model(nn.Module):
    model_type: str
    language_model: LanguageModel
    def __call__(
        self, inputs: mx.array, cache: list[KVCache] | None = None
    ) -> mx.array: ...
    @property
    def model(self) -> DeepseekV3Model: ...
    @property
    def layers(self) -> list[DeepseekV3DecoderLayer]: ...
