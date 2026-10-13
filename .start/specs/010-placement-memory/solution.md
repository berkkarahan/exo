# Solution: 010-placement-memory

## Approach

`shard_placement_bytes` is a pure function of a model card and a layer count.

- Weight bytes are `storage_size * layer_count // n_layers`.
- Head dimension is `hidden_size // num_attention_heads` when that division is exact.
- KV bytes are `2 * num_key_value_heads * head_dimension * context_length * layer_count * 2` when the head dimension, key-value heads, and context length are all present. The leading 2 is the key tensor and the value tensor. The trailing 2 is float16.
- When the KV term is non-zero, temporary bytes are `weight_bytes // 8`.

`memory_after_reservations` takes each node's capacity as the larger of `ram_total` and `ram_available`. The placement ceiling is that capacity minus the budgets of instances already on the node, keyed by `node_to_runner` and floored at zero. Available bytes are the smaller of the reported free sample and that ceiling. `place_instance` uses the adjusted map, and the full-model budget, only when `instance_meta` is Tinygrad. Deleting an instance removes it from `state.instances`, so the next placement no longer reserves it.

## Error handling

The budget functions do not raise. Missing attention metadata yields a weight-only budget. `place_instance` still raises `ValueError` with "No cycles found with sufficient memory" when the reserved node cannot hold the new model. The master already surfaces that failure on the place command.
