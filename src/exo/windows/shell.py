"""Taskbar icon and settings window for Windows.

The layout follows the macOS menu-bar window and the EXO Settings tabs:
General, Model, Advanced, Environment, and About. Save & Restart writes the
same environment variables the Mac app injects into its child process.
"""

from __future__ import annotations

import ctypes
import queue
import subprocess
import sys
import threading
import tkinter as tk
import webbrowser
from collections.abc import Callable, Sequence
from ctypes import wintypes
from pathlib import Path
from tkinter import ttk
from typing import final

from exo import __version__
from exo.shared.constants import RESOURCES_DIR
from exo.windows.launcher import (
    LauncherController,
    LauncherSettings,
    LauncherStatus,
    WindowsDeviceChoice,
    WindowsDeviceName,
    api_is_reachable,
    custom_environment_text,
    default_launcher_settings_path,
    device_menu_label,
    drain_process_output,
    load_launcher_settings,
    memory_field_label,
    parse_custom_environment,
    restored_choice,
    start_exo_process,
)
from exo.windows.taskbar import TaskbarIcon

DASHBOARD_URL = "http://localhost:52416/"
API_BASE_URL = "http://localhost:52416/v1"
ONBOARDING_RESET_URL = "http://localhost:52416/?reset-onboarding"
_ERROR_ALREADY_EXISTS = 183


def settings_tab_titles() -> tuple[str, ...]:
    """Return the settings tabs in the same order as the macOS window."""
    return ("General", "Model", "Advanced", "Environment", "About")


def acquire_shell_mutex() -> bool:
    """Hold the single-instance mutex.

    A second shell returns False so two taskbar icons do not start two
    servers. The handle stays open until this process exits.
    """
    if sys.platform != "win32":
        return False
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.CreateMutexW.restype = wintypes.HANDLE
    kernel32.CreateMutexW.argtypes = (
        wintypes.LPVOID,
        wintypes.BOOL,
        wintypes.LPCWSTR,
    )
    kernel32.CloseHandle.argtypes = (wintypes.HANDLE,)
    kernel32.CloseHandle.restype = wintypes.BOOL
    handle = kernel32.CreateMutexW(None, False, "Local\\EXOWindowsShell")
    already_open = not handle or ctypes.get_last_error() == _ERROR_ALREADY_EXISTS
    if already_open:
        if handle:
            _ = kernel32.CloseHandle(handle)
        return False
    return True


