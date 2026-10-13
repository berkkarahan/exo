# Requirements: GGUF model card

## Problem

`ModelCard.fetch_from_hf` downloads `config.json` and `model.safetensors.index.json`. A GGUF-only repository cannot be registered, and no built-in card advertises a Tinygrad or Windows backend. Placement then cannot put that model on the Windows node.

## Features

### Feature 1: Choose one GGUF file

- [x] Given one `.gguf` path, When a card is registered with no preference, Then that path is `gguf_filename`.
- [x] Given several complete quant files, When no preference is set, Then the unique `q4_k_m` file is selected before a larger quant.
- [x] Given an explicit filename, When that file is in the listing, Then that file is selected.
- [x] Given only a split file such as `model-00001-of-00002.gguf`, When registration runs, Then it fails instead of recording one shard of a set.

### Feature 2: Budget placement from the header

- [x] Given a GGUF header, When the card is built, Then `n_layers`, `hidden_size`, and `num_key_value_heads` come from that header.
- [x] Given a file size and a float16 realization size, When the card is built, Then `storage_size` is the larger of the two.
- [x] Given the card, When it is placed on a node that advertises only `WinAMD` and has enough memory, Then the instance is a tinygrad instance bound to `WinAMD`.

### Feature 3: Download only the named file

- [x] Given `gguf_filename`, When download patterns are resolved, Then that file is included and other `.gguf` names are not.
- [x] Given a repository that also has `model.safetensors.index.json`, When fetch is called without `gguf_filename`, Then the safetensors card is returned.

## Out of scope

- Dashboard controls for picking a quant.
- Multi-file GGUF splits.
- Changing placement for safetensors cards.
