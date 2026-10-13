from typing import Any

bos_token: str
eos_token: str
dsml_token: str
thinking_start_token: str
thinking_end_token: str

def encode_messages(
    messages: list[dict[str, Any]],
    thinking_mode: str = "thinking",
    context: list[dict[str, Any]] | None = None,
    drop_thinking: bool = True,
    add_default_bos_token: bool = True,
    tools: Any = None,
) -> str: ...
