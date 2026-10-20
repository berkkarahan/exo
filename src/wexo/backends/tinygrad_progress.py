"""Progress budgets for one tinygrad runner.

Compile, prefill, decode, and pipeline transport each have a limit. The
engine and the pipeline transports compare an injected clock with
``progress_is_overdue`` and raise ``TinygradProgressDeadlineError`` when a phase
stops making progress.
"""

from __future__ import annotations

from typing import Literal, final

from pydantic import Field

from wexo.utils.pydantic_ext import FrozenModel

type TinygradProgressPhase = Literal["compile", "prefill", "decode", "transport"]


@final
class TinygradProgressDeadlineError(Exception):
    """Raised when a tinygrad phase exceeds its progress budget.

    ``exo.worker.runner.bootstrap.entrypoint`` handles this by publishing
    ``RunnerTerminationError``. A stderr line containing the message is
    classified as ``RunnerTinygradProgressDeadline``.
    """

    def __init__(self, phase: TinygradProgressPhase, budget_seconds: float) -> None:
        self.phase: TinygradProgressPhase = phase
        self.budget_seconds = budget_seconds
        super().__init__(
            f"Tinygrad progress deadline: {phase} exceeded {budget_seconds:g} seconds"
        )


@final
class TinygradProgressBudgets(FrozenModel):
    """Seconds allowed for each tinygrad phase before the runner stops."""

    compile_seconds: float = Field(gt=0)
    prefill_seconds: float = Field(gt=0)
    decode_seconds: float = Field(gt=0)
    transport_seconds: float = Field(gt=0)


DEFAULT_TINYGRAD_PROGRESS_BUDGETS = TinygradProgressBudgets(
    compile_seconds=600.0,
    prefill_seconds=120.0,
    decode_seconds=60.0,
    transport_seconds=30.0,
)


def progress_budget_seconds(
    budgets: TinygradProgressBudgets, phase: TinygradProgressPhase
) -> float:
    """Return the limit for ``phase``."""
    if phase == "compile":
        return budgets.compile_seconds
    if phase == "prefill":
        return budgets.prefill_seconds
    if phase == "decode":
        return budgets.decode_seconds
    return budgets.transport_seconds


def progress_is_overdue(started_at: float, now: float, budget_seconds: float) -> bool:
    """Return whether ``now`` is more than ``budget_seconds`` after ``started_at``."""
    return now - started_at > budget_seconds
