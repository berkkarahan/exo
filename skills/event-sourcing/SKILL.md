---
name: event-sourcing
description: Add or modify wEXO events, commands, tasks, and state transitions following the event-sourcing architecture (State, apply(), TaggedModel events, topics). Use when adding a new event type, changing apply() or State, wiring master indexing and broadcast, or editing src/wexo/shared/types or src/wexo/shared/apply.py.
---

# Event Sourcing in wEXO

wEXO is event-sourced: the master indexes events and broadcasts `IndexedEvent`s; every node replays
them through a pure `apply` to derive identical state.

## Core pieces

- `State` - `src/wexo/shared/types/state.py`. A `FrozenModel` (immutable). Never mutate in place;
  return a new instance via `model_copy(update=...)`.
- `apply(state, event)` - `src/wexo/shared/apply.py`. Pure. Asserts `last_event_applied_idx == event.idx - 1`,
  dispatches via a `match` in `event_apply`, then bumps `last_event_applied_idx`.
- Events - `src/wexo/shared/types/events.py`. `BaseEvent(TaggedModel)` subclasses, unioned into `Event`.
  `TaggedModel` serializes as `{"ClassName": {...}}`, so the class name is part of the wire format.
- Topics - `src/wexo/routing/topics.py`: `GLOBAL_EVENTS`, `LOCAL_EVENTS`, `COMMANDS`,
  `ELECTION_MESSAGES`, `CONNECTION_MESSAGES`, `DOWNLOAD_COMMANDS`.

## Add a new event type

1. Define it in `events.py`: `class MyThingHappened(BaseEvent): <fields>`. Keep the name descriptive.
2. Add it to the `Event` union so it serializes/round-trips.
3. In `apply.py`, add a `case MyThingHappened()` to the `event_apply` `match` and a dedicated
   `apply_my_thing_happened(event: MyThingHappened, state: State) -> State` returning a **new** `State`.
4. Emit the event where the fact occurs: locally (worker) via `LOCAL_EVENTS`, or as an indexed
   event broadcast by the master via `GLOBAL_EVENTS`.

## Rules (from RULES.md)

- Pydantic `FrozenModel`/`TaggedModel` (`frozen=True`, `strict=True`, `extra="forbid"`, camelCase aliases).
  Never bypass the type checker.
- Keep `apply` computationally pure. Side-effects (I/O, networking, spawning tasks) belong in injectable
  effect handlers passed into the otherwise-pure function - not inside `apply`.
- Descriptive names: no 3-letter acronyms or non-standard contractions. Use `Literal[...]` for enum-like
  sets and `NewType` for primitive IDs (see `src/wexo/shared/types/common.py`).
- Idempotency tags are a salted hash of persisted state with a **unique salt per function**, so a resumed
  node cannot re-publish the same event under a different tag.

## Testing

Tests live in `tests/` next to the code (pytest-asyncio, auto mode). `apply` transitions are pure, so
they are cheap to test directly - cover the new event and any ordering assumptions.
