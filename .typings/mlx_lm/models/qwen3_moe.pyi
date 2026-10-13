import mlx.core as mx
import mlx.nn as nn

from .cache import KVCache
from .switch_layers import SwitchGLU

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

class Qwen3MoeSparseMoeBlock(nn.Module):
    gate: nn.Linear
    switch_mlp: SwitchGLU
    num_experts: int
    top_k: int
    norm_topk_prob: bool
    def __call__(self, x: mx.array) -> mx.array: ...

class Qwen3MoeDecoderLayer(nn.Module):
    self_attn: Attention
    mlp: MLP | Qwen3MoeSparseMoeBlock

class Qwen3MoeModel(nn.Module):
    embed_tokens: nn.Embedding
    layers: list[Qwen3MoeDecoderLayer]
    norm: nn.RMSNorm

class Model(nn.Module):
    model_type: str
    model: Qwen3MoeModel
    lm_head: nn.Linear
    def __call__(
        self,
        inputs: mx.array,
        cache: list[KVCache] | None = None,
        input_embeddings: mx.array | None = None,
    ) -> mx.array: ...
    @property
    def layers(self) -> list[Qwen3MoeDecoderLayer]: ...
