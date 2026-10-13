import mlx.core as mx
import mlx.nn as nn

from .cache import KVCache, RotatingKVCache

class Attention(nn.Module):
    n_heads: int
    n_kv_heads: int
    q_proj: nn.Linear
    k_proj: nn.Linear
    v_proj: nn.Linear
    o_proj: nn.Linear

class MLP(nn.Module):
    gate_proj: nn.Linear
    down_proj: nn.Linear
    up_proj: nn.Linear

class TransformerBlock(nn.Module):
    self_attn: Attention
    mlp: MLP

class LanguageModel(nn.Module):
    embed_tokens: nn.Embedding
    layers: list[TransformerBlock]
    norm: nn.RMSNorm

class Model(nn.Module):
    model_type: str
    model: LanguageModel
    lm_head: nn.Linear
    def __call__(
        self,
        inputs: mx.array,
        cache: list[KVCache | RotatingKVCache] | None = None,
        input_embeddings: mx.array | None = None,
    ) -> mx.array: ...
    @property
    def layers(self) -> list[TransformerBlock]: ...
