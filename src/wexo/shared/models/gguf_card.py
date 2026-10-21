"""Register a GGUF repository as a model card without a safetensors index.

The card names one file and budgets placement with the larger of that file's
byte size and the float16 size the tinygrad loader realizes. ``fetch_from_hf``
calls ``fetch_gguf_model_card`` when the repository has no safetensors index.
``GgufRegistrationError`` is handled there and by the model-add API, which
surfaces the message to the caller.
"""

from __future__ import annotations

import re
import tempfile
from collections.abc import Awaitable, Callable, Iterable, Sequence
from pathlib import Path, PurePosixPath
from typing import Final
from urllib.parse import quote, urljoin

from wexo.shared.models.model_cards import ModelCard, ModelTask
from wexo.shared.types.backends import Backend
from wexo.shared.types.common import ModelId
from wexo.shared.types.memory import Memory
from wexo.shared.types.worker.downloads import FileListEntry

_FLOAT16_BYTES: Final = 2
_HEADER_ATTEMPT_BYTES: Final = (1_048_576, 4_194_304, 16_777_216, 67_108_864)
_QUANT_PREFERENCE: Final = (
    "q4_k_m",
    "q5_k_m",
    "q6_k",
    "q8_0",
    "q4_0",
    "q3_k_m",
    "q2_k",
)
_SPLIT_FILE: Final = re.compile(r"-\d+-of-\d+\.gguf$", re.IGNORECASE)
_TRUNCATED_HEADER: Final = "GGUF header is truncated"

TINYGRAD_GGUF_BACKENDS: Final = (
    Backend.TinygradAmd,
    Backend.TinygradMetal,
    Backend.TinygradCuda,
    Backend.TinygradCpu,
    Backend.WinAMD,
    Backend.WinCUDA,
    Backend.WinCPU,
)


class GgufRegistrationError(Exception):
    """A GGUF repository cannot be turned into one model card.

    ``ModelCard.fetch_from_hf`` lets this propagate to the model-add API.
    """


def repository_gguf_paths(paths: Iterable[str]) -> tuple[str, ...]:
    """Return repository paths that name a GGUF file."""
    return tuple(path for path in paths if path.lower().endswith(".gguf"))


def choose_gguf_filename(paths: Iterable[str], preference: str | None) -> str:
    """Pick one GGUF path from a repository listing.

    An explicit preference matches by exact filename, basename, or sub-token.
    With no preference, it selects the best available quantization,
    resolving any ambiguity and falling back to any available single or
    split GGUF file.

    Raises:
        GgufRegistrationError: If the repository contains no GGUF files.
    """
    files = repository_gguf_paths(paths)
    if not files:
        raise GgufRegistrationError(
            f"No GGUF files found in repository listing: {list(paths)}"
        )

    if preference is not None:
        pref = preference.strip()
        # Direct exact or basename match (case-insensitive fallback)
        matches = [
            path
            for path in files
            if path == pref
            or PurePosixPath(path).name == pref
            or path.lower() == pref.lower()
            or PurePosixPath(path).name.lower() == pref.lower()
        ]
        if matches:
            return matches[0]

        # Token match within filename
        token_matches = [
            path for path in files if pref.lower() in PurePosixPath(path).name.lower()
        ]
        if token_matches:
            token_matches.sort(key=lambda p: (len(PurePosixPath(p).name), p))
            return token_matches[0]

        raise GgufRegistrationError(
            f"{preference} does not match any GGUF file in {list(files)}"
        )

    singles = tuple(
        path for path in files if _SPLIT_FILE.search(PurePosixPath(path).name) is None
    )
    candidate_files = singles if singles else files

    # 1. Try preference tokens
    for token in _QUANT_PREFERENCE:
        matched = tuple(
            path for path in candidate_files if token in PurePosixPath(path).name.lower()
        )
        if len(matched) == 1:
            return matched[0]
        if len(matched) > 1:
            clean = tuple(m for m in matched if "imatrix" not in PurePosixPath(m).name.lower())
            pool = clean if clean else matched
            return sorted(pool, key=lambda p: (len(PurePosixPath(p).name), p))[0]

    # 2. Try extended common quants
    extended_tokens = (
        "q4_k_s",
        "q5_k_s",
        "q6_k_l",
        "q4_1",
        "q5_0",
        "q5_1",
        "iq4_nl",
        "iq4_xs",
        "iq3_m",
        "iq3_s",
        "iq3_xs",
        "iq2_m",
        "q2_k_l",
        "bf16",
        "f16",
    )
    for token in extended_tokens:
        matched = tuple(
            path for path in candidate_files if token in PurePosixPath(path).name.lower()
        )
        if matched:
            clean = tuple(m for m in matched if "imatrix" not in PurePosixPath(m).name.lower())
            pool = clean if clean else matched
            return sorted(pool, key=lambda p: (len(PurePosixPath(p).name), p))[0]

    # 3. Fall back to the first candidate in sorted order
    return sorted(candidate_files)[0]