@final
class SettingsPanel:
    """The EXO Settings notebook.

    Each Save button reads one tab and leaves the other tabs on the settings
    object the shell already stored.
    """

    def __init__(
        self,
        parent: tk.Misc,
        choices: Sequence[WindowsDeviceChoice],
        settings: LauncherSettings,
        memory_text: str,
        version: str,
    ) -> None:
        self._choices = list(choices)
        self.notebook = ttk.Notebook(parent)
        pages = {
            title: ttk.Frame(self.notebook, padding=12)
            for title in settings_tab_titles()
        }
        for title, frame in pages.items():
            self.notebook.add(frame, text=title)
        self._memory_label = tk.StringVar()
        self._memory_text = tk.StringVar(value=memory_text)
        self._namespace = tk.StringVar(value=settings.cluster_namespace)
        self._token = tk.StringVar(value=settings.hugging_face_token)
        self._endpoint = tk.StringVar(value=settings.hugging_face_endpoint)
        self._offline = tk.BooleanVar(value=settings.offline_mode)
        self._image_models = tk.BooleanVar(value=settings.enable_image_models)
        self._fast_synch = tk.BooleanVar(value=settings.fast_synch_enabled)
        self._default_models = tk.StringVar(value=settings.default_models_directory)
        self._additional_models = tk.StringVar(
            value=settings.additional_models_directories
        )
        self._read_only_models = tk.StringVar(
            value=settings.read_only_models_directories
        )
        initial = next(
            (
                choice
                for choice in self._choices
                if choice.label == settings.device_label
                or choice.device_name == settings.device_name
            ),
            self._choices[0],
        )
        self._device = tk.StringVar(value=device_menu_label(initial))
        self._memory_label.set(memory_field_label(initial))
        self._environment = tk.Text(
            pages["Environment"], height=6, width=64, wrap="none"
        )
        self._environment.insert(
            "1.0",
            custom_environment_text(settings.custom_environment_variables),
        )
        self._build_general(pages["General"])
        self._build_model(pages["Model"])
        self._build_advanced(pages["Advanced"])
        self._build_environment(pages["Environment"])
        self._build_about(pages["About"], version)
        self._on_save: Callable[[str], None] = lambda _title: None

    def pack(self) -> None:
        self.notebook.pack(fill="both", expand=True)

    def tab_titles(self) -> tuple[str, ...]:
        titles: list[str] = []
        for tab_id in self.notebook.tabs():  # pyright: ignore[reportUnknownVariableType, reportUnknownMemberType]
            text = self.notebook.tab(tab_id, "text")  # pyright: ignore[reportUnknownMemberType, reportUnknownArgumentType, reportUnknownVariableType]
            titles.append(text if isinstance(text, str) else "")
        return tuple(titles)

    def set_save_handler(self, handler: Callable[[str], None]) -> None:
        """Call ``handler`` with the tab title when Save & Restart is pressed."""
        self._on_save = handler

    def saved_settings(
        self,
        current: LauncherSettings,
        tab: str,
    ) -> tuple[LauncherSettings, str]:
        """Return the settings and memory text for a save of ``tab``."""
        if tab == "General":
            choice = self._selected_choice()
            return (
                current.model_copy(
                    update={
                        "device_name": choice.device_name,
                        "device_label": choice.label,
                        "cluster_namespace": self._namespace.get(),
                        "hugging_face_token": self._token.get(),
                        "hugging_face_endpoint": self._endpoint.get(),
                        "offline_mode": bool(self._offline.get()),
                    }
                ),
                self._memory_text.get(),
            )
        if tab == "Model":
            return (
                current.model_copy(
                    update={"enable_image_models": bool(self._image_models.get())}
                ),
                _memory_text_for(current),
            )
        if tab == "Advanced":
            return (
                current.model_copy(
                    update={"fast_synch_enabled": bool(self._fast_synch.get())}
                ),
                _memory_text_for(current),
            )
        if tab == "Environment":
            return (
                current.model_copy(
                    update={
                        "default_models_directory": self._default_models.get(),
                        "additional_models_directories": self._additional_models.get(),
                        "read_only_models_directories": self._read_only_models.get(),
                        "custom_environment_variables": parse_custom_environment(
                            self._environment.get("1.0", "end")
                        ),
                    }
                ),
                _memory_text_for(current),
            )
        return current, _memory_text_for(current)

    def _selected_choice(self) -> WindowsDeviceChoice:
        label = self._device.get()
        for choice in self._choices:
            if device_menu_label(choice) == label:
                return choice
        return self._choices[0]

    def _build_general(self, page: ttk.Frame) -> None:
        labels = [device_menu_label(choice) for choice in self._choices]
        _field(page, 0, "Device", None)
        device_menu = ttk.Combobox(
            page,
            textvariable=self._device,
            values=labels,
            state="readonly",
            width=42,
        )
        device_menu.grid(row=0, column=1, sticky="ew", padx=(8, 0))
        device_menu.bind("<<ComboboxSelected>>", self._on_device_changed)
        memory_caption = ttk.Label(page, textvariable=self._memory_label)
        memory_caption.grid(row=1, column=0, sticky="w", pady=(8, 0))
        ttk.Entry(page, textvariable=self._memory_text, width=12).grid(
            row=1, column=1, sticky="w", padx=(8, 0), pady=(8, 0)
        )
        _caption(page, 2, "Leave memory blank to use the device's available memory.")
        _labeled_entry(page, 3, "Cluster Namespace", self._namespace)
        _caption(
            page,
            4,
            "Nodes with the same namespace form a cluster. Leave empty for default.",
        )
        _labeled_entry(page, 5, "HuggingFace Token", self._token, secret=True)
        _caption(
            page,
            6,
            "Required for gated models. Get one at huggingface.co/settings/tokens.",
        )
        _labeled_entry(page, 7, "HuggingFace Endpoint", self._endpoint)
        _caption(
            page,
            8,
            "Defaults to huggingface.co. A mirror such as hf-mirror.com also works.",
        )
        ttk.Checkbutton(page, text="Offline Mode", variable=self._offline).grid(
            row=9, column=0, columnspan=2, sticky="w", pady=(12, 0)
        )
        _caption(
            page, 10, "Skip internet checks and use only locally available models."
        )
        _save_button(page, 11, lambda: self._on_save("General"))

    def _on_device_changed(self, _event: object) -> None:
        self._memory_label.set(memory_field_label(self._selected_choice()))

    def _build_model(self, page: ttk.Frame) -> None:
        ttk.Checkbutton(
            page,
            text="Enable Image Models (experimental)",
            variable=self._image_models,
        ).grid(row=0, column=0, sticky="w")
        _caption(
            page,
            1,
            "Allow text-to-image and image-to-image models in the model picker.",
        )
        _save_button(page, 2, lambda: self._on_save("Model"))

    def _build_advanced(self, page: ttk.Frame) -> None:
        ttk.Checkbutton(
            page,
            text="Fast Synch Enabled",
            variable=self._fast_synch,
        ).grid(row=0, column=0, sticky="w")
        _caption(
            page,
            1,
            "Experimental CPU to GPU synchronization. The Mac app uses this for low-latency RDMA and tensor parallelism.",
        )
        ttk.Button(
            page,
            text="Reset Onboarding",
            command=lambda: webbrowser.open(ONBOARDING_RESET_URL),
        ).grid(row=2, column=0, sticky="w", pady=(12, 0))
        _caption(page, 3, "Opens the dashboard and resets the onboarding wizard.")
        _save_button(page, 4, lambda: self._on_save("Advanced"))

    def _build_environment(self, page: ttk.Frame) -> None:
        _labeled_entry(page, 0, "Default Models Directory", self._default_models)
        _caption(page, 1, "Sets EXO_DEFAULT_MODELS_DIR. Where models are downloaded.")
        _labeled_entry(page, 2, "Additional Directories", self._additional_models)
        _caption(page, 3, "Sets EXO_MODELS_DIRS. Extra writable model directories.")
        _labeled_entry(page, 4, "Read-Only Directories", self._read_only_models)
        _caption(page, 5, "Sets EXO_MODELS_READ_ONLY_DIRS. Never written to.")
        ttk.Label(page, text="Custom Environment Variables").grid(
            row=6, column=0, columnspan=2, sticky="w", pady=(12, 0)
        )
        _caption(
            page,
            7,
            "One KEY=value per line. These override the fields above when the names match.",
        )
        self._environment.grid(row=8, column=0, columnspan=2, sticky="ew", pady=(4, 0))
        _save_button(page, 9, lambda: self._on_save("Environment"))

    def _build_about(self, page: ttk.Frame, version: str) -> None:
        ttk.Label(page, text=f"Version {version}").grid(row=0, column=0, sticky="w")
        ttk.Label(
            page,
            text="EXO for Windows. Right-click the taskbar icon to open this window or exit.",
        ).grid(row=1, column=0, sticky="w", pady=(8, 0))


