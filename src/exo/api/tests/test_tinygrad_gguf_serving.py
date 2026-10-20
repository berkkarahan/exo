from __future__ import annotations

from collections.abc import AsyncGenerator
from pathlib import Path

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from pydantic import BaseModel

from exo.api.main import API
from exo.api.types import (
    ChatCompletionChoice,
    ChatCompletionMessage,
    ChatCompletionRequest,
    ChatCompletionResponse,
    StreamingChoiceResponse,
)
from exo.backends.tests.test_tinygrad_generate import loaded_engine, text_task
from exo.shared.types.chunks import (
    ErrorChunk,
    PrefillProgressChunk,
    TokenChunk,
    ToolCallChunk,
)
from exo.shared.types.common import CommandId, ModelId
from exo.shared.types.tasks import TextGeneration
from exo.shared.types.text_generation import TextGenerationTaskParams


class ChatCompletionStreamEvent(BaseModel):
    """One SSE ``data:`` payload emitted by ``generate_chat_stream``."""

    choices: list[StreamingChoiceResponse]


@pytest.mark.parametrize("stream", [False, True])
async def test_tinygrad_gguf_serves_chat_completion_over_http(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, stream: bool
) -> None:
    engine = loaded_engine(
        tmp_path,
        monkeypatch,
        tokens=("a", "b", "c", "d"),
        eos_token_id=1,
        layer_count=1,
        include_output=True,
    )
    api = object.__new__(API)
    api.app = FastAPI()
    api._setup_exception_handlers()  # pyright: ignore[reportPrivateUsage]
    api.app.post("/v1/chat/completions", response_model=None)(api.chat_completions)
    command_id = CommandId("tinygrad-gguf-http")

    async def validate_model(_model_id: ModelId) -> ModelId:
        return ModelId("tinygrad-gguf")

    async def dispatch(task_params: TextGenerationTaskParams) -> TextGeneration:
        task = text_task(max_output_tokens=1).model_copy(
            update={"task_params": task_params, "command_id": command_id}
        )
        engine.submit(task)
        return task

    async def chunks(
        _command_id: CommandId,
    ) -> AsyncGenerator[
        TokenChunk | ErrorChunk | ToolCallChunk | PrefillProgressChunk, None
    ]:
        while True:
            results = list(engine.step())
            if not results:
                return
            for _task_id, result in results:
                if isinstance(
                    result,
                    (TokenChunk, ErrorChunk, ToolCallChunk, PrefillProgressChunk),
                ):
                    yield result
                else:
                    return

    monkeypatch.setattr(api, "_validate_model_has_instance", validate_model)
    monkeypatch.setattr(api, "_send_text_generation_with_images", dispatch)
    monkeypatch.setattr(api, "_token_chunk_stream", chunks)

    request = ChatCompletionRequest(
        model=ModelId("tinygrad-gguf"),
        messages=[ChatCompletionMessage(role="user", content="a")],
        max_tokens=1,
        temperature=0.0,
        stream=stream,
    )
    try:
        async with AsyncClient(
            transport=ASGITransport(app=api.app), base_url="http://test"
        ) as client:
            response = await client.post(
                "/v1/chat/completions", json=request.model_dump(mode="json")
            )
        assert response.status_code == 200
        if stream:
            events = [
                ChatCompletionStreamEvent.model_validate_json(
                    line.removeprefix("data: ")
                )
                for line in response.text.splitlines()
                if line.startswith("data: {")
            ]
            assert events
            assert any(event.choices[0].delta.content == "a" for event in events)
            assert events[-1].choices[0].finish_reason == "length"
            assert response.text.rstrip().endswith("data: [DONE]")
        else:
            completion = ChatCompletionResponse.model_validate_json(response.content)
            assert completion.model == "tinygrad-gguf"
            choice = completion.choices[0]
            assert isinstance(choice, ChatCompletionChoice)
            assert isinstance(choice.message.content, str)
            assert choice.message.content == "a"
            assert choice.finish_reason == "length"
            assert completion.usage is not None
            assert completion.usage.completion_tokens == 1
    finally:
        engine.close()
