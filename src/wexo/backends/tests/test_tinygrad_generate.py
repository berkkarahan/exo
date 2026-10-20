from __future__ import annotations

import struct
import sys
import threading
import time
from pathlib import Path
from typing import Literal

import pytest

from wexo.backends.tinygrad_checkpoint import read_gguf_checkpoint
from wexo.backends.tinygrad_engine import TinygradEngine
from wexo.backends.tinygrad_pipeline import connect_memory_pipeline
from wexo.backends.tinygrad_progress import (
    TinygradProgressBudgets,
    TinygradProgressDeadlineError,
)
from wexo.backends.tinygrad_tokenizer import (
    GgufTokenizer,
    decode_token,
    decode_tokens,
    encode,
    encode_chat,
    format_chat_messages,
    gpt2_byte_symbols_for_text,
)
from wexo.backends.tinygrad_weights import (
    TinygradModelSupportError,
    TinygradShardRoleError,
)
from wexo.shared.models.model_cards import ModelCard, ModelId, ModelTask
from wexo.shared.types.backends import Backend
from wexo.shared.types.chunks import TokenChunk
from wexo.shared.types.common import CommandId, NodeId
from wexo.shared.types.memory import Memory
from wexo.shared.types.tasks import (
    CANCEL_ALL_TASKS,
    ImageGeneration,
    TaskId,
    TextGeneration,
)
from wexo.shared.types.text_generation import (
    InputMessage,
    InputMessageContent,
    TextGenerationTaskParams,
)
from wexo.shared.types.worker.instances import (
    BoundInstance,
    InstanceId,
    TinygradInstance,
)
from wexo.shared.types.worker.runner_response import (
    CancelledResponse,
    FinishedResponse,
)
from wexo.shared.types.worker.runners import RunnerId, ShardAssignments
from wexo.shared.types.worker.shards import PipelineShardMetadata

_HIDDEN = 16
_HEADS = 4
_KEY_VALUE_HEADS = 2
_INTERMEDIATE = 32
_HEAD_DIM = 4


def test_gpt2_merge_round_trip() -> None:
    tokenizer = _tokenizer(tokens=("a", "b", "ab"), merges=("a b",))
    assert encode(tokenizer, "ab") == (2,)
    assert decode_token(tokenizer, 2) == "ab"


def test_qwen_chat_wraps_the_user_message() -> None:
    formatted = "<|im_start|>user\nhi<|im_end|>\n<|im_start|>assistant\n"
    tokenizer = _chat_tokenizer(
        ("<|im_start|>", "<|im_end|>"),
        formatted,
        pretokenizer="qwen2",
    )
    assert format_chat_messages(tokenizer, (("user", "hi"),), None) == formatted
    assert decode_tokens(tokenizer, encode(tokenizer, formatted)) == formatted


def test_llama3_chat_wraps_the_user_message() -> None:
    formatted = (
        "<|begin_of_text|><|start_header_id|>user<|end_header_id|>\n\n"
        "hi<|eot_id|><|start_header_id|>assistant<|end_header_id|>\n\n"
    )
    tokenizer = _chat_tokenizer(
        (
            "<|begin_of_text|>",
            "<|start_header_id|>",
            "<|end_header_id|>",
            "<|eot_id|>",
        ),
        formatted,
        pretokenizer="llama-bpe",
    )
    assert format_chat_messages(tokenizer, (("user", "hi"),), None) == formatted
    assert decode_tokens(tokenizer, encode(tokenizer, formatted)) == formatted
    assert encode_chat(tokenizer, (("user", "hi"),), None)[0] == 0


def test_sentencepiece_merge_round_trip() -> None:
    tokenizer = _tokenizer(
        tokens=("<unk>", "▁", "a", "▁a"),
        merges=("▁ a",),
        model="llama",
        pretokenizer="sentencepiece",
    )
    assert encode(tokenizer, "a") == (3,)
    assert decode_token(tokenizer, 3) == " a"


