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

from exo.shared.models.model_cards import ModelCard, ModelTask
from exo.shared.types.backends import Backend
from exo.shared.types.common import ModelId
from exo.shared.types.memory import Memory
from exo.shared.types.worker.downloads import FileListEntry

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
    """Pick one non-split GGUF path from a repository listing.

    An explicit ``*.gguf`` preference must match one listed path. Any other
    preference must match one file name. With no preference, a repository
    with one file uses that file; otherwise the first unique quant token in
    ``q4_k_m``, ``q5_k_m``, ``q6_k``, ``q8_0``, ``q4_0``, ``q3_k_m``, ``q2_k``
    wins.

    Raises:
        GgufRegistrationError: Propagates through ``fetch_from_hf`` when the
            listing has no single registrable file.
    """
    files = repository_gguf_paths(paths)
    if preference is not None and preference.lower().endswith(".gguf"):
        matches = [
            path
            for path in files
            if path == preference or PurePosixPath(path).name == preference
        ]
        if len(matches) != 1:
            raise GgufRegistrationError(
                f"{preference} does not match one GGUF file in {list(files)}"
            )
        chosen = matches[0]
        _reject_split(chosen)
        return chosen

    singles = tuple(
        path for path in files if _SPLIT_FILE.search(PurePosixPath(path).name) is None
    )
    if not singles:
        raise GgufRegistrationError(
            "only split GGUF files were found; a single-file GGUF is required: "
            f"{list(files)}"
        )
    if preference is not None:
        return _unique_token_match(singles, preference.lower())
    if len(singles) == 1:
        return singles[0]
    for token in _QUANT_PREFERENCE:
        matched = tuple(
            path for path in singles if token in PurePosixPath(path).name.lower()
        )
        if len(matched) == 1:
            return matched[0]
        if len(matched) > 1:
            raise GgufRegistrationError(
                f"more than one GGUF file matches {token}: {list(matched)}"
            )
    raise GgufRegistrationError(
        f"repository has no single GGUF file to register: {list(files)}"
    )


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
    from exo.backends.tinygrad_checkpoint import (
        architecture_from_gguf,
        read_one_gguf_checkpoint,
    )
    from exo.backends.tinygrad_weights import (
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
    from exo.backends.tinygrad_checkpoint import read_one_gguf_checkpoint
    from exo.backends.tinygrad_weights import TinygradWeightError

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
        from exo.download.download_utils import file_meta

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
    from exo.download.download_utils import (
        HuggingFaceAuthenticationError,
        HuggingFaceRateLimitError,
        create_http_session,
        get_download_headers,
    )
    from exo.download.huggingface_utils import get_hf_endpoint

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


def _reject_split(repo_path: str) -> None:
    if _SPLIT_FILE.search(PurePosixPath(repo_path).name):
        raise GgufRegistrationError(
            f"{repo_path} is one split of a multi-file GGUF and cannot be "
            "registered as a single file"
        )


def _unique_token_match(paths: tuple[str, ...], token: str) -> str:
    matched = tuple(path for path in paths if token in PurePosixPath(path).name.lower())
    if len(matched) != 1:
        raise GgufRegistrationError(
            f"{token} does not match one GGUF file in {list(paths)}"
        )
    return matched[0]