def model_card_from_gguf_file(
    model_id: ModelId,
    path: Path,
    *,
    repo_path: str,
    file_size: int,
) -> ModelCard:
    """Build a tinygrad model card from one local GGUF header.

    ``file_size`` is the complete object size. ``path`` may be only a header
    prefix as long as that prefix includes every tensor record.

    Raises:
        GgufRegistrationError: Propagates through ``fetch_from_hf``.
    """
    from wexo.backends.tinygrad_checkpoint import (
        architecture_from_gguf,
        read_one_gguf_checkpoint,
    )
    from wexo.backends.tinygrad_weights import (
        TinygradModelSupportError,
        TinygradWeightError,
    )

    try:
        checkpoint = read_one_gguf_checkpoint(path)
        architecture = architecture_from_gguf(checkpoint)
    except (TinygradWeightError, TinygradModelSupportError) as error:
        raise GgufRegistrationError(str(error)) from error

    key_value_heads = architecture.num_key_value_heads
    if (
        architecture.num_hidden_layers < 1
        or architecture.hidden_size < 1
        or key_value_heads is None
        or key_value_heads < 1
    ):
        raise GgufRegistrationError(
            f"{repo_path} does not describe a positive layer, hidden size, "
            "or attention head count"
        )
    if file_size < 1:
        raise GgufRegistrationError(f"{repo_path} has no bytes")

    realized_bytes = sum(
        record.element_count * _FLOAT16_BYTES
        for record in checkpoint.tensors
        if record.canonical_name is not None
    )
    if realized_bytes < 1:
        raise GgufRegistrationError(f"{repo_path} has no tensors the loader can place")

    context_value = checkpoint.scalar(f"{checkpoint.architecture_name}.context_length")
    context_length = (
        context_value
        if isinstance(context_value, int) and not isinstance(context_value, bool)
        else 0
    )
    if context_length < 0:
        raise GgufRegistrationError(f"{repo_path} has a negative context length")

    family = (
        "qwen"
        if checkpoint.architecture_name in ("qwen2", "qwen3")
        else checkpoint.architecture_name
    )
    return ModelCard(
        model_id=model_id,
        storage_size=Memory.from_bytes(max(file_size, realized_bytes)),
        n_layers=architecture.num_hidden_layers,
        hidden_size=architecture.hidden_size,
        supports_tensor=checkpoint.architecture_name in {"llama", "qwen2", "qwen3"},
        num_key_value_heads=key_value_heads,
        num_attention_heads=architecture.num_attention_heads,
        tasks=[ModelTask.TextGeneration],
        family=family,
        quantization=checkpoint.file_type_name or "",
        base_model=checkpoint.architecture_name,
        context_length=context_length,
        trust_remote_code=False,
        is_custom=True,
        gguf_filename=repo_path,
        backends=list(TINYGRAD_GGUF_BACKENDS),
    )


def model_card_from_gguf_bytes(
    model_id: ModelId,
    repo_path: str,
    payload: bytes,
    *,
    file_size: int,
) -> ModelCard:
    """Parse ``payload`` as a GGUF header and return its model card."""
    with tempfile.TemporaryDirectory() as temporary:
        path = Path(temporary) / PurePosixPath(repo_path).name
        _ = path.write_bytes(payload)
        return model_card_from_gguf_file(
            model_id,
            path,
            repo_path=repo_path,
            file_size=file_size,
        )


