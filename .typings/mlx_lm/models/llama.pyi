from dataclasses import dataclass

import mlx.core as mx
import mlx.nn as nn

from .base import BaseModelArgs
from .cache import KVCache, RotatingKVCache

@dataclass
class ModelArgs(BaseModelArgs):
    model_type: str
    hidden_size: int
    num_hidden_layers: int
    intermediate_size: int
    num_attention_heads: int
    rms_norm_eps: float
    vocab_size: int
    head_dim: int | None = None
    max_position_embeddings: int | None = None
    num_key_value_heads: int | None = None
    attention_bias: bool = False
    mlp_bias: bool = False
    rope_theta: float = 10000
    rope_traditional: bool = False
    rope_scaling: dict[str, float | str] | None = None
    tie_word_embeddings: bool = True
    layer_types: list[str] | None = None
    sliding_window: int | None = None

class Attention(nn.Module):
    n_heads: int
    n_kv_heads: int | None
    head_dim: int
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
    input_layernorm: nn.RMSNorm
    post_attention_layernorm: nn.RMSNorm

class LlamaModel(nn.Module):
    args: ModelArgs
    embed_tokens: nn.Embedding
    layers: list[TransformerBlock]
    norm: nn.RMSNorm

class Model(nn.Module):
    args: ModelArgs
    model_type: str
    model: LlamaModel
    lm_head: nn.Linear
    def __init__(self, args: ModelArgs) -> None: ...
    def __call__(
        self,
        inputs: mx.array,
        cache: list[KVCache | RotatingKVCache] | None = None,
        input_embeddings: mx.array | None = None,
    ) -> mx.array: ...
    @property
    def layers(self) -> list[TransformerBlock]: ...
    def make_cache(self) -> list[KVCache | RotatingKVCache]: ...
