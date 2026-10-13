"""Windows window that starts exo with a device and a memory limit.

The Mac app injects settings through the child environment. This launcher
does the same for ``EXO_TINYGRAD_DEVICES`` and ``OVERRIDE_MEMORY_MB``.
"""

from __future__ import annotations

import http.client
import os
import subprocess
import sys
import time
import urllib.parse
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from typing import Literal, final

from pydantic import ValidationError

from exo.backends.tinygrad_engine import windows_backend_for_adapter_name
from exo.shared.constants import EXO_CONFIG_HOME
from exo.shared.types.backends import Backend
from exo.utils.pydantic_ext import FrozenModel

type WindowsDeviceName = Literal["AMD", "CUDA", "CPU"]
type MemoryKind = Literal["vram", "ram"]


@final
class WindowsDeviceChoice(FrozenModel):
    """One row in the device dropdown.

    ``device_name`` is the value written to ``EXO_TINYGRAD_DEVICES``.
    ``memory_kind`` selects the megabyte label: VRAM for a GPU, RAM for CPU.
    """

    device_name: WindowsDeviceName
    label: str
    memory_kind: MemoryKind
    driver_version: str = ""


def driver_version_for_adapter_name(
    adapter_name: str,
    driver_versions: Sequence[tuple[str, str]],
) -> str:
    """Return the OpenCL driver for ``adapter_name``.

    Every matching device name must report the same version. A missing match
    or two different versions returns an empty string.
    """
    stripped = adapter_name.strip().casefold()
    versions = {
        version.strip()
        for name, version in driver_versions
        if name.strip().casefold() == stripped and version.strip() != ""
    }
    if len(versions) != 1:
        return ""
    version = next(iter(versions))
    return version


def device_menu_label(choice: WindowsDeviceChoice) -> str:
    """Return the dropdown caption, including the driver when it is known."""
    if choice.driver_version.strip() == "":
        return choice.label
    return f"{choice.label} — {choice.driver_version.strip()}"


def device_status_text(label: str, driver_version: str) -> str:
    """Return the status device line."""
    stripped = driver_version.strip()
    if stripped == "":
        return label
    return f"{label} ({stripped})"


def windows_device_choices(
    adapter_names: Sequence[str],
    has_nvidia_gpu: bool,
    driver_versions: Sequence[tuple[str, str]] = (),
) -> list[WindowsDeviceChoice]:
    """List the devices the launcher can start.

    Each AMD or NVIDIA adapter is its own row, labeled with the adapter name
    and VRAM. NVML with no NVIDIA name adds one CUDA row. CPU is always last
    and labeled RAM, so a GPU machine can still join as ``WinCPU``.
    """
    choices: list[WindowsDeviceChoice] = []
    saw_cuda = False
    for adapter_name in adapter_names:
        stripped_name = adapter_name.strip()
        if stripped_name == "":
            continue
        identity = windows_backend_for_adapter_name(stripped_name)
        if identity is Backend.WinAMD:
            choices.append(
                WindowsDeviceChoice(
                    device_name="AMD",
                    label=f"{stripped_name} (VRAM)",
                    memory_kind="vram",
                    driver_version=driver_version_for_adapter_name(
                        stripped_name, driver_versions
                    ),
                )
            )
        elif identity is Backend.WinCUDA:
            saw_cuda = True
            choices.append(
                WindowsDeviceChoice(
                    device_name="CUDA",
                    label=f"{stripped_name} (VRAM)",
                    memory_kind="vram",
                    driver_version=driver_version_for_adapter_name(
                        stripped_name, driver_versions
                    ),
                )
            )
    if has_nvidia_gpu and not saw_cuda:
        choices.append(
            WindowsDeviceChoice(
                device_name="CUDA",
                label="CUDA (VRAM)",
                memory_kind="vram",
            )
        )
    choices.append(
        WindowsDeviceChoice(
            device_name="CPU",
            label="CPU (RAM)",
            memory_kind="ram",
        )
    )
    return choices


def memory_field_label(choice: WindowsDeviceChoice) -> str:
    """Return the megabyte caption for the selected device."""
    if choice.memory_kind == "vram":
        return "VRAM (MB)"
    return "RAM (MB)"


def parse_memory_limit_megabytes(text: str) -> int | None:
    """Parse the memory box.

    A blank box returns ``None`` so the existing probe is left unchanged.

    Raises:
        ValueError: The window shows this on the status line when the text
            is not a positive number of megabytes.
    """
    stripped = text.strip()
    if stripped == "":
        return None
    if not stripped.isdecimal():
        raise ValueError("Memory limit must be a positive number of megabytes")
    return _require_positive_megabytes(int(stripped))