def run_windows_shell(
    choices: Sequence[WindowsDeviceChoice],
    settings_path: Path | None = None,
) -> None:
    """Open the taskbar icon and EXO Settings.

    The exo child starts from the saved settings. Right-click the icon for
    the dashboard, settings, start, stop, restart, and exit. Closing Settings
    leaves the icon in place. Exit stops the child and leaves the taskbar.

    Raises:
        ValueError: There is no device row to show.
    """
    if len(choices) == 0:
        raise ValueError("the launcher needs at least one device")
    if not acquire_shell_mutex():
        print("EXO is already open.", file=sys.stderr)
        return

    path = default_launcher_settings_path() if settings_path is None else settings_path
    saved = load_launcher_settings(path)
    initial_choice, initial_memory = restored_choice(choices, saved)
    if saved is None:
        saved = LauncherSettings(
            device_name=initial_choice.device_name,
            device_label=initial_choice.label,
        )
    current = [
        saved.model_copy(
            update={
                "device_name": initial_choice.device_name,
                "device_label": initial_choice.label,
            }
        )
    ]
    root = tk.Tk()
    root.withdraw()
    icon_path = RESOURCES_DIR / "exo.ico"
    _apply_window_icon(root, icon_path)

    commands: queue.Queue[Callable[[], None]] = queue.Queue()

    settings_window = tk.Toplevel(root)
    settings_window.withdraw()
    settings_window.title("EXO Settings")
    settings_window.geometry("640x560")
    settings_window.minsize(640, 560)
    panel = SettingsPanel(
        settings_window,
        choices,
        current[0],
        initial_memory,
        __version__,
    )
    panel.pack()
    _place_centered(settings_window, 640, 560)
    settings_window.withdraw()

    def driver_version(settings: LauncherSettings) -> str:
        for choice in choices:
            if choice.label == settings.device_label:
                return choice.driver_version
        return ""

    controller = LauncherController(
        _starter(current),
        api_probe=api_is_reachable,
        device_label=initial_choice.label,
        driver_version=initial_choice.driver_version,
    )

    def show(status: LauncherStatus) -> None:
        running = "Running" if status.process == "running" else "Stopped"
        taskbar.update_tooltip(f"EXO — {running}")

    def start_drain() -> None:
        active = controller.current_process()
        if active is None:
            return
        threading.Thread(
            target=drain_process_output,
            args=(active, controller.note_output_line),
            daemon=True,
        ).start()

    def apply_settings(settings: LauncherSettings, memory_text: str) -> None:
        current[0] = settings
        previous = controller.current_process()
        launch = controller.restart if controller.is_running() else controller.start
        status = launch(
            settings.device_name,
            memory_text,
            settings.device_label,
            path,
            driver_version(settings),
            settings,
        )
        show(status)
        process = controller.current_process()
        if process is not None and process is not previous and controller.is_running():
            start_drain()
        loaded = load_launcher_settings(path)
        if loaded is not None and controller.is_running():
            current[0] = loaded

    def save_tab(tab: str) -> None:
        settings, memory_text = panel.saved_settings(current[0], tab)
        apply_settings(settings, memory_text)

    panel.set_save_handler(save_tab)

    def open_dashboard() -> None:
        _ = webbrowser.open(DASHBOARD_URL)

    def copy_api_url() -> None:
        root.clipboard_clear()
        root.clipboard_append(API_BASE_URL)

    def show_settings() -> None:
        settings_window.deiconify()
        settings_window.lift()  # pyright: ignore[reportUnknownMemberType]

    def quit_shell() -> None:
        _ = controller.stop()
        taskbar.remove()
        root.destroy()

    def run_menu_command(command: str) -> None:
        if command == "dashboard":
            open_dashboard()
            return
        if command == "settings":
            show_settings()
            return
        if command == "copy-api":
            copy_api_url()
            return
        if command == "start" or command == "restart":
            apply_settings(current[0], _memory_text_for(current[0]))
            return
        if command == "stop":
            show(controller.stop())
            return
        if command == "exit":
            quit_shell()

    def hide_settings() -> None:
        settings_window.withdraw()

    settings_window.protocol("WM_DELETE_WINDOW", hide_settings)

    def poll_icon() -> None:
        while True:
            try:
                command = commands.get_nowait()
            except queue.Empty:
                break
            command()
        if root.winfo_exists():
            root.after(150, poll_icon)

    def refresh_status() -> None:
        show(controller.status())
        if root.winfo_exists():
            root.after(1000, refresh_status)

    def queue_menu_command(command: str) -> None:
        def run_chosen() -> None:
            run_menu_command(command)

        commands.put(run_chosen)

    taskbar = TaskbarIcon()
    installed = taskbar.install(icon_path, "EXO", queue_menu_command)
    print(
        "EXO taskbar icon installed" if installed else "EXO taskbar icon unavailable",
        flush=True,
    )
    apply_settings(current[0], initial_memory)
    root.after(150, poll_icon)
    root.after(1000, refresh_status)
    root.mainloop()


