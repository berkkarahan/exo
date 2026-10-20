from __future__ import annotations

import errno
import os
import re
from collections import deque
from typing import Literal, final

from wexo.utils.pydantic_ext import TaggedModel

_EVIDENCE_LINES = 4

_METAL_GPU_TIMEOUT_RE = re.compile(
    r"^\s*(?:libc\+\+abi:.*std::runtime_error:\s*)?"
    r"(?P<message>\[METAL\].*GPU\s+Timeout.*)\s*$",
    re.IGNORECASE,
)
_RING_SOCKET_ERRNO_RE = re.compile(
    r"^\s*\[ring\]\s+Receiving\s+from\s+socket\s+\d+\s+failed\s+with\s+errno\s+"
    r"(?P<error_number>\d+)\s*$",
    re.IGNORECASE,
)
_RING_TRANSPORT_ABORT_RE = re.compile(
    r"^\s*\[ring\]\s+Too\s+many\s+send/recv\s+errors\.\s+Aborting\.\.\.\s*$",
    re.IGNORECASE,
)
_OPENCL_COMPILE_RE = re.compile(r"OpenCL Compile Error", re.IGNORECASE)
_OPENCL_RUNTIME_RE = re.compile(r"OpenCL Error\s+-?\d+:\s+(?P<name>CL_[A-Z0-9_]+)")
_OPENCL_ALLOCATION_NAMES = frozenset(
    {
        "CL_MEM_OBJECT_ALLOCATION_FAILURE",
        "CL_OUT_OF_RESOURCES",
        "CL_OUT_OF_HOST_MEMORY",
    }
)
_OPENCL_DEVICE_LOSS_NAMES = frozenset(
    {
        "CL_DEVICE_NOT_FOUND",
        "CL_DEVICE_NOT_AVAILABLE",
    }
)
_DEVICE_LOST_RE = re.compile(r"device lost", re.IGNORECASE)
_PROGRESS_DEADLINE_RE = re.compile(
    r"Tinygrad progress deadline: (?P<phase>compile|prefill|decode|transport) exceeded"
)

type _ProgressPhase = Literal["compile", "prefill", "decode", "transport"]


class BaseRunnerDiagnostic(TaggedModel):
    message: str
    evidence: tuple[str, ...] = ()


class RunnerMetalGpuTimeout(BaseRunnerDiagnostic):
    pass


class RunnerRingTransportError(BaseRunnerDiagnostic):
    pass


class RunnerRingSocketReceivingError(BaseRunnerDiagnostic):
    error_number: int
    error_name: str
    error_description: str


class RunnerOpenClCompileError(BaseRunnerDiagnostic):
    pass


class RunnerOpenClAllocationError(BaseRunnerDiagnostic):
    error_name: str


class RunnerOpenClDeviceLoss(BaseRunnerDiagnostic):
    error_name: str


class RunnerTinygradProgressDeadline(BaseRunnerDiagnostic):
    phase: _ProgressPhase


class RunnerUnknown(BaseRunnerDiagnostic):
    pass


KnownRunnerDiagnostic = (
    RunnerMetalGpuTimeout
    | RunnerRingTransportError
    | RunnerRingSocketReceivingError
    | RunnerOpenClCompileError
    | RunnerOpenClAllocationError
    | RunnerOpenClDeviceLoss
    | RunnerTinygradProgressDeadline
)

RunnerDiagnostic = KnownRunnerDiagnostic | RunnerUnknown