def launch_environment(
    base: Mapping[str, str],
    device_name: WindowsDeviceName,
    memory_limit_megabytes: int | None,
) -> dict[str, str]:
    """Return the environment for the exo child.

    ``device_name`` becomes ``EXO_TINYGRAD_DEVICES``. A positive memory limit
    becomes ``OVERRIDE_MEMORY_MB``. ``None`` removes that variable so a blank
    box does not keep a stale override from the parent.

    Raises:
        ValueError: The window shows this on the status line when
            ``memory_limit_megabytes`` is below 1.
    """
    environment = dict(base)
    environment["EXO_TINYGRAD_DEVICES"] = device_name
    if memory_limit_megabytes is None:
        environment.pop("OVERRIDE_MEMORY_MB", None)
    else:
        environment["OVERRIDE_MEMORY_MB"] = str(
            _require_positive_megabytes(memory_limit_megabytes)
        )
    return environment


def exit_status(exit_code: int, output_lines: Sequence[str]) -> str:
    """Return the status line after the child leaves.

    A non-zero exit keeps the last output line so a missing extension is
    visible. A clean exit shows only the code.
    """
    if exit_code != 0 and output_lines:
        return f"exited {exit_code}: {output_lines[-1]}"
    return f"exited {exit_code}"


@final
class CustomEnvironmentVariable(FrozenModel):
    """One user-defined variable injected into the exo child."""

    key: str
    value: str


@final
class LauncherSettings(FrozenModel):
    """Settings restored the next time the Windows shell opens.

    The device row is the Windows equivalent of picking the accelerator.
    The other fields match the macOS settings window and are passed to the
    child the same way that app injects them.
    """

    device_name: WindowsDeviceName
    device_label: str
    memory_limit_megabytes: int | None = None
    cluster_namespace: str = ""
    hugging_face_token: str = ""
    hugging_face_endpoint: str = ""
    offline_mode: bool = False
    enable_image_models: bool = False
    fast_synch_enabled: bool = False
    default_models_directory: str = ""
    additional_models_directories: str = ""
    read_only_models_directories: str = ""
    custom_environment_variables: tuple[CustomEnvironmentVariable, ...] = ()


class LauncherStatus(FrozenModel):
    """Process, API, and device lines for the running exo child."""

    process: str
    api: str
    device: str

    def line(self) -> str:
        return f"process: {self.process}\napi: {self.api}\ndevice: {self.device}"


def default_launcher_settings_path() -> Path:
    """Return the JSON file that stores the last successful start."""
    return EXO_CONFIG_HOME / "windows-launcher.json"


def load_launcher_settings(path: Path) -> LauncherSettings | None:
    """Read saved launcher settings.

    A missing or unreadable file returns ``None`` so the window opens on the
    first device row. ``ValidationError`` from a corrupt file is that case.
    """
    if not path.is_file():
        return None
    try:
        return LauncherSettings.model_validate_json(path.read_text(encoding="utf-8"))
    except ValidationError:
        return None


def is_environment_variable_name(key: str) -> bool:
    """Return whether ``key`` is a POSIX environment variable name."""
    if key == "":
        return False
    first = key[0]
    if not first.isascii() or not (first.isalpha() or first == "_"):
        return False
    return all(
        character.isascii() and (character.isalnum() or character == "_")
        for character in key[1:]
    )


def parse_custom_environment(text: str) -> tuple[CustomEnvironmentVariable, ...]:
    """Parse ``KEY=value`` lines into custom environment variables.

    Blank lines and names that are not POSIX identifiers are skipped. When a
    key is repeated, the later value replaces the earlier one.
    """
    selected: dict[str, CustomEnvironmentVariable] = {}
    order: list[str] = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if line == "" or line.startswith("#"):
            continue
        key, separator, value = line.partition("=")
        stripped_key = key.strip()
        if separator == "" or not is_environment_variable_name(stripped_key):
            continue
        if stripped_key not in selected:
            order.append(stripped_key)
        selected[stripped_key] = CustomEnvironmentVariable(
            key=stripped_key,
            value=value,
        )
    return tuple(selected[key] for key in order)


def custom_environment_text(
    variables: Sequence[CustomEnvironmentVariable],
) -> str:
    """Return the settings text box contents for ``variables``."""
    return "\n".join(f"{variable.key}={variable.value}" for variable in variables)


