# Solution: GGUF model card

## Approach

`choose_gguf_filename` is a pure listing function. `model_card_from_gguf_file` reads one header through `read_one_gguf_checkpoint` and `architecture_from_gguf`. `fetch_from_hf` lists the repository first. A root safetensors index keeps the existing card. Otherwise, when a GGUF file exists, `fetch_gguf_model_card` range-reads a header prefix and builds the card.

`resolve_allow_patterns` returns the named GGUF file plus tokenizer sidecars. Other repositories still receive `*`.

The card's backends are the tinygrad device identities and the Windows join identities. `supports_tensor` is false because this loader places pipeline shards.

## Error handling

`GgufRegistrationError` is the registration failure. It wraps an unreadable header, an unsupported architecture, and an ambiguous listing. `ModelCard.fetch_from_hf` does not convert it. HTTP 401 and 429 stay the existing download exceptions.
