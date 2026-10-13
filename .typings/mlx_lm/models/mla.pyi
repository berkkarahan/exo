import mlx.core as mx
import mlx.nn as nn

class MultiLinear(nn.Module):
    weight: mx.array
    def __init__(self, input_dims: int, output_dims: int, num_heads: int) -> None: ...
    def __call__(self, x: mx.array, transpose: bool = True) -> mx.array: ...