def _set_or_clear(environment: dict[str, str], name: str, value: str) -> None:
    stripped = value.strip()
    if stripped == "":
        environment.pop(name, None)
        return
    environment[name] = stripped


def configured_environment(
    base: Mapping[str, str],
    settings: LauncherSettings,
) -> dict[str, str]:
    """Return the child environment for a settings panel save.

    Device and memory follow ``launch_environment``. Namespace, tokens,
    offline mode, image models, fast synch, and model directories match the
    variables the macOS app writes. Custom variables are applied last so they
    can override those fields.

    Raises:
        ValueError: ``launch_environment`` raises when the memory limit is
            below 1. The settings window shows that on the status line.
    """
    environment = launch_environment(
        base,
        settings.device_name,
        settings.memory_limit_megabytes,
    )
    _set_or_clear(environment, "EXO_ZENOH_NAMESPACE", settings.cluster_namespace)
    _set_or_clear(environment, "HF_TOKEN", settings.hugging_face_token)
    _set_or_clear(environment, "HF_ENDPOINT", settings.hugging_face_endpoint)
    if settings.offline_mode:
        environment["EXO_OFFLINE"] = "true"
    else:
        environment.pop("EXO_OFFLINE", None)
    if settings.enable_image_models:
        environment["EXO_ENABLE_IMAGE_MODELS"] = "true"
    else:
        environment.pop("EXO_ENABLE_IMAGE_MODELS", None)
    environment["EXO_FAST_SYNCH"] = "true" if settings.fast_synch_enabled else "false"
    _set_or_clear(
        environment,
        "EXO_DEFAULT_MODELS_DIR",
        settings.default_models_directory,
    )
    _set_or_clear(
        environment,
        "EXO_MODELS_DIRS",
        settings.additional_models_directories,
    )
    _set_or_clear(
        environment,
        "EXO_MODELS_READ_ONLY_DIRS",
        settings.read_only_models_directories,
    )
    for variable in settings.custom_environment_variables:
        if is_environment_variable_name(variable.key):
            environment[variable.key] = variable.value
    return environment


def child_command(
    executable: str,
    settings: LauncherSettings,
    *,
    frozen: bool,
) -> list[str]:
    """Return the argv used to start the exo runtime.

    A frozen Windows executable re-invokes itself with ``--exo-runtime`` so
    the taskbar shell and the server can share one binary. A source checkout
    uses ``python -m exo``. A non-empty namespace and offline mode are passed
    as arguments because those settings are not read from the environment.
    """
    command = [executable]
    if frozen:
        command.append("--exo-runtime")
    else:
        command.extend(["-m", "exo"])
    namespace = settings.cluster_namespace.strip()
    if namespace != "":
        command.extend(["--namespace", namespace])
    if settings.offline_mode:
        command.append("--offline")
    return command


def running_as_frozen_executable() -> bool:
    """Return whether this process is the PyInstaller executable."""
    return bool(getattr(sys, "frozen", False))


def save_launcher_settings(path: Path, settings: LauncherSettings) -> None:
    """Write the settings chosen by a successful start or Save & Restart."""
    path.parent.mkdir(parents=True, exist_ok=True)
    _ = path.write_text(settings.model_dump_json(), encoding="utf-8")


def restored_choice(
    choices: Sequence[WindowsDeviceChoice],
    saved: LauncherSettings | None,
) -> tuple[WindowsDeviceChoice, str]:
    """Return the dropdown row and memory text to show.

    The saved label wins when that adapter is still present. Otherwise a row
    with the same device name is used, then the first row.

    Raises:
        ValueError: ``open_launcher`` handles this by refusing to open when
            the probe produced no device rows.
    """
    if len(choices) == 0:
        raise ValueError("the launcher needs at least one device")
    if saved is None:
        return choices[0], ""
    memory_text = (
        ""
        if saved.memory_limit_megabytes is None
        else str(saved.memory_limit_megabytes)
    )
    for choice in choices:
        if (
            choice.label == saved.device_label
            and choice.device_name == saved.device_name
        ):
            return choice, memory_text
    for choice in choices:
        if choice.device_name == saved.device_name:
            return choice, memory_text
    return choices[0], ""


