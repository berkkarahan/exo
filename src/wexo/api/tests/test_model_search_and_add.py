# pyright: reportUnusedFunction=false, reportAny=false, reportPrivateUsage=false, reportUnusedVariable=false
from __future__ import annotations

from unittest.mock import AsyncMock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from wexo.api.main import API
from wexo.shared.models.model_cards import ModelCard, ModelId, ModelTask
from wexo.shared.types.backends import Backend
from wexo.shared.types.common import SystemId
from wexo.shared.types.memory import Memory
from wexo.shared.types.worker.downloads import FileListEntry


def _create_test_api() -> tuple[API, TestClient]:
    app = FastAPI()
    api = object.__new__(API)
    api.app = app
    api._system_id = SystemId("test-system")
    api._setup_exception_handlers()
    api.command_sender = AsyncMock()

    app.get("/models/search")(api.search_models)
    app.get("/models/huggingface/files")(api.get_huggingface_model_files)
    app.post("/models/add")(api.add_custom_model)

    return api, TestClient(app)


def test_huggingface_files_endpoint() -> None:
    _api, client = _create_test_api()

    mock_entries = [
        FileListEntry(type="file", path="model-00001-of-00002.gguf", size=2000),
        FileListEntry(type="file", path="model-q4_k_m.gguf", size=1000),
        FileListEntry(type="file", path="config.json", size=50),
    ]

    with patch(
        "wexo.download.download_utils.fetch_file_list_with_cache",
        new=AsyncMock(return_value=mock_entries),
    ):
        response = client.get("/models/huggingface/files?model_id=org/repo")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2
        assert data[0]["filename"] == "model-00001-of-00002.gguf"
        assert data[0]["is_split"] is True
        assert data[1]["filename"] == "model-q4_k_m.gguf"
        assert data[1]["quantization"] == "Q4_K_M"
        assert data[1]["size_bytes"] == 1000


def test_add_custom_model_supports_colon_syntax() -> None:
    _api, client = _create_test_api()

    mock_card = ModelCard(
        model_id=ModelId("org/repo"),
        storage_size=Memory.from_bytes(1000),
        n_layers=1,
        hidden_size=16,
        num_key_value_heads=2,
        num_attention_heads=4,
        supports_tensor=True,
        gguf_filename="my-model-q4_k_m.gguf",
        tasks=[ModelTask.TextGeneration],
        backends=[Backend.TinygradCpu],
    )

    with (
        patch(
            "wexo.shared.models.model_cards.ModelCard.fetch_from_hf",
            new=AsyncMock(return_value=mock_card),
        ) as mock_fetch,
        patch("wexo.shared.models.model_cards.card_cache.save", new=AsyncMock()),
    ):
        response = client.post(
            "/models/add", json={"model_id": "org/repo:my-model-q4_k_m.gguf"}
        )
        assert response.status_code == 200
        mock_fetch.assert_called_once_with(
            ModelId("org/repo"), gguf_filename="my-model-q4_k_m.gguf"
        )


def test_add_custom_model_supports_gguf_filename_param() -> None:
    _api, client = _create_test_api()

    mock_card = ModelCard(
        model_id=ModelId("org/repo"),
        storage_size=Memory.from_bytes(1000),
        n_layers=1,
        hidden_size=16,
        num_key_value_heads=2,
        num_attention_heads=4,
        supports_tensor=True,
        gguf_filename="custom.gguf",
        tasks=[ModelTask.TextGeneration],
        backends=[Backend.TinygradCpu],
    )

    with (
        patch(
            "wexo.shared.models.model_cards.ModelCard.fetch_from_hf",
            new=AsyncMock(return_value=mock_card),
        ) as mock_fetch,
        patch("wexo.shared.models.model_cards.card_cache.save", new=AsyncMock()),
    ):
        response = client.post(
            "/models/add",
            json={"model_id": "org/repo", "gguf_filename": "custom.gguf"},
        )
        assert response.status_code == 200
        mock_fetch.assert_called_once_with(
            ModelId("org/repo"), gguf_filename="custom.gguf"
        )
