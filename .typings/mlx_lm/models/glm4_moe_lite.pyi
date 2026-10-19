import mlx.core as mx
import mlx.nn as nn

from .cache import KVCache
from .mla import MultiLinear
from .switch_layers import SwitchGLU

class Glm4MoeLiteAttention(nn.Module):
    num_heads: int
    q_lora_rank: int
    q_proj: nn.Linear
    q_b_proj: nn.Linear
    o_proj: nn.Linear
    embed_q: MultiLinear
    unembed_out: MultiLinear

class Glm4MoeLiteMLP(nn.Module):
    gate_proj: nn.Linear
    up_proj: nn.Linear
    down_proj: nn.Linear

class MoEGate(nn.Module):
    weight: mx.array
    e_score_correction_bias: mx.array

class Glm4MoeLiteMoE(nn.Module):
    gate: MoEGate
    switch_mlp: SwitchGLU
    shared_experts: Glm4MoeLiteMLP
    num_experts_per_tok: int
    sharding_group: mx.distributed.Group | None
    def __call__(self, x: mx.array) -> mx.array: ...

class Glm4MoeLiteDecoderLayer(nn.Module):
    self_attn: Glm4MoeLiteAttention
    mlp: Glm4MoeLiteMLP | Glm4MoeLiteMoE

class Glm4MoeLiteModel(nn.Module):
    embed_tokens: nn.Embedding
    layers: list[Glm4MoeLiteDecoderLayer]
    norm: nn.RMSNorm

class Model(nn.Module):
    model_type: str
    model: Glm4MoeLiteModel
    lm_head: nn.Linear
    def __call__(
        self, inputs: mx.array, cache: list[KVCache] | None = None
    ) -> mx.array: ...
    @property
    def layers(self) -> list[Glm4MoeLiteDecoderLayer]: ...
