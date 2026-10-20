import subprocess
import sys
import time
from pathlib import Path

import pytest

from exo.windows.launcher import (
    CustomEnvironmentVariable,
    LauncherController,
    LauncherSettings,
    child_command,
    configured_environment,
    device_menu_label,
    exit_status,
    launch_environment,
    launcher_status,
    load_launcher_settings,
    memory_field_label,
    parse_custom_environment,
    parse_memory_limit_megabytes,
    restored_choice,
    save_launcher_settings,
    stop_process_tree,
    windows_device_choices,
)


def test_device_choices_keep_each_adapter_and_always_offer_cpu() -> None:
    choices = windows_device_choices(
        ["AMD Radeon RX 9700 XT", "NVIDIA GeForce RTX 4090", "Microsoft Basic Display"],
        has_nvidia_gpu=False,
    )
    assert [
        (choice.device_name, choice.label, choice.memory_kind) for choice in choices
    ] == [
        ("AMD", "AMD Radeon RX 9700 XT (VRAM)", "vram"),
        ("CUDA", "NVIDIA GeForce RTX 4090 (VRAM)", "vram"),
        ("CPU", "CPU (RAM)", "ram"),
    ]
    assert memory_field_label(choices[0]) == "VRAM (MB)"
    assert memory_field_label(choices[2]) == "RAM (MB)"
    assert all(choice.driver_version == "" for choice in choices)


def test_nvml_without_an_adapter_name_adds_cuda() -> None:
    choices = windows_device_choices([], has_nvidia_gpu=True)
    assert [choice.device_name for choice in choices] == ["CUDA", "CPU"]
    assert choices[0].label == "CUDA (VRAM)"


def test_no_accelerator_offers_only_cpu() -> None:
    choices = windows_device_choices(
        ["Microsoft Basic Display Adapter"],
        has_nvidia_gpu=False,
    )
    assert [choice.device_name for choice in choices] == ["CPU"]


def test_launch_environment_sets_device_and_memory_limit() -> None:
    environment = launch_environment(
        {"PATH": "/usr/bin", "OVERRIDE_MEMORY_MB": "1"},
        "AMD",
        14000,
    )
    assert environment["PATH"] == "/usr/bin"
    assert environment["EXO_TINYGRAD_DEVICES"] == "AMD"
    assert environment["OVERRIDE_MEMORY_MB"] == "14000"


def test_blank_memory_limit_drops_a_stale_override() -> None:
    assert parse_memory_limit_megabytes("  ") is None
    environment = launch_environment(
        {"OVERRIDE_MEMORY_MB": "14000"},
        "CPU",
        None,
    )
    assert environment["EXO_TINYGRAD_DEVICES"] == "CPU"
    assert "OVERRIDE_MEMORY_MB" not in environment


def test_memory_limit_below_one_is_rejected() -> None:
    with pytest.raises(ValueError, match="positive number of megabytes"):
        launch_environment({}, "CUDA", 0)
    with pytest.raises(ValueError, match="positive number of megabytes"):
        parse_memory_limit_megabytes("0")
    with pytest.raises(ValueError, match="positive number of megabytes"):
        parse_memory_limit_megabytes("nope")


def test_exit_status_keeps_the_import_error() -> None:
    assert exit_status(0, ["ready"]) == "exited 0"
    assert exit_status(1, ["ready", "No module named exo_rs"]) == (
        "exited 1: No module named exo_rs"
    )


def test_restored_choice_keeps_the_saved_adapter_label() -> None:
    choices = windows_device_choices(
        ["AMD Radeon(TM) Graphics", "AMD Radeon RX 9070 XT"],
        has_nvidia_gpu=False,
    )
    saved = LauncherSettings(
        device_name="AMD",
        device_label="AMD Radeon RX 9070 XT (VRAM)",
        memory_limit_megabytes=14000,
    )
    choice, memory_text = restored_choice(choices, saved)
    assert choice.label == "AMD Radeon RX 9070 XT (VRAM)"
    assert memory_text == "14000"


def test_missing_saved_label_falls_back_to_the_same_device_name() -> None:
    choices = windows_device_choices(
        ["AMD Radeon RX 9070 XT"],
        has_nvidia_gpu=False,
    )
    saved = LauncherSettings(
        device_name="AMD",
        device_label="AMD Radeon(TM) Graphics (VRAM)",
        memory_limit_megabytes=None,
    )
    choice, memory_text = restored_choice(choices, saved)
    assert choice.device_name == "AMD"
    assert choice.label == "AMD Radeon RX 9070 XT (VRAM)"
    assert memory_text == ""


