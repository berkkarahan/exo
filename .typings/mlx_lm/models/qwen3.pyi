from dataclasses import dataclass

import mlx.core as mx
import mlx.nn as nn

from .base import BaseModelArgs
from .cache import KVCache

@dataclass
class ModelArgs(BaseModelArgs):
    model_type: str
    hidden_size: int
    num_hidden_layers: int
    intermediate_size: int
    num_attention_heads: int
    rms_norm_eps: float
    vocab_size: int
    num_key_value_heads: int
    max_position_embeddings: int
    rope_theta: float
    head_dim: int
    tie_word_embeddings: bool
    rope_scaling: dict[str, float | str] | None = None

class Attention(nn.Module):
    n_heads: int
    n_kv_heads: int
    q_proj: nn.Linear
    k_proj: nn.Linear
    v_proj: nn.Linear
    o_proj: nn.Linear
    q_norm: nn.RMSNorm
    k_norm: nn.RMSNorm

class MLP(nn.Module):
    gate_proj: nn.Linear
    down_proj: nn.Linear
    up_proj: nn.Linear

class TransformerBlock(nn.Module):
    self_attn: Attention
    mlp: MLP

class Qwen3Model(nn.Module):
    embed_tokens: nn.Embedding
    layers: list[TransformerBlock]
    norm: nn.RMSNorm

class Model(nn.Module):
    args: ModelArgs
    model_type: str
    model: Qwen3Model
    lm_head: nn.Linear
    def __init__(self, args: ModelArgs) -> None: ...
    def __call__(
        self,
        inputs: mx.array,
        cache: list[KVCache] | None = None,
        input_embeddings: mx.array | None = None,
    ) -> mx.array: ...
    @property
    def layers(self) -> list[TransformerBlock]: ...