def launcher_status(
    *,
    process: subprocess.Popen[str] | None,
    output_lines: Sequence[str],
    validation_message: str | None,
    device_label: str,
    api_reachable: bool | None,
    stopped_by_user: bool,
    driver_version: str = "",
) -> LauncherStatus:
    """Describe the launcher without reading the network or the process tree."""
    exit_code = None if process is None else process.poll()
    if validation_message is not None:
        process_text = validation_message
    elif process is None or (stopped_by_user and exit_code is not None):
        process_text = "stopped"
    elif exit_code is None:
        process_text = "running"
    else:
        process_text = exit_status(exit_code, output_lines)
    if exit_code is not None or process is None or api_reachable is None:
        api_text = "not checked"
    elif api_reachable:
        api_text = "up"
    else:
        api_text = "down"
    return LauncherStatus(
        process=process_text,
        api=api_text,
        device=device_status_text(device_label, driver_version),
    )


def api_is_reachable(
    url: str = "http://127.0.0.1:52416/state",
    timeout_seconds: float = 0.2,
) -> bool:
    """Return whether the local exo API answered.

    ``OSError`` and ``TimeoutError`` are reported as unreachable. The status
    line shows that as ``api: down`` while the child process is still running.
    """
    parsed = urllib.parse.urlparse(url)
    host = parsed.hostname or "127.0.0.1"
    port = parsed.port or 80
    path = parsed.path or "/"
    connection = http.client.HTTPConnection(host, port, timeout=timeout_seconds)
    try:
        connection.request("GET", path)
        return connection.getresponse().status == 200
    except (OSError, TimeoutError):
        return False
    finally:
        connection.close()


def stop_process_tree(
    process: subprocess.Popen[str], *, wait_seconds: float = 5
) -> int:
    """End ``process`` and the processes it started.

    On Windows ``taskkill /T /F`` ends the tree. A parent-only terminate would
    leave runner children. Other platforms terminate the process itself.

    Raises:
        subprocess.TimeoutExpired: The process was still alive after terminate
            and kill. The launcher leaves that exception visible.
    """
    if process.poll() is not None:
        return process.returncode if process.returncode is not None else 0
    if sys.platform == "win32":
        _ = subprocess.run(
            ["taskkill", "/T", "/F", "/PID", str(process.pid)],
            check=False,
            capture_output=True,
            text=True,
        )
    else:
        process.terminate()
    try:
        return process.wait(timeout=wait_seconds)
    except subprocess.TimeoutExpired:
        process.kill()
        return process.wait(timeout=wait_seconds)


@final
class LauncherController:
    """Start, stop, and describe one exo child."""

    def __init__(
        self,
        start_process: Callable[[WindowsDeviceName, int | None], subprocess.Popen[str]],
        *,
        api_probe: Callable[[], bool] | None = None,
        device_label: str = "",
        driver_version: str = "",
    ) -> None:
        self._start_process = start_process
        self._api_probe = api_probe
        self._process: subprocess.Popen[str] | None = None
        self._output: list[str] = []
        self._validation_message: str | None = None
        self._device_label = device_label
        self._driver_version = driver_version
        self._stopped_by_user = False
        self._api_reachable: bool | None = None
        self._api_checked_at = 0.0

    def current_process(self) -> subprocess.Popen[str] | None:
        return self._process

    def is_running(self) -> bool:
        return self._process is not None and self._process.poll() is None

    def note_output_line(self, line: str) -> None:
        self._output.append(line)
        del self._output[:-20]

    def recent_log(self) -> str:
        return "\n".join(self._output)

    def start(
        self,
        device_name: WindowsDeviceName,
        memory_text: str,
        device_label: str,
        settings_path: Path,
        driver_version: str = "",
        app_settings: LauncherSettings | None = None,
    ) -> LauncherStatus:
        """Spawn exo and remember the settings panel.

        A child that is already running is left in place. ``ValueError`` from
        the memory box and ``OSError`` from spawning become the process line.
        ``app_settings`` keeps the macOS-style fields; the device row and
        memory box replace those two values.
        """
        if self.is_running():
            return self.status()
        self._device_label = device_label
        self._driver_version = driver_version
        try:
            memory_limit = parse_memory_limit_megabytes(memory_text)
        except ValueError as error:
            self._validation_message = str(error)
            return self.status()
        self._validation_message = None
        self._stopped_by_user = False
        self._output.clear()
        self._api_reachable = None
        try:
            self._process = self._start_process(device_name, memory_limit)
        except OSError as error:
            self._validation_message = str(error)
            return self.status()
        stored = _settings_for_start(
            device_name,
            device_label,
            memory_limit,
            app_settings,
        )
        save_launcher_settings(settings_path, stored)
        return self.status()

    def stop(self) -> LauncherStatus:
        """End the child tree. A later status line says the process is stopped."""
        if self.is_running() and self._process is not None:
            _ = stop_process_tree(self._process)
            self._stopped_by_user = True
        return self.status()

    def restart(
        self,
        device_name: WindowsDeviceName,
        memory_text: str,
        device_label: str,
        settings_path: Path,
        driver_version: str = "",
        app_settings: LauncherSettings | None = None,
    ) -> LauncherStatus:
        """Stop the current child, then start with the current settings."""
        _ = self.stop()
        return self.start(
            device_name,
            memory_text,
            device_label,
            settings_path,
            driver_version,
            app_settings,
        )

    def status(self) -> LauncherStatus:
        api_reachable = None
        if self.is_running() and self._api_probe is not None:
            now = time.monotonic()
            if self._api_reachable is None or now - self._api_checked_at >= 2:
                self._api_reachable = self._api_probe()
                self._api_checked_at = now
            api_reachable = self._api_reachable
        return launcher_status(
            process=self._process,
            output_lines=self._output,
            validation_message=self._validation_message,
            device_label=self._device_label,
            api_reachable=api_reachable,
            stopped_by_user=self._stopped_by_user,
            driver_version=self._driver_version,
        )