async def gguf_header_bytes(
    read_prefix: Callable[[int], Awaitable[bytes]],
    *,
    file_size: int,
) -> bytes:
    """Return the shortest tried prefix that contains a complete GGUF header.

    Raises:
        GgufRegistrationError: Propagates through ``fetch_gguf_model_card``
            when every prefix is still truncated.
    """
    from wexo.backends.tinygrad_checkpoint import read_one_gguf_checkpoint
    from wexo.backends.tinygrad_weights import TinygradWeightError

    attempts = tuple(
        dict.fromkeys(min(size, file_size) for size in _HEADER_ATTEMPT_BYTES)
    )
    for length in attempts:
        if length < 1:
            continue
        payload = await read_prefix(length)
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "header.gguf"
            _ = path.write_bytes(payload)
            try:
                _ = read_one_gguf_checkpoint(path)
            except TinygradWeightError as error:
                if str(error) != _TRUNCATED_HEADER:
                    raise GgufRegistrationError(str(error)) from error
                continue
        return payload
    raise GgufRegistrationError(
        f"GGUF header did not fit in the first {attempts[-1]} bytes"
    )


async def fetch_gguf_model_card(
    model_id: ModelId,
    file_list: Sequence[FileListEntry],
    *,
    preference: str | None = None,
    read_prefix: Callable[[int], Awaitable[bytes]] | None = None,
) -> ModelCard:
    """Choose one GGUF file and build its card from a header prefix.

    ``read_prefix`` replaces the Hugging Face range request in tests.

    Raises:
        GgufRegistrationError: Propagates through ``ModelCard.fetch_from_hf``.
    """
    paths = tuple(entry.path for entry in file_list if entry.type == "file")
    repo_path = choose_gguf_filename(paths, preference)
    listed_size = next(
        (entry.size for entry in file_list if entry.path == repo_path),
        None,
    )
    file_size = listed_size if listed_size is not None and listed_size > 0 else None
    if file_size is None:
        from wexo.download.download_utils import file_meta

        file_size, _etag = await file_meta(model_id, "main", repo_path)

    async def http_prefix(length: int) -> bytes:
        return await _read_http_prefix(model_id, repo_path, length)

    payload = await gguf_header_bytes(
        read_prefix if read_prefix is not None else http_prefix,
        file_size=file_size,
    )
    return model_card_from_gguf_bytes(
        model_id,
        repo_path,
        payload,
        file_size=file_size,
    )


async def _read_http_prefix(model_id: ModelId, repo_path: str, length: int) -> bytes:
    from wexo.download.download_utils import (
        HuggingFaceAuthenticationError,
        HuggingFaceRateLimitError,
        create_http_session,
        get_download_headers,
    )
    from wexo.download.huggingface_utils import get_hf_endpoint

    headers = await get_download_headers()
    headers["Range"] = f"bytes=0-{length - 1}"
    url = urljoin(
        f"{get_hf_endpoint()}/{model_id}/resolve/main/",
        quote(repo_path, safe="/"),
    )
    async with (
        create_http_session(timeout_profile="short") as session,
        session.get(url, headers=headers) as response,
    ):
        if response.status in (401, 403):
            raise HuggingFaceAuthenticationError(
                f"Model {model_id} file {repo_path} requires authentication"
            )
        if response.status == 404:
            raise GgufRegistrationError(f"{repo_path} was not found in {model_id}")
        if response.status == 429:
            raise HuggingFaceRateLimitError(
                f"Rate limited while reading {repo_path} from {model_id}"
            )
        if response.status not in (200, 206):
            raise GgufRegistrationError(
                f"Reading {repo_path} from {model_id} returned HTTP {response.status}"
            )
        payload = bytearray()
        async for chunk in response.content.iter_chunked(1024 * 1024):
            payload.extend(chunk)
            if len(payload) >= length:
                break
        return bytes(payload[:length])


def is_split_gguf(name: str) -> bool:
    """Return whether ``name`` matches the GGUF split-file naming pattern."""
    return _SPLIT_FILE.search(name) is not None