def test_corrupt_settings_are_ignored(tmp_path: Path) -> None:
    path = tmp_path / "windows-launcher.json"
    _ = path.write_text("{", encoding="utf-8")
    assert load_launcher_settings(path) is None


def test_driver_version_is_kept_when_one_opencl_version_matches() -> None:
    choices = windows_device_choices(
        ["AMD Radeon(TM) Graphics", "AMD Radeon RX 9070 XT"],
        has_nvidia_gpu=False,
        driver_versions=(
            ("AMD Radeon(TM) Graphics", "3679.0"),
            ("AMD Radeon RX 9070 XT", "3679.0"),
            ("AMD Radeon RX 9070 XT", "3679.0"),
        ),
    )
    integrated, discrete, cpu = choices
    assert integrated.driver_version == "3679.0"
    assert discrete.driver_version == "3679.0"
    assert cpu.driver_version == ""
    assert device_menu_label(discrete) == "AMD Radeon RX 9070 XT (VRAM) — 3679.0"
    saved = LauncherSettings(
        device_name="AMD",
        device_label="AMD Radeon RX 9070 XT (VRAM)",
        memory_limit_megabytes=14000,
    )
    restored, _memory_text = restored_choice(choices, saved)
    assert restored.label == discrete.label
    assert restored.driver_version == "3679.0"


def test_disagreeing_driver_versions_are_omitted() -> None:
    choices = windows_device_choices(
        ["AMD Radeon RX 9070 XT"],
        has_nvidia_gpu=False,
        driver_versions=(
            ("AMD Radeon RX 9070 XT", "3679.0"),
            ("amd radeon rx 9070 xt", "3600.0"),
        ),
    )
    assert choices[0].driver_version == ""
    assert device_menu_label(choices[0]) == "AMD Radeon RX 9070 XT (VRAM)"


def test_status_includes_the_driver_version() -> None:
    process = _sleeper()
    try:
        running = launcher_status(
            process=process,
            output_lines=[],
            validation_message=None,
            device_label="AMD Radeon RX 9070 XT (VRAM)",
            api_reachable=None,
            stopped_by_user=False,
            driver_version="3679.0",
        )
        assert running.device == "AMD Radeon RX 9070 XT (VRAM) (3679.0)"
        assert "device: AMD Radeon RX 9070 XT (VRAM) (3679.0)" in running.line()
    finally:
        _ = stop_process_tree(process)


def test_status_separates_process_api_and_device() -> None:
    process = _sleeper()
    try:
        running = launcher_status(
            process=process,
            output_lines=[],
            validation_message=None,
            device_label="CPU (RAM)",
            api_reachable=True,
            stopped_by_user=False,
        )
        assert running.process == "running"
        assert running.api == "up"
        assert running.device == "CPU (RAM)"
        assert "process: running" in running.line()
        _ = stop_process_tree(process)
        stopped = launcher_status(
            process=process,
            output_lines=[],
            validation_message=None,
            device_label="CPU (RAM)",
            api_reachable=True,
            stopped_by_user=True,
        )
        assert stopped.process == "stopped"
        assert stopped.api == "not checked"
    finally:
        if process.poll() is None:
            _ = stop_process_tree(process)


def test_invalid_memory_does_not_start(tmp_path: Path) -> None:
    controller = LauncherController(_reject_start)
    status = controller.start("CPU", "nope", "CPU (RAM)", tmp_path / "settings.json")
    assert "positive number" in status.process
    assert load_launcher_settings(tmp_path / "settings.json") is None


def test_stop_and_restart_replace_the_child(tmp_path: Path) -> None:
    started: list[str] = []

    def starter(
        device_name: str, memory_limit_megabytes: int | None
    ) -> subprocess.Popen[str]:
        started.append(device_name)
        _ = memory_limit_megabytes
        return _sleeper()

    controller = LauncherController(starter, device_label="CPU (RAM)")
    path = tmp_path / "settings.json"
    try:
        assert controller.start("CPU", "512", "CPU (RAM)", path).process == "running"
        saved = load_launcher_settings(path)
        assert saved is not None
        assert saved.memory_limit_megabytes == 512
        assert saved.device_label == "CPU (RAM)"
        assert controller.start("AMD", "1", "other", path).process == "running"
        assert started == ["CPU"]
        assert controller.stop().process == "stopped"
        restarted = controller.restart(
            "AMD",
            "",
            "AMD Radeon RX 9070 XT (VRAM)",
            path,
        )
        assert restarted.process == "running"
        assert started == ["CPU", "AMD"]
        assert controller.recent_log() == ""
    finally:
        _ = controller.stop()