def _starter(
    current: list[LauncherSettings],
) -> Callable[[WindowsDeviceName, int | None], subprocess.Popen[str]]:
    def start_child(
        device_name: WindowsDeviceName,
        memory_limit_megabytes: int | None,
    ) -> subprocess.Popen[str]:
        settings = current[0].model_copy(
            update={
                "device_name": device_name,
                "memory_limit_megabytes": memory_limit_megabytes,
            }
        )
        current[0] = settings
        return start_exo_process(
            device_name,
            memory_limit_megabytes,
            settings=settings,
        )

    return start_child


def _memory_text_for(settings: LauncherSettings) -> str:
    if settings.memory_limit_megabytes is None:
        return ""
    return str(settings.memory_limit_megabytes)


def _apply_window_icon(root: tk.Tk, icon_path: Path) -> None:
    if not icon_path.is_file():
        return
    try:
        root.iconbitmap(default=str(icon_path))  # pyright: ignore[reportUnknownMemberType]
    except tk.TclError:
        return


def _place_centered(window: tk.Toplevel, width: int, height: int) -> None:
    window.update_idletasks()
    x_position = max(0, (window.winfo_screenwidth() - width) // 2)
    y_position = max(0, (window.winfo_screenheight() - height) // 2)
    window.geometry(f"{width}x{height}+{x_position}+{y_position}")


def _field(
    page: ttk.Frame, row: int, label: str, variable: tk.StringVar | None
) -> None:
    ttk.Label(page, text=label).grid(row=row, column=0, sticky="w", pady=(8, 0))
    if variable is not None:
        ttk.Entry(page, textvariable=variable, width=42).grid(
            row=row, column=1, sticky="ew", padx=(8, 0), pady=(8, 0)
        )


def _labeled_entry(
    page: ttk.Frame,
    row: int,
    label: str,
    variable: tk.StringVar,
    *,
    secret: bool = False,
) -> None:
    ttk.Label(page, text=label).grid(row=row, column=0, sticky="w", pady=(8, 0))
    show = "*" if secret else ""
    ttk.Entry(page, textvariable=variable, width=42, show=show).grid(
        row=row, column=1, sticky="ew", padx=(8, 0), pady=(8, 0)
    )


def _caption(page: ttk.Frame, row: int, text: str) -> None:
    ttk.Label(page, text=text, wraplength=560).grid(
        row=row, column=0, columnspan=2, sticky="w", pady=(2, 0)
    )


def _save_button(page: ttk.Frame, row: int, command: Callable[[], None]) -> None:
    ttk.Button(page, text="Save & Restart", command=command).grid(
        row=row, column=1, sticky="e", pady=(12, 0)
    )