def test_gguf_header_keeps_tokenizer_arrays(tmp_path: Path) -> None:
    _write_gguf(
        tmp_path / "weights.gguf",
        metadata=_tokenizer_metadata(
            tokens=("a", "b", "ab"),
            merges=("a b",),
            token_types=(1, 1, 1),
            eos_token_id=1,
        ),
        tensors=[],
    )
    checkpoint = read_gguf_checkpoint(tmp_path)
    assert checkpoint.tokenizer_tokens == ("a", "b", "ab")
    assert checkpoint.tokenizer_merges == ("a b",)
    assert checkpoint.tokenizer_token_types == (1, 1, 1)
    assert checkpoint.tokenizer_token_count == 3


@pytest.mark.skipif(sys.platform != "win32", reason="OpenCL generation needs Windows")
def test_live_opencl_generation_uses_the_discrete_gpu(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    pytest.importorskip("tinygrad")
    from tinygrad.runtime.ops_cl import CLDevice

    from wexo.backends.tinygrad_opencl import (
        clear_opencl_resolution_cache,
        resolve_usable_opencl_adapter,
    )

    clear_opencl_resolution_cache()
    adapter = resolve_usable_opencl_adapter()
    if adapter is None or adapter.host_unified_memory:
        pytest.skip("no discrete OpenCL GPU")

    engine = _loaded_engine(
        tmp_path,
        monkeypatch,
        tokens=("a", "b", "c", "d"),
        eos_token_id=1,
        layer_count=1,
        include_output=True,
        device_name="CL",
    )
    loaded_shard = engine.loaded_shard
    assert loaded_shard is not None
    assert loaded_shard.layers[0].input_norm_weight.device == "CL"
    assert CLDevice("CL").device_name == adapter.device_name

    engine.submit(_text_task(max_output_tokens=1))
    results = list(engine.step())
    assert len(results) == 2
    _task_id, chunk = results[0]
    assert isinstance(chunk, TokenChunk)
    assert chunk.token_id == 0
    assert chunk.text == "a"
    assert chunk.finish_reason == "length"
    assert isinstance(results[1][1], FinishedResponse)


@pytest.mark.skipif(sys.platform != "win32", reason="OpenCL generation needs Windows")
def test_q4_k_block_realizes_on_the_pinned_opencl_device(tmp_path: Path) -> None:
    pytest.importorskip("tinygrad")
    from tinygrad.runtime.ops_cl import CLDevice

    from wexo.backends.tinygrad_checkpoint import ggml_tensor_from_file
    from wexo.backends.tinygrad_engine import assign_tinygrad_default_device
    from wexo.backends.tinygrad_opencl import (
        clear_opencl_resolution_cache,
        resolve_usable_opencl_adapter,
    )

    clear_opencl_resolution_cache()
    adapter = resolve_usable_opencl_adapter()
    if adapter is None or adapter.host_unified_memory:
        pytest.skip("no discrete OpenCL GPU")
    assign_tinygrad_default_device("CL")
    payload = tmp_path / "q4k.bin"
    payload.write_bytes(b"\x00" * 144)
    realized = ggml_tensor_from_file(payload, 0, 144, 256, 12).contiguous().realize()
    assert realized.device == "CL"
    assert CLDevice("CL").device_name == adapter.device_name
    assert realized.shape == (1, 256)
    assert realized.float().numpy().tobytes() == struct.pack("<256f", *([0.0] * 256))


def test_length_stop_emits_one_token_then_finished(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    pytest.importorskip("tinygrad")
    engine = _loaded_engine(
        tmp_path,
        monkeypatch,
        tokens=("a", "b", "c", "d"),
        eos_token_id=1,
        layer_count=1,
        include_output=True,
    )
    engine.submit(_text_task(max_output_tokens=1))
    results = list(engine.step())
    assert len(results) == 2
    _task_id, chunk = results[0]
    assert isinstance(chunk, TokenChunk)
    assert chunk.token_id == 0
    assert chunk.text == "a"
    assert chunk.finish_reason == "length"
    assert chunk.usage is not None
    assert chunk.usage.prompt_tokens == 1
    assert chunk.usage.completion_tokens == 1
    assert isinstance(results[1][1], FinishedResponse)


def test_eos_stop_emits_empty_text(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    pytest.importorskip("tinygrad")
    engine = _loaded_engine(
        tmp_path,
        monkeypatch,
        tokens=("a", "b", "c", "d"),
        eos_token_id=0,
        layer_count=1,
        include_output=True,
    )
    engine.submit(_text_task(max_output_tokens=4))
    results = list(engine.step())
    _task_id, chunk = results[0]
    assert isinstance(chunk, TokenChunk)
    assert chunk.token_id == 0
    assert chunk.text == ""
    assert chunk.finish_reason == "stop"
    assert isinstance(results[1][1], FinishedResponse)


def test_warmup_clears_the_key_value_cache(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    pytest.importorskip("tinygrad")
    engine = _loaded_engine(
        tmp_path,
        monkeypatch,
        tokens=("a", "b", "c", "d"),
        eos_token_id=1,
        layer_count=1,
        include_output=True,
    )
    engine.warmup()
    cache = engine.key_value_cache
    assert cache is not None
    assert cache.cached(0) == (None, None)


def test_partial_shard_warmup_is_rejected(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    pytest.importorskip("tinygrad")
    engine = _loaded_engine(
        tmp_path,
        monkeypatch,
        tokens=("a", "b", "c", "d"),
        eos_token_id=1,
        layer_count=2,
        include_output=False,
        end_layer=1,
    )
    with pytest.raises(TinygradShardRoleError):
        engine.warmup()


def test_cancelled_task_yields_cancelled_response(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    pytest.importorskip("tinygrad")
    engine = _loaded_engine(
        tmp_path,
        monkeypatch,
        tokens=("a", "b", "c", "d"),
        eos_token_id=1,
        layer_count=1,
        include_output=True,
    )
    task = _text_task(max_output_tokens=4)
    engine.cancel_receiver = _PendingCancellations([task.task_id])
    engine.submit(task)
    assert list(engine.step()) == [(task.task_id, CancelledResponse())]


def _require_discrete_opencl() -> None:
    pytest.importorskip("tinygrad")
    from wexo.backends.tinygrad_opencl import (
        clear_opencl_resolution_cache,
        resolve_usable_opencl_adapter,
    )

    clear_opencl_resolution_cache()
    adapter = resolve_usable_opencl_adapter()
    if adapter is None or adapter.host_unified_memory:
        pytest.skip("no discrete OpenCL GPU")


def test_request_after_cancel_all_still_generates(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _require_discrete_opencl()
    engine = _loaded_engine(
        tmp_path,
        monkeypatch,
        tokens=("a", "b", "c", "d"),
        eos_token_id=1,
        layer_count=1,
        include_output=True,
        device_name="CL",
    )
    monkeypatch.setattr(engine, "_realize_logits", _fixed_logits)
    first = _text_task(max_output_tokens=4)
    second = _text_task(max_output_tokens=1)
    engine.submit(first)
    engine.cancel_receiver = _PendingCancellations([CANCEL_ALL_TASKS])
    assert list(engine.step()) == [(first.task_id, CancelledResponse())]
    engine.submit(second)
    results = list(engine.step())
    assert results[0][0] == second.task_id
    assert isinstance(results[0][1], TokenChunk)


def test_compile_deadline_is_raised_before_warmup(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _require_discrete_opencl()
    engine = _loaded_engine(
        tmp_path,
        monkeypatch,
        tokens=("a", "b", "c", "d"),
        eos_token_id=1,
        layer_count=1,
        include_output=True,
        device_name="CL",
    )
    calls = {"count": 0}

    def logits(token_ids: object) -> list[float]:
        del token_ids
        calls["count"] += 1
        return [1.0, 0.0, 0.0, 0.0]

    monkeypatch.setattr(engine, "_realize_logits", logits)
    engine.progress_budgets = TinygradProgressBudgets(
        compile_seconds=1.0,
        prefill_seconds=120.0,
        decode_seconds=60.0,
        transport_seconds=30.0,
    )
    engine.progress_clock = _ScriptedClock((0.0, 10.0))
    with pytest.raises(TinygradProgressDeadlineError, match="compile") as caught:
        engine.warmup()
    assert caught.value.phase == "compile"
    assert calls["count"] == 0


def test_prefill_deadline_is_raised_before_the_forward(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _require_discrete_opencl()
    engine = _loaded_engine(
        tmp_path,
        monkeypatch,
        tokens=("a", "b", "c", "d"),
        eos_token_id=1,
        layer_count=1,
        include_output=True,
        device_name="CL",
    )
    calls = {"count": 0}

    def logits(token_ids: object) -> list[float]:
        del token_ids
        calls["count"] += 1
        return [1.0, 0.0, 0.0, 0.0]

    monkeypatch.setattr(engine, "_realize_logits", logits)
    engine.progress_budgets = TinygradProgressBudgets(
        compile_seconds=600.0,
        prefill_seconds=1.0,
        decode_seconds=60.0,
        transport_seconds=30.0,
    )
    engine.progress_clock = _ScriptedClock((0.0, 10.0))
    engine.submit(_text_task(max_output_tokens=1))
    with pytest.raises(TinygradProgressDeadlineError, match="prefill") as caught:
        _ = list(engine.step())
    assert caught.value.phase == "prefill"
    assert calls["count"] == 0


def test_decode_deadline_is_raised_on_the_following_step(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _require_discrete_opencl()
    engine = _loaded_engine(
        tmp_path,
        monkeypatch,
        tokens=("a", "b", "c", "d"),
        eos_token_id=1,
        layer_count=1,
        include_output=True,
        device_name="CL",
    )
    calls = {"count": 0}

    def logits(token_ids: object) -> list[float]:
        del token_ids
        calls["count"] += 1
        return [1.0, 0.0, 0.0, 0.0]

    monkeypatch.setattr(engine, "_realize_logits", logits)
    engine.progress_budgets = TinygradProgressBudgets(
        compile_seconds=600.0,
        prefill_seconds=10.0,
        decode_seconds=1.0,
        transport_seconds=30.0,
    )
    engine.progress_clock = _ScriptedClock((0.0, 0.0, 0.0, 0.0, 5.0))
    engine.submit(_text_task(max_output_tokens=4))
    first = list(engine.step())
    assert isinstance(first[0][1], TokenChunk)
    with pytest.raises(TinygradProgressDeadlineError, match="decode") as caught:
        _ = list(engine.step())
    assert caught.value.phase == "decode"
    assert calls["count"] == 1


class _ScriptedClock:
    def __init__(self, readings: tuple[float, ...]) -> None:
        self._readings = readings
        self._index = 0

    def __call__(self) -> float:
        reading = self._readings[self._index]
        if self._index + 1 < len(self._readings):
            self._index += 1
        return reading


def _fixed_logits(token_ids: object) -> list[float]:
    del token_ids
    return [1.0, 0.0, 0.0, 0.0]


def test_image_task_is_rejected(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    pytest.importorskip("tinygrad")
    from wexo.api.types import ImageGenerationTaskParams

    engine = _loaded_engine(
        tmp_path,
        monkeypatch,
        tokens=("a", "b", "c", "d"),
        eos_token_id=1,
        layer_count=1,
        include_output=True,
    )
    task = ImageGeneration(
        instance_id=InstanceId("tinygrad-gguf"),
        command_id=CommandId("image"),
        task_params=ImageGenerationTaskParams(prompt="draw", model="tinygrad-gguf"),
    )
    with pytest.raises(TinygradModelSupportError):
        engine.submit(task)


def _chat_tokenizer(
    specials: tuple[str, ...],
    formatted: str,
    *,
    pretokenizer: Literal["qwen2", "llama-bpe"],
) -> GgufTokenizer:
    plain = formatted
    for special in specials:
        plain = plain.replace(special, "")
    tokens = specials + gpt2_byte_symbols_for_text(plain)
    token_types = (3,) * len(specials) + (1,) * (len(tokens) - len(specials))
    return _tokenizer(tokens=tokens, token_types=token_types, pretokenizer=pretokenizer)


def _tokenizer(
    *,
    tokens: tuple[str, ...],
    merges: tuple[str, ...] = (),
    token_types: tuple[int, ...] | None = None,
    model: Literal["llama", "gpt2"] = "gpt2",
    pretokenizer: Literal["gpt-2", "llama-bpe", "qwen2", "sentencepiece"] = "gpt-2",
    eos_token_id: int | None = None,
) -> GgufTokenizer:
    resolved_types = (
        token_types if token_types is not None else tuple(1 for _token in tokens)
    )
    ids_by_token: dict[str, int] = {}
    for index, token in enumerate(tokens):
        if token not in ids_by_token:
            ids_by_token[token] = index
    merge_ranks: dict[tuple[str, str], int] = {}
    for rank, merge in enumerate(merges):
        left, separator, right = merge.partition(" ")
        if separator != " ":
            continue
        merge_ranks.setdefault((left, right), rank)
    return GgufTokenizer(
        model=model,
        pretokenizer=pretokenizer,
        tokens=tokens,
        merges=merges,
        token_types=resolved_types,
        bos_token_id=None,
        eos_token_id=eos_token_id,
        add_bos_token=False,
        ids_by_token=ids_by_token,
        merge_ranks=merge_ranks,
    )


class _PendingCancellations:
    def __init__(self, task_ids: list[TaskId]) -> None:
        self._task_ids = task_ids

    def collect(self) -> list[TaskId]:
        task_ids = self._task_ids
        self._task_ids = []
        return task_ids


def _text_task(*, max_output_tokens: int) -> TextGeneration:
    return TextGeneration(
        instance_id=InstanceId("tinygrad-gguf"),
        command_id=CommandId("command"),
        task_params=TextGenerationTaskParams(
            model=ModelId("tinygrad-gguf"),
            input=[
                InputMessage(role="user", content=InputMessageContent("a")),
            ],
            temperature=0.0,
            max_output_tokens=max_output_tokens,
        ),
    )


def _loaded_engine(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    *,
    tokens: tuple[str, ...],
    eos_token_id: int,
    layer_count: int,
    include_output: bool,
    end_layer: int | None = None,
    device_name: Literal["CPU", "CL"] = "CPU",
) -> TinygradEngine:
    from wexo.backends.tinygrad_engine import TinygradEngine

    _write_generation_gguf(
        tmp_path / "weights.gguf",
        tokens=tokens,
        eos_token_id=eos_token_id,
        layer_count=layer_count,
        include_output=include_output,
    )

    def use_temporary_directory(
        model_id: ModelId, card: ModelCard | None = None
    ) -> Path:
        _ = model_id
        return tmp_path

    monkeypatch.setattr(
        "wexo.backends.tinygrad_weights.build_model_path",
        use_temporary_directory,
    )
    resolved_end = layer_count if end_layer is None else end_layer
    engine = TinygradEngine(device_name=device_name)
    list(
        engine.iter_load_model(
            _bound_instance(
                start_layer=0,
                end_layer=resolved_end,
                layer_count=layer_count,
            )
        )
    )
    return engine


# Public aliases so the API serving test can reuse these fixtures without
# private cross-module imports.
loaded_engine = _loaded_engine
text_task = _text_task


def write_tinygrad_generation_gguf(
    path: Path,
    *,
    tokens: tuple[str, ...],
    eos_token_id: int,
    layer_count: int,
    include_output: bool,
) -> None:
    """Write the one-layer GGUF fixture used by loader and registration tests."""
    _write_generation_gguf(
        path,
        tokens=tokens,
        eos_token_id=eos_token_id,
        layer_count=layer_count,
        include_output=include_output,
    )


def _write_generation_gguf(
    path: Path,
    *,
    tokens: tuple[str, ...],
    eos_token_id: int,
    layer_count: int,
    include_output: bool,
) -> None:
    vocabulary = len(tokens)
    metadata = [
        *_tokenizer_metadata(
            tokens=tokens,
            merges=(),
            token_types=tuple(1 for _token in tokens),
            eos_token_id=eos_token_id,
        ),
        _kv_uint32("llama.block_count", layer_count),
        _kv_uint32("llama.embedding_length", _HIDDEN),
        _kv_uint32("llama.attention.head_count", _HEADS),
        _kv_uint32("llama.attention.head_count_kv", _KEY_VALUE_HEADS),
        _kv_uint32("llama.feed_forward_length", _INTERMEDIATE),
        _kv_float32("llama.attention.layer_norm_rms_epsilon", 1e-5),
        _kv_float32("llama.rope.freq_base", 10000.0),
        _kv_uint32("llama.attention.key_length", _HEAD_DIM),
        _kv_uint32("llama.vocab_size", vocabulary),
    ]
    query_rows = _HEADS * _HEAD_DIM
    key_rows = _KEY_VALUE_HEADS * _HEAD_DIM
    tensors: list[tuple[str, tuple[int, ...], int, bytes]] = [
        _named("token_embd.weight", (vocabulary, _HIDDEN)),
    ]
    for layer_index in range(layer_count):
        prefix = f"blk.{layer_index}"
        tensors.extend(
            [
                _named(f"{prefix}.attn_norm.weight", (_HIDDEN,)),
                _named(f"{prefix}.attn_q.weight", (query_rows, _HIDDEN)),
                _named(f"{prefix}.attn_k.weight", (key_rows, _HIDDEN)),
                _named(f"{prefix}.attn_v.weight", (key_rows, _HIDDEN)),
                _named(f"{prefix}.attn_output.weight", (_HIDDEN, query_rows)),
                _named(f"{prefix}.ffn_norm.weight", (_HIDDEN,)),
                _named(f"{prefix}.ffn_gate.weight", (_INTERMEDIATE, _HIDDEN)),
                _named(f"{prefix}.ffn_up.weight", (_INTERMEDIATE, _HIDDEN)),
                _named(f"{prefix}.ffn_down.weight", (_HIDDEN, _INTERMEDIATE)),
            ]
        )
    if include_output:
        tensors.append(_named("output_norm.weight", (_HIDDEN,)))
        tensors.append(_named("output.weight", (vocabulary, _HIDDEN)))
    _write_gguf(path, metadata, tensors)


def _tokenizer_metadata(
    *,
    tokens: tuple[str, ...],
    merges: tuple[str, ...],
    token_types: tuple[int, ...],
    eos_token_id: int,
) -> list[bytes]:
    return [
        _kv_string("general.architecture", "llama"),
        _kv_uint32("general.file_type", 1),
        _kv_string("tokenizer.ggml.model", "gpt2"),
        _kv_string("tokenizer.ggml.pre", "gpt-2"),
        _kv_uint32("tokenizer.ggml.eos_token_id", eos_token_id),
        _kv_string_array("tokenizer.ggml.tokens", tokens),
        _kv_string_array("tokenizer.ggml.merges", merges),
        _kv_int_array("tokenizer.ggml.token_type", token_types),
    ]


def _named(
    name: str, logical_shape: tuple[int, ...]
) -> tuple[str, tuple[int, ...], int, bytes]:
    count = 1
    for dimension in logical_shape:
        count *= dimension
    return (name, tuple(reversed(logical_shape)), 1, b"\x00" * (count * 2))


def _write_gguf(
    path: Path,
    metadata: list[bytes],
    tensors: list[tuple[str, tuple[int, ...], int, bytes]],
) -> None:
    payload = bytearray()
    infos = bytearray()
    offset = 0
    for name, dimensions, ggml_type, raw in tensors:
        aligned = ((offset + 31) // 32) * 32
        payload.extend(b"\x00" * (aligned - offset))
        infos.extend(_tensor_info(name, dimensions, ggml_type, aligned))
        payload.extend(raw)
        offset = aligned + len(raw)
    header = bytearray(b"GGUF")
    header.extend(struct.pack("<I", 3))
    header.extend(struct.pack("<q", len(tensors)))
    header.extend(struct.pack("<q", len(metadata)))
    for item in metadata:
        header.extend(item)
    header.extend(infos)
    data_start = ((len(header) + 31) // 32) * 32
    header.extend(b"\x00" * (data_start - len(header)))
    header.extend(payload)
    path.write_bytes(header)


def _tensor_info(
    name: str, dimensions: tuple[int, ...], ggml_type: int, offset: int
) -> bytes:
    body = _pack_string(name)
    body += struct.pack("<I", len(dimensions))
    for dimension in dimensions:
        body += struct.pack("<Q", dimension)
    body += struct.pack("<I", ggml_type)
    body += struct.pack("<Q", offset)
    return body


def _kv_string(key: str, value: str) -> bytes:
    return _pack_string(key) + struct.pack("<I", 8) + _pack_string(value)


def _kv_uint32(key: str, value: int) -> bytes:
    return _pack_string(key) + struct.pack("<I", 4) + struct.pack("<I", value)


def _kv_float32(key: str, value: float) -> bytes:
    return _pack_string(key) + struct.pack("<I", 6) + struct.pack("<f", value)


def _kv_string_array(key: str, values: tuple[str, ...]) -> bytes:
    body = struct.pack("<I", 8) + struct.pack("<Q", len(values))
    for value in values:
        body += _pack_string(value)
    return _pack_string(key) + struct.pack("<I", 9) + body


def _kv_int_array(key: str, values: tuple[int, ...]) -> bytes:
    body = struct.pack("<I", 5) + struct.pack("<Q", len(values))
    for value in values:
        body += struct.pack("<i", value)
    return _pack_string(key) + struct.pack("<I", 9) + body


def _pack_string(value: str) -> bytes:
    encoded = value.encode("utf-8")
    return struct.pack("<Q", len(encoded)) + encoded


def _bound_instance(
    *,
    start_layer: int,
    end_layer: int,
    layer_count: int,
    device_rank: int = 0,
    world_size: int = 1,
) -> BoundInstance:
    model_card = ModelCard(
        model_id=ModelId("tinygrad-gguf"),
        storage_size=Memory.from_mb(16),
        n_layers=layer_count,
        hidden_size=_HIDDEN,
        supports_tensor=False,
        tasks=[ModelTask.TextGeneration],
        backends=[Backend.TinygradCpu],
    )
    shard = PipelineShardMetadata(
        model_card=model_card,
        device_rank=device_rank,
        world_size=world_size,
        start_layer=start_layer,
        end_layer=end_layer,
        n_layers=layer_count,
    )
    node_id = NodeId(f"node-{device_rank}")
    runner_id = RunnerId(f"runner-{device_rank}")
    instance = TinygradInstance(
        instance_id=InstanceId("tinygrad-gguf"),
        shard_assignments=ShardAssignments(
            model_id=shard.model_card.model_id,
            node_to_runner={node_id: runner_id},
            runner_to_shard={runner_id: shard},
        ),
        device_backend_by_node={node_id: Backend.TinygradCpu},
    )
    return BoundInstance(
        instance=instance,
        bound_runner_id=runner_id,
        bound_node_id=node_id,
    )


def test_pipeline_ranks_emit_one_token_from_rank_zero(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    pytest.importorskip("tinygrad")
    engines = _loaded_pipeline(tmp_path, monkeypatch, world_size=3)
    transports = connect_memory_pipeline(3)
    for engine, transport in zip(engines, transports, strict=True):
        engine.pipeline_transport = transport
    task = _text_task(max_output_tokens=1)
    for engine in engines:
        engine.warmup()
        engine.submit(task)

    results: list[list[tuple[TaskId, object]]] = [[], [], []]
    errors: list[BaseException] = []

    def run(index: int) -> None:
        try:
            results[index].extend(engines[index].step())
        except BaseException as error:
            errors.append(error)

    threads = [threading.Thread(target=run, args=(index,)) for index in (1, 2)]
    for thread in threads:
        thread.start()
    run(0)
    for thread in threads:
        thread.join(30)
        assert not thread.is_alive()
    assert errors == []

    assert len(results[0]) == 2
    _task_id, chunk = results[0][0]
    assert isinstance(chunk, TokenChunk)
    assert chunk.token_id == 0
    assert chunk.text == "a"
    assert chunk.finish_reason == "length"
    assert chunk.usage is not None
    assert chunk.usage.prompt_tokens == 1
    assert chunk.usage.completion_tokens == 1
    assert isinstance(results[0][1][1], FinishedResponse)
    for index in (1, 2):
        assert len(results[index]) == 1
        assert isinstance(results[index][0][1], FinishedResponse)
    for engine in engines:
        engine.close()


def test_cancel_frame_unblocks_the_next_rank(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    pytest.importorskip("tinygrad")
    engines = _loaded_pipeline(tmp_path, monkeypatch, world_size=2)
    transports = connect_memory_pipeline(2)
    for engine, transport in zip(engines, transports, strict=True):
        engine.pipeline_transport = transport
    task = _text_task(max_output_tokens=4)
    for engine in engines:
        engine.submit(task)
    engines[0].cancel_receiver = _PendingCancellations([task.task_id])

    follower: list[tuple[TaskId, object]] = []
    errors: list[BaseException] = []

    def run_follower() -> None:
        try:
            follower.extend(engines[1].step())
        except BaseException as error:
            errors.append(error)

    thread = threading.Thread(target=run_follower)
    thread.start()
    time.sleep(0.2)
    leader = list(engines[0].step())
    thread.join(5)
    assert not thread.is_alive()
    assert errors == []
    assert len(leader) == 1
    assert isinstance(leader[0][1], CancelledResponse)
    assert len(follower) == 1
    assert isinstance(follower[0][1], CancelledResponse)
    for engine in engines:
        engine.close()


def _loaded_pipeline(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, *, world_size: int
) -> list[TinygradEngine]:
    _write_generation_gguf(
        tmp_path / "weights.gguf",
        tokens=("a", "b", "c", "d"),
        eos_token_id=1,
        layer_count=world_size,
        include_output=True,
    )

    def use_temporary_directory(
        model_id: ModelId, card: ModelCard | None = None
    ) -> Path:
        _ = model_id
        return tmp_path

    monkeypatch.setattr(
        "wexo.backends.tinygrad_weights.build_model_path",
        use_temporary_directory,
    )
    engines: list[TinygradEngine] = []
    for device_rank in range(world_size):
        engine = TinygradEngine(device_name="CPU")
        list(
            engine.iter_load_model(
                _bound_instance(
                    start_layer=device_rank,
                    end_layer=device_rank + 1,
                    layer_count=world_size,
                    device_rank=device_rank,
                    world_size=world_size,
                )
            )
        )
        engines.append(engine)
    return engines
