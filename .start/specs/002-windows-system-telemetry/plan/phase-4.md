---
title: "Phase 4: Integration & Validation"
status: pending
version: "1.0"
phase: 4
---

# Phase 4: Integration & Validation

## Phase Context

**GATE**: Read all referenced files before starting this phase.

**Specification References**:
- `[ref: solution/Runtime View; Primary Flow, full sequence diagram]`
- `[ref: solution/Quality Requirements; Reliability]`
- `[ref: solution/Acceptance Criteria; full EARS list]`
- `[ref: requirements/Success Metrics; Key Performance Indicators]`

**Key Decisions**:
- This phase adds no new production code paths — it proves the ones built in Phases 1-3 compose correctly end-to-end and closes out the spec's documentation debt (README.md's macOS-only framing of hardware monitoring).

**Dependencies**:
- Phase 1, Phase 2, Phase 3 — all must be complete; this phase integrates their outputs.

---

## Tasks

Proves the full pipeline (Windows dispatch → GPU source layering → identity resolution → `NodeGatheredInfo` event → `apply_node_gathered_info` → `State`) works end-to-end without crashing under every degradation scenario named in requirements.md, then runs the full project quality gate and updates user-facing docs.

- [ ] **T4.1 End-to-end Windows telemetry integration test** `[activity: validate]`

  1. Prime: Read the full sequence diagram `[ref: solution/Runtime View; Primary Flow: Windows node telemetry tick]` and the Reliability quality requirement `[ref: solution/Quality Requirements; Reliability]`.
  2. Test: With `IS_WINDOWS` monkeypatched `True` and NVML/DXGI/WMI all mocked to succeed, running `InfoGatherer.run()` for one polling cycle results in a `WindowsGpuMetrics` event being applied via `apply_node_gathered_info` such that `State.node_system[node_id].vram_total` reflects the mocked value (Node A path); with NVML failing and DXGI succeeding, the same assertion holds via the DXGI path (Node B / stated AMD Radeon RX path); with both NVML and DXGI failing, `InfoGatherer.run()` completes the cycle without raising and `State.node_system` is simply not updated for that tick (Node C path) while `State.node_memory` still updates via the existing `_monitor_memory_usage` task, proving RAM telemetry is unaffected by GPU telemetry failure.
  3. Implement: Add the integration test to `src/exo/utils/info_gatherer/tests/` (or `src/exo/shared/tests/` if state-application is the focus), following the existing pytest-asyncio (`asyncio_mode = "auto"`) conventions and `EXO_TESTS=1` environment assumption per `AGENTS.md`'s Testing section.
  4. Validate: New integration test passes locally; no existing test in the suite regresses (`uv run pytest` full run, not just the new file).
  5. Success: The full Windows telemetry pipeline (gather → event → apply → state) works for the NVML-succeeds, DXGI-fallback, and all-sources-fail cases in one composed test `[ref: requirements/Success Metrics; Quality KPI — zero node-process crashes]`; RAM telemetry is demonstrably independent of GPU telemetry outcome `[ref: requirements/Feature 4; criterion 2]`.

- [ ] **T4.2 Full project quality gate and README documentation update** `[activity: validate]`

  1. Prime: Read `AGENTS.md`'s Pre-Commit Checks section and `README.md:109-118,180`'s current macOS-only framing of hardware monitoring.
  2. Test: N/A (documentation + gate task, not new behavior) — the "test" is that every existing test across the repository still passes after all three prior phases' changes.
  3. Implement: Run the full pre-commit sequence (`uv run basedpyright && uv run ruff check && nix fmt && uv run pytest`), fixing any regression surfaced by Phases 1-3's changes; add a short Windows-specific note to `README.md` alongside the existing macOS/Linux hardware-monitoring documentation (`README.md:109-118,180`) stating that Windows nodes gather GPU/VRAM telemetry via NVML/DXGI with no required external binary, mirroring the existing "macmon is macOS-only" framing but for the new Windows path.
  4. Validate: `uv run basedpyright && uv run ruff check && nix fmt && uv run pytest` all pass with zero errors on the full repository, not just this feature's files.
  5. Success: The full pre-commit gate defined in `AGENTS.md` passes `[ref: solution/Project Commands]`; README.md no longer implies Windows nodes have no hardware-monitoring story `[ref: requirements/User Journey Maps; Primary User Journey step 2]`.

- [ ] **T4.3 Final Phase Validation** `[activity: validate]`

  Confirm every acceptance criterion in `solution.md`'s Acceptance Criteria (EARS) section has a corresponding passing test from Phases 1-4, and every Gherkin criterion in `requirements.md`'s four Must-Have features is demonstrably satisfied by the shipped code. Re-run `uv run basedpyright && uv run ruff check && nix fmt && uv run pytest` one final time as the spec's definition of done.
