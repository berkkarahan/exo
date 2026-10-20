from wexo.worker.runner.diagnostics import (
    RunnerDiagnosticCollector,
    RunnerMetalGpuTimeout,
    RunnerOpenClAllocationError,
    RunnerOpenClCompileError,
    RunnerOpenClDeviceLoss,
    RunnerRingTransportError,
    RunnerTinygradProgressDeadline,
    RunnerUnknown,
)


def test_opencl_compile_error_is_classified() -> None:
    collector = RunnerDiagnosticCollector()

    collector.record_line("CompileError: OpenCL Compile Error")

    assert isinstance(collector.diagnostics()[-1], RunnerOpenClCompileError)


def test_opencl_allocation_errors_are_classified() -> None:
    collector = RunnerDiagnosticCollector()
    collector.record_line(
        "RuntimeError: OpenCL Error -4: CL_MEM_OBJECT_ALLOCATION_FAILURE"
    )
    collector.record_line("RuntimeError: OpenCL Error -5: CL_OUT_OF_RESOURCES")
    collector.record_line("RuntimeError: OpenCL Error -6: CL_OUT_OF_HOST_MEMORY")

    names = [
        item.error_name
        for item in collector.diagnostics()
        if isinstance(item, RunnerOpenClAllocationError)
    ]
    assert names == [
        "CL_MEM_OBJECT_ALLOCATION_FAILURE",
        "CL_OUT_OF_RESOURCES",
        "CL_OUT_OF_HOST_MEMORY",
    ]


def test_opencl_device_loss_is_classified() -> None:
    collector = RunnerDiagnosticCollector()
    collector.record_line("RuntimeError: OpenCL Error -2: CL_DEVICE_NOT_AVAILABLE")
    collector.record_line("amdpal: device lost while submitting")

    first, second = collector.diagnostics()
    assert isinstance(first, RunnerOpenClDeviceLoss)
    assert first.error_name == "CL_DEVICE_NOT_AVAILABLE"
    assert isinstance(second, RunnerOpenClDeviceLoss)
    assert second.error_name == "device lost"


def test_other_opencl_errors_stay_unclassified() -> None:
    collector = RunnerDiagnosticCollector()

    collector.record_line("RuntimeError: OpenCL Error -48: CL_INVALID_KERNEL")

    assert isinstance(collector.diagnostics()[-1], RunnerUnknown)


def test_metal_and_ring_diagnostics_still_classify() -> None:
    collector = RunnerDiagnosticCollector()
    collector.record_line("[METAL] GPU Timeout after 10s")
    collector.record_line("[ring] Too many send/recv errors. Aborting...")

    first, second = collector.diagnostics()
    assert isinstance(first, RunnerMetalGpuTimeout)
    assert isinstance(second, RunnerRingTransportError)


def test_tinygrad_progress_deadline_is_classified() -> None:
    collector = RunnerDiagnosticCollector()

    collector.record_line(
        "TinygradProgressDeadlineError: Tinygrad progress deadline: prefill exceeded 1 seconds"
    )

    diagnostic = collector.diagnostics()[-1]
    assert isinstance(diagnostic, RunnerTinygradProgressDeadline)
    assert diagnostic.phase == "prefill"
