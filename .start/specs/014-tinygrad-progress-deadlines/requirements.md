# Requirements: Tinygrad Progress Deadlines

## User Stories

### Story: Refuse a pipeline peer that is not this instance

When two Windows nodes open a Tinygrad pipeline, each rank learns the other's instance, rank, model, and protocol. A peer for a different model or rank does not proceed to hidden states.

### Story: Stop a rank that is no longer making progress

When compile, prefill, decode, or a pipeline receive exceeds its budget, the runner raises a named deadline instead of waiting forever. The same line is classified if it appears on stderr.

### Story: Chat again immediately after cancelling

When the in-flight task is cancelled and the next text task is submitted after that cancellation has been applied, the next task produces a token.

## Acceptance Criteria

1. [x] A pipeline `open` exchanges instance id, device rank, world size, model id, protocol `tinygrad-pipeline`, and protocol version 1.
2. [x] A peer whose model id differs is rejected with a handshake error before hidden states are sent.
3. [x] A compile budget that is already overdue raises before warmup runs a forward.
4. [x] A prefill budget that is already overdue raises before the first forward, and a decode budget raises on the following step.
5. [x] A transport receive with no incoming frame raises when its budget is overdue.
6. [x] A stderr line reporting a Tinygrad progress deadline is classified with that phase.
7. [x] After cancel-all has been applied to the current task, the next submitted task yields a token chunk.

## Out of Scope

- Sleep, resume, disconnect, and rejoin.
- Request sequence numbers beyond the existing task id.
- Firewall rules, driver-version text, and peer-discovery probes.