@pytest.mark.skipif(sys.platform != "win32", reason="taskkill tree stop is Windows")
def test_stop_process_tree_ends_a_child(tmp_path: Path) -> None:
    child_pid_path = tmp_path / "child.pid"
    parent = subprocess.Popen(
        [
            sys.executable,
            "-c",
            (
                "import subprocess, sys, time\n"
                "from pathlib import Path\n"
                "child = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(120)'])\n"
                "Path(sys.argv[1]).write_text(str(child.pid), encoding='utf-8')\n"
                "time.sleep(120)\n"
            ),
            str(child_pid_path),
        ],
        text=True,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    try:
        deadline = time.time() + 5
        while time.time() < deadline and not child_pid_path.is_file():
            time.sleep(0.05)
        child_pid = int(child_pid_path.read_text(encoding="utf-8"))
        assert _windows_pid_is_running(child_pid)
        _ = stop_process_tree(parent)
        assert parent.poll() is not None
        assert not _windows_pid_is_running(child_pid)
    finally:
        if parent.poll() is None:
            _ = stop_process_tree(parent)


def _sleeper() -> subprocess.Popen[str]:
    return subprocess.Popen(
        [sys.executable, "-c", "import time; time.sleep(30)"],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )


def _reject_start(
    device_name: str,
    memory_limit_megabytes: int | None,
) -> subprocess.Popen[str]:
    _ = device_name, memory_limit_megabytes
    raise AssertionError("launcher started a process")


def test_saved_settings_round_trip_the_macos_fields(tmp_path: Path) -> None:
    settings = _macos_style_settings()
    path = tmp_path / "windows-launcher.json"
    save_launcher_settings(path, settings)
    assert load_launcher_settings(path) == settings


def test_configured_environment_matches_the_macos_app() -> None:
    environment = configured_environment(
        {"PATH": "C:\\Windows", "HF_TOKEN": "stale", "EXO_OFFLINE": "true"},
        _macos_style_settings(),
    )
    assert environment["PATH"] == "C:\\Windows"
    assert environment["EXO_TINYGRAD_DEVICES"] == "AMD"
    assert environment["OVERRIDE_MEMORY_MB"] == "14000"
    assert environment["EXO_ZENOH_NAMESPACE"] == "lab"
    assert environment["HF_TOKEN"] == "hf_test"
    assert environment["HF_ENDPOINT"] == "https://hf-mirror.com"
    assert environment["EXO_OFFLINE"] == "true"
    assert environment["EXO_ENABLE_IMAGE_MODELS"] == "true"
    assert "EXO_FAST_SYNCH" not in environment
    assert environment["EXO_DEFAULT_MODELS_DIR"] == "D:/models"
    assert environment["EXO_MODELS_DIRS"] == "D:/extra"
    assert environment["EXO_MODELS_READ_ONLY_DIRS"] == "D:/ro"
    assert environment["EXO_CUSTOM"] == "kept"


def test_blank_macos_fields_clear_parent_environment_values() -> None:
    environment = configured_environment(
        {
            "HF_TOKEN": "stale",
            "HF_ENDPOINT": "https://example.invalid",
            "EXO_OFFLINE": "true",
            "EXO_ENABLE_IMAGE_MODELS": "true",
            "EXO_ZENOH_NAMESPACE": "old",
            "EXO_DEFAULT_MODELS_DIR": "D:/old",
        },
        LauncherSettings(device_name="CPU", device_label="CPU (RAM)"),
    )
    assert environment["EXO_TINYGRAD_DEVICES"] == "CPU"
    assert "EXO_FAST_SYNCH" not in environment
    for name in (
        "HF_TOKEN",
        "HF_ENDPOINT",
        "EXO_OFFLINE",
        "EXO_ENABLE_IMAGE_MODELS",
        "EXO_ZENOH_NAMESPACE",
        "EXO_DEFAULT_MODELS_DIR",
        "OVERRIDE_MEMORY_MB",
    ):
        assert name not in environment


def test_custom_environment_keeps_the_later_value() -> None:
    parsed = parse_custom_environment("A=1\nnot valid\nA=2\n# comment\n1BAD=x\nB=\n")
    assert [(item.key, item.value) for item in parsed] == [("A", "2"), ("B", "")]


def test_child_command_reinvokes_a_frozen_executable() -> None:
    settings = _macos_style_settings()
    assert child_command("exo.exe", settings, frozen=True) == [
        "exo.exe",
        "--exo-runtime",
        "--namespace",
        "lab",
        "--offline",
    ]
    plain = settings.model_copy(
        update={"cluster_namespace": "  ", "offline_mode": False}
    )
    assert child_command("python.exe", plain, frozen=False) == [
        "python.exe",
        "-m",
        "exo",
    ]


def test_start_keeps_macos_fields_in_the_saved_file(tmp_path: Path) -> None:
    controller = LauncherController(_sleeper_starter)
    path = tmp_path / "settings.json"
    try:
        status = controller.start(
            "CPU",
            "512",
            "CPU (RAM)",
            path,
            app_settings=_macos_style_settings(),
        )
        assert status.process == "running"
        loaded = load_launcher_settings(path)
        assert loaded is not None
        assert loaded.cluster_namespace == "lab"
        assert loaded.hugging_face_token == "hf_test"
        assert loaded.memory_limit_megabytes == 512
        assert loaded.device_name == "CPU"
    finally:
        _ = controller.stop()


@pytest.mark.skipif(sys.platform != "win32", reason="Windows settings window")
def test_settings_window_lists_the_macos_tabs() -> None:
    import tkinter as tk

    from exo.windows.launcher import windows_device_choices as choices_for
    from exo.windows.shell import SettingsPanel, settings_tab_titles

    root = tk.Tk()
    root.withdraw()
    try:
        panel = SettingsPanel(
            root,
            choices_for(["AMD Radeon RX 9070 XT"], has_nvidia_gpu=False),
            _macos_style_settings(),
            "14000",
            "test",
        )
        assert panel.tab_titles() == settings_tab_titles()
        saved, memory_text = panel.saved_settings(_macos_style_settings(), "General")
        assert saved.cluster_namespace == "lab"
        assert saved.hugging_face_token == "hf_test"
        assert memory_text == "14000"
        model_settings, _memory = panel.saved_settings(_macos_style_settings(), "Model")
        assert model_settings.enable_image_models is True
    finally:
        root.destroy()


def test_taskbar_menu_includes_exit() -> None:
    from exo.windows.taskbar import command_for_menu_id, taskbar_menu_labels

    labels = taskbar_menu_labels()
    assert "Open Dashboard" in labels
    assert "Settings" in labels
    assert labels[-1] == "Exit EXO"
    assert command_for_menu_id(len(labels)) == "exit"
    assert command_for_menu_id(0) == ""


@pytest.mark.skipif(sys.platform != "win32", reason="taskbar icon is Windows")
def test_taskbar_icon_installs_and_removes() -> None:
    from exo.windows.taskbar import TaskbarIcon

    icon = TaskbarIcon()
    assert icon.install(Path("missing.ico"), "EXO", lambda _command: None)
    icon.update_tooltip("EXO — Running")
    icon.remove()


def _macos_style_settings() -> LauncherSettings:
    return LauncherSettings(
        device_name="AMD",
        device_label="AMD Radeon RX 9070 XT (VRAM)",
        memory_limit_megabytes=14000,
        cluster_namespace="lab",
        hugging_face_token="hf_test",
        hugging_face_endpoint="https://hf-mirror.com",
        offline_mode=True,
        enable_image_models=True,
        default_models_directory="D:/models",
        additional_models_directories="D:/extra",
        read_only_models_directories="D:/ro",
        custom_environment_variables=(
            CustomEnvironmentVariable(key="EXO_CUSTOM", value="kept"),
        ),
    )


def _sleeper_starter(
    device_name: str,
    memory_limit_megabytes: int | None,
) -> subprocess.Popen[str]:
    _ = device_name, memory_limit_megabytes
    return _sleeper()


def _windows_pid_is_running(pid: int) -> bool:
    completed = subprocess.run(
        ["tasklist", "/FI", f"PID eq {pid}", "/NH"],
        check=False,
        capture_output=True,
        text=True,
    )
    return str(pid) in completed.stdout