def _require_positive_megabytes(memory_limit_megabytes: int) -> int:
    if memory_limit_megabytes < 1:
        raise ValueError("Memory limit must be a positive number of megabytes")
    return memory_limit_megabytes


def _settings_for_start(
    device_name: WindowsDeviceName,
    device_label: str,
    memory_limit_megabytes: int | None,
    app_settings: LauncherSettings | None,
) -> LauncherSettings:
    if app_settings is None:
        return LauncherSettings(
            device_name=device_name,
            device_label=device_label,
            memory_limit_megabytes=memory_limit_megabytes,
        )
    return app_settings.model_copy(
        update={
            "device_name": device_name,
            "device_label": device_label,
            "memory_limit_megabytes": memory_limit_megabytes,
        }
    )


def start_exo_process(
    device_name: WindowsDeviceName,
    memory_limit_megabytes: int | None,
    *,
    environment: Mapping[str, str] | None = None,
    settings: LauncherSettings | None = None,
) -> subprocess.Popen[str]:
    """Spawn the exo runtime with the settings-panel environment.

    A frozen executable is re-invoked with ``--exo-runtime``. A source
    checkout runs ``python -m exo``. ``EXO_RUNTIME_DIR`` is set so the child
    does not open a browser; the shell's Web Dashboard button does that.

    Raises:
        ValueError: ``configured_environment`` raises when the memory limit is
            below 1. The window catches that and shows it on the status line
            before this function is called.
    """
    base = os.environ if environment is None else environment
    applied = _settings_for_start(
        device_name,
        "" if settings is None else settings.device_label,
        memory_limit_megabytes,
        settings,
    )
    child_environment = configured_environment(base, applied)
    child_environment["EXO_RUNTIME_DIR"] = str(Path(sys.executable).resolve().parent)
    creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    return subprocess.Popen(
        child_command(
            sys.executable,
            applied,
            frozen=running_as_frozen_executable(),
        ),
        env=child_environment,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        creationflags=creationflags,
    )


def drain_process_output(
    process: subprocess.Popen[str],
    on_line: Callable[[str], None],
) -> None:
    stdout = process.stdout
    if stdout is None:
        return
    for line in stdout:
        on_line(line.rstrip())


def open_launcher(
    choices: Sequence[WindowsDeviceChoice],
    settings_path: Path | None = None,
) -> None:
    """Show the taskbar icon, status panel, and settings window.

    Tk is imported by the shell so tests can import the launch helpers without
    a display. Quit stops the exo child before the process exits.

    Raises:
        ValueError: There is no device row to show. ``main`` always includes
            the CPU row, so this is the empty-probe guard.
    """
    from exo.windows.shell import run_windows_shell

    run_windows_shell(choices, settings_path)


def main() -> None:
    """Open the Windows launcher.

    Raises:
        SystemExit: The console script exits on macOS and Linux. The message
            is written to stderr.
    """
    if sys.platform != "win32":
        print("exo-windows runs on Windows.", file=sys.stderr)
        raise SystemExit(1)
    from exo.backends.tinygrad_opencl import opencl_driver_versions
    from exo.utils.info_gatherer.info_gatherer import windows_device_probe

    adapter_names, has_nvidia_gpu = windows_device_probe()
    open_launcher(
        windows_device_choices(
            adapter_names,
            has_nvidia_gpu,
            opencl_driver_versions(),
        )
    )