@final
class RunnerDiagnosticCollector:
    def __init__(self) -> None:
        self._stderr_tail: deque[str] = deque(maxlen=_EVIDENCE_LINES)
        self._diagnostics: list[RunnerDiagnostic] = []

    def record_line(self, line: str) -> None:
        if not line or line.isspace():
            return

        self._stderr_tail.append(line)
        evidence = tuple(self._stderr_tail)
        diagnostic = self._classify_line(line, evidence) or RunnerUnknown(
            message="Unclassified runner stderr line",
            evidence=evidence,
        )

        # TODO: Eventually this will become a stateful parser with a more advanced architecture,
        #       right now the statefulness is restricted to bespoke handling of specific errors
        #
        # `RunnerRingSocketReceivingError` usually happens a few times before `RunnerRingTransportError`
        #  therefore we deduplicate and only keep last `RunnerRingSocketReceivingError`
        if len(self._diagnostics) > 0 and (
            isinstance(self._diagnostics[-1], RunnerRingSocketReceivingError)
            and isinstance(diagnostic, RunnerRingSocketReceivingError)
        ):
            self._diagnostics[-1] = diagnostic
            return

        self._diagnostics.append(diagnostic)

    def diagnostics(self) -> tuple[RunnerDiagnostic, ...]:
        return tuple(self._diagnostics)

    def _classify_line(
        self, line: str, evidence: tuple[str, ...]
    ) -> KnownRunnerDiagnostic | None:
        if metal_error := _parse_metal_gpu_timeout(line, evidence):
            return metal_error

        if socket_error := _parse_ring_socket_error(line, evidence):
            return socket_error

        if _RING_TRANSPORT_ABORT_RE.match(line):
            return RunnerRingTransportError(
                message="Ring transport aborted after too many send/recv errors",
                evidence=evidence,
            )

        if _OPENCL_COMPILE_RE.search(line):
            return RunnerOpenClCompileError(
                message="OpenCL kernel compilation failed",
                evidence=evidence,
            )

        if runtime_error := _OPENCL_RUNTIME_RE.search(line):
            error_name = runtime_error.group("name")
            if error_name in _OPENCL_ALLOCATION_NAMES:
                return RunnerOpenClAllocationError(
                    message=f"OpenCL allocation failed: {error_name}",
                    error_name=error_name,
                    evidence=evidence,
                )
            if error_name in _OPENCL_DEVICE_LOSS_NAMES:
                return RunnerOpenClDeviceLoss(
                    message=f"OpenCL device is unavailable: {error_name}",
                    error_name=error_name,
                    evidence=evidence,
                )

        if _DEVICE_LOST_RE.search(line):
            return RunnerOpenClDeviceLoss(
                message="OpenCL device was lost",
                error_name="device lost",
                evidence=evidence,
            )

        if progress_deadline := _parse_progress_deadline(line, evidence):
            return progress_deadline

        return None


def _progress_phase(value: str) -> _ProgressPhase | None:
    if (
        value == "compile"
        or value == "prefill"
        or value == "decode"
        or value == "transport"
    ):
        return value
    return None


def _parse_progress_deadline(
    line: str, evidence: tuple[str, ...]
) -> RunnerTinygradProgressDeadline | None:
    match = _PROGRESS_DEADLINE_RE.search(line)
    if match is None:
        return None
    phase = _progress_phase(match.group("phase"))
    if phase is None:
        return None
    return RunnerTinygradProgressDeadline(
        message=f"Tinygrad {phase} progress deadline exceeded",
        phase=phase,
        evidence=evidence,
    )


def _parse_metal_gpu_timeout(
    line: str, evidence: tuple[str, ...]
) -> RunnerMetalGpuTimeout | None:
    match = _METAL_GPU_TIMEOUT_RE.match(line)
    if match is None:
        return None

    return RunnerMetalGpuTimeout(
        message=f"Metal GPU timeout: {match.group('message')}",
        evidence=evidence,
    )


def _parse_ring_socket_error(
    line: str, evidence: tuple[str, ...]
) -> RunnerRingSocketReceivingError | None:
    match = _RING_SOCKET_ERRNO_RE.match(line)
    if match is None:
        return None

    error_number = int(match.group("error_number"))
    error_name = errno.errorcode.get(error_number, "UNKNOWN_ERRNO")
    error_description = os.strerror(error_number)

    return RunnerRingSocketReceivingError(
        error_number=error_number,
        error_name=error_name,
        error_description=error_description,
        evidence=evidence,
        message=(
            f"Ring socket receive failed: errno {error_number} "
            f"{error_name} ({error_description})"
        ),
    )
