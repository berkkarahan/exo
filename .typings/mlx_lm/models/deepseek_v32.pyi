import mlx.core as mx
import mlx.nn as nn

from .cache import CacheList
from .mla import MultiLinear
from .switch_layers import SwitchGLU

class DeepseekV32Attention(nn.Module):
    num_heads: int
    q_lora_rank: int
    q_proj: nn.Linear
    q_b_proj: nn.Linear
    o_proj: nn.Linear
    embed_q: MultiLinear
    unembed_out: MultiLinear

class DeepseekV32MLP(nn.Module):
    gate_proj: nn.Linear
    up_proj: nn.Linear
    down_proj: nn.Linear

class MoEGate(nn.Module):
    weight: mx.array
    e_score_correction_bias: mx.array

class DeepseekV32MoE(nn.Module):
    gate: MoEGate
    switch_mlp: SwitchGLU
    shared_experts: DeepseekV32MLP
    num_experts_per_tok: int
    sharding_group: mx.distributed.Group | None
    def __call__(self, x: mx.array) -> mx.array: ...

class DeepseekV32DecoderLayer(nn.Module):
    self_attn: DeepseekV32Attention
    mlp: DeepseekV32MLP | DeepseekV32MoE

class DeepseekV32Model(nn.Module):
    embed_tokens: nn.Embedding
    layers: list[DeepseekV32DecoderLayer]
    norm: nn.RMSNorm
    start_idx: int
    end_idx: int
    num_layers: int

class Model(nn.Module):
    model_type: str
    model: DeepseekV32Model
    lm_head: nn.Linear
    def __call__(
        self, inputs: mx.array, cache: list[CacheList] | None = None
    ) -> mx.array: ...
    @property
    def layers(self) -> list[DeepseekV32DecoderLayer]: ...
    def make_cache(self) -> list[CacheList]: ...
