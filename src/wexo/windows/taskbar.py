"""Windows taskbar notification icon for the exo shell.

The macOS app uses a menu-bar icon. This is the same control on Windows:
an icon that stays in the notification area and opens a menu on right-click.
"""

from __future__ import annotations

import ctypes
import sys
import threading
from collections.abc import Callable
from ctypes import wintypes
from pathlib import Path
from typing import final

_NIM_ADD = 0
_NIM_MODIFY = 1
_NIM_DELETE = 2
_NIF_MESSAGE = 0x1
_NIF_ICON = 0x2
_NIF_TIP = 0x4
_WM_CLOSE = 0x0010
_WM_DESTROY = 0x0002
_WM_RBUTTONUP = 0x0205
_WM_CONTEXTMENU = 0x007B
_WM_NULL = 0
_WM_TRAY = 0x8000
_MF_STRING = 0
_MF_SEPARATOR = 0x800
_TPM_RIGHTBUTTON = 0x0002
_TPM_NONOTIFY = 0x0080
_TPM_RETURNCMD = 0x0100
_IMAGE_ICON = 1
_LR_LOADFROMFILE = 0x00000010
_IDI_APPLICATION = 32512
_RIGHT_CLICKS = frozenset({_WM_RBUTTONUP, _WM_CONTEXTMENU})


class _NotifyIconData(ctypes.Structure):
    _fields_ = (
        ("cbSize", wintypes.DWORD),
        ("hWnd", wintypes.HWND),
        ("uID", wintypes.UINT),
        ("uFlags", wintypes.UINT),
        ("uCallbackMessage", wintypes.UINT),
        ("hIcon", wintypes.HICON),
        ("szTip", wintypes.WCHAR * 128),
        ("dwState", wintypes.DWORD),
        ("dwStateMask", wintypes.DWORD),
        ("szInfo", wintypes.WCHAR * 256),
        ("uVersion", wintypes.UINT),
        ("szInfoTitle", wintypes.WCHAR * 64),
        ("dwInfoFlags", wintypes.DWORD),
        ("guidItem", ctypes.c_byte * 16),
        ("hBalloonIcon", wintypes.HICON),
    )


class _WindowClass(ctypes.Structure):
    _fields_ = (
        ("cbSize", wintypes.UINT),
        ("style", wintypes.UINT),
        ("lpfnWndProc", ctypes.c_void_p),
        ("cbClsExtra", ctypes.c_int),
        ("cbWndExtra", ctypes.c_int),
        ("hInstance", wintypes.HINSTANCE),
        ("hIcon", wintypes.HICON),
        ("hCursor", wintypes.HANDLE),
        ("hbrBackground", wintypes.HBRUSH),
        ("lpszMenuName", wintypes.LPCWSTR),
        ("lpszClassName", wintypes.LPCWSTR),
        ("hIconSm", wintypes.HICON),
    )


class _Point(ctypes.Structure):
    _fields_ = (("x", wintypes.LONG), ("y", wintypes.LONG))


class _Message(ctypes.Structure):
    _fields_ = (
        ("hwnd", wintypes.HWND),
        ("message", wintypes.UINT),
        ("wParam", wintypes.WPARAM),
        ("lParam", wintypes.LPARAM),
        ("time", wintypes.DWORD),
        ("pt_x", wintypes.LONG),
        ("pt_y", wintypes.LONG),
    )


def _user32():
    if sys.platform != "win32":
        raise OSError("the taskbar icon is only available on Windows")
    library = ctypes.WinDLL("user32", use_last_error=True)
    library.RegisterClassExW.argtypes = (ctypes.POINTER(_WindowClass),)
    library.RegisterClassExW.restype = wintypes.ATOM
    library.CreateWindowExW.argtypes = (
        wintypes.DWORD,
        wintypes.LPCWSTR,
        wintypes.LPCWSTR,
        wintypes.DWORD,
        ctypes.c_int,
        ctypes.c_int,
        ctypes.c_int,
        ctypes.c_int,
        wintypes.HWND,
        wintypes.HMENU,
        wintypes.HINSTANCE,
        wintypes.LPVOID,
    )
    library.CreateWindowExW.restype = wintypes.HWND
    library.DefWindowProcW.argtypes = (
        wintypes.HWND,
        wintypes.UINT,
        wintypes.WPARAM,
        wintypes.LPARAM,
    )
    library.DefWindowProcW.restype = ctypes.c_ssize_t
    library.DestroyWindow.argtypes = (wintypes.HWND,)
    library.DestroyWindow.restype = wintypes.BOOL
    library.PostQuitMessage.argtypes = (ctypes.c_int,)
    library.PostQuitMessage.restype = None
    library.PostMessageW.argtypes = (
        wintypes.HWND,
        wintypes.UINT,
        wintypes.WPARAM,
        wintypes.LPARAM,
    )
    library.PostMessageW.restype = wintypes.BOOL
    library.GetMessageW.argtypes = (
        ctypes.POINTER(_Message),
        wintypes.HWND,
        wintypes.UINT,
        wintypes.UINT,
    )
    library.GetMessageW.restype = ctypes.c_int
    library.TranslateMessage.argtypes = (ctypes.POINTER(_Message),)
    library.TranslateMessage.restype = wintypes.BOOL
    library.DispatchMessageW.argtypes = (ctypes.POINTER(_Message),)
    library.DispatchMessageW.restype = ctypes.c_ssize_t
    library.LoadImageW.argtypes = (
        wintypes.HINSTANCE,
        ctypes.c_void_p,
        wintypes.UINT,
        ctypes.c_int,
        ctypes.c_int,
        wintypes.UINT,
    )
    library.LoadImageW.restype = wintypes.HANDLE
    library.CreatePopupMenu.argtypes = ()
    library.CreatePopupMenu.restype = wintypes.HMENU
    library.AppendMenuW.argtypes = (
        wintypes.HMENU,
        wintypes.UINT,
        wintypes.UINT,
        wintypes.LPCWSTR,
    )
    library.AppendMenuW.restype = wintypes.BOOL
    library.TrackPopupMenu.argtypes = (
        wintypes.HMENU,
        wintypes.UINT,
        ctypes.c_int,
        ctypes.c_int,
        ctypes.c_int,
        wintypes.HWND,
        ctypes.c_void_p,
    )
    library.TrackPopupMenu.restype = wintypes.UINT
    library.DestroyMenu.argtypes = (wintypes.HMENU,)
    library.DestroyMenu.restype = wintypes.BOOL
    library.SetForegroundWindow.argtypes = (wintypes.HWND,)
    library.SetForegroundWindow.restype = wintypes.BOOL
    library.GetCursorPos.argtypes = (ctypes.POINTER(_Point),)
    library.GetCursorPos.restype = wintypes.BOOL
    return library


def _shell32():
    if sys.platform != "win32":
        raise OSError("the taskbar icon is only available on Windows")
    library = ctypes.WinDLL("shell32", use_last_error=True)
    library.Shell_NotifyIconW.argtypes = (
        wintypes.DWORD,
        ctypes.POINTER(_NotifyIconData),
    )
    library.Shell_NotifyIconW.restype = wintypes.BOOL
    return library


def _kernel32():
    if sys.platform != "win32":
        raise OSError("the taskbar icon is only available on Windows")
    library = ctypes.WinDLL("kernel32", use_last_error=True)
    library.GetModuleHandleW.argtypes = (wintypes.LPCWSTR,)
    library.GetModuleHandleW.restype = wintypes.HINSTANCE
    return library


def _handle(value: int | None) -> int:
    if value is None:
        return 0
    return value


def _load_icon(path: Path) -> int:
    if sys.platform != "win32":
        return 0
    user32 = _user32()
    if path.is_file():
        encoded = ctypes.create_unicode_buffer(str(path))
        loaded = _handle(
            user32.LoadImageW(
                None,
                ctypes.cast(encoded, ctypes.c_void_p),
                _IMAGE_ICON,
                0,
                0,
                _LR_LOADFROMFILE,
            )
        )
        if loaded != 0:
            return loaded
    return _handle(
        user32.LoadImageW(
            None,
            ctypes.c_void_p(_IDI_APPLICATION),
            _IMAGE_ICON,
            0,
            0,
            0x8000,
        )
    )


def _tooltip(text: str) -> str:
    return text[:127]


def taskbar_menu_entries() -> tuple[tuple[str, str], ...]:
    """Return the right-click menu as ``(command, label)`` pairs.

    An empty command is a separator. ``exit`` stops exo and leaves the taskbar.
    """
    return (
        ("dashboard", "Open Dashboard"),
        ("settings", "Settings"),
        ("copy-api", "Copy API URL"),
        ("start", "Start"),
        ("stop", "Stop"),
        ("restart", "Restart"),
        ("", ""),
        ("exit", "Exit EXO"),
    )


def taskbar_menu_labels() -> tuple[str, ...]:
    """Return the visible right-click labels, including Exit EXO."""
    return tuple(label for command, label in taskbar_menu_entries() if command != "")


def command_for_menu_id(item_id: int) -> str:
    """Return the command for a menu item id, or an empty string when none was chosen."""
    commands = [command for command, _label in taskbar_menu_entries() if command != ""]
    if item_id < 1 or item_id > len(commands):
        return ""
    return commands[item_id - 1]


@final
class TaskbarIcon:
    """One notification-area icon backed by a hidden window.

    ``install`` returns when the icon is on the taskbar or the add failed.
    ``remove`` posts a close to that window and waits for the message loop.
    """

    def __init__(self) -> None:
        self._thread: threading.Thread | None = None
        self._hwnd = 0
        self._icon = 0
        self._added = False
        self._ready = threading.Event()
        self._on_command: Callable[[str], None] = lambda _command: None
        self._menu_is_open = False
        # Referenced from the window procedure, which the Darwin type check
        # treats as unreachable. This binding keeps the method in use.
        self._open_menu: Callable[[int], None] = self._show_context_menu
        self._window_procedure: object | None = None
        self._class_name = "EXOTaskbarIcon"
        self._icon_path = Path()

    def install(
        self,
        icon_path: Path,
        tooltip: str,
        on_command: Callable[[str], None],
    ) -> bool:
        """Add the icon. A second call returns the first result.

        Returns False off Windows.

        ``on_command`` runs on the icon's thread when a right-click menu item
        is chosen, so it may only schedule work back onto the window thread.
        """
        if sys.platform != "win32":
            return False
        if self._thread is not None:
            return self._added
        self._on_command = on_command
        self._icon_path = icon_path
        self._thread = threading.Thread(
            target=self._message_loop,
            name="exo-taskbar",
            daemon=True,
        )
        self._thread.start()
        _ = self._ready.wait(timeout=3)
        if not self._added:
            return False
        self.update_tooltip(tooltip)
        return True

    def update_tooltip(self, tooltip: str) -> None:
        """Replace the hover text. A missing icon does nothing."""
        if sys.platform != "win32" or not self._added or self._hwnd == 0:
            return
        data = self._icon_data(_tooltip(tooltip))
        _ = _shell32().Shell_NotifyIconW(_NIM_MODIFY, ctypes.byref(data))

    def remove(self) -> None:
        """Take the icon off the taskbar and stop its message loop."""
        if sys.platform != "win32":
            return
        hwnd = self._hwnd
        if hwnd != 0:
            _ = _user32().PostMessageW(hwnd, _WM_CLOSE, 0, 0)
        thread = self._thread
        if thread is not None:
            thread.join(timeout=2)
        self._added = False
        self._hwnd = 0

    def _message_loop(self) -> None:
        if sys.platform != "win32":
            self._ready.set()
            return
        user32 = _user32()
        kernel32 = _kernel32()
        procedure_type = ctypes.WINFUNCTYPE(
            ctypes.c_ssize_t,
            wintypes.HWND,
            wintypes.UINT,
            wintypes.WPARAM,
            wintypes.LPARAM,
        )

        def window_procedure(
            hwnd: int,
            message: int,
            wparam: int,
            lparam: int,
        ) -> int:
            if message == _WM_TRAY and (int(lparam) & 0xFFFF) in _RIGHT_CLICKS:
                self._open_menu(int(hwnd))
                return 0
            if message == _WM_CLOSE:
                if self._added:
                    data = self._icon_data("EXO")
                    _ = _shell32().Shell_NotifyIconW(_NIM_DELETE, ctypes.byref(data))
                    self._added = False
                _ = user32.DestroyWindow(hwnd)
                return 0
            if message == _WM_DESTROY:
                user32.PostQuitMessage(0)
                return 0
            return int(user32.DefWindowProcW(hwnd, message, wparam, lparam))

        self._window_procedure = procedure_type(window_procedure)
        instance = kernel32.GetModuleHandleW(None)
        window_class = _WindowClass()
        window_class.cbSize = ctypes.sizeof(_WindowClass)
        window_class.lpfnWndProc = ctypes.cast(
            self._window_procedure,
            ctypes.c_void_p,
        )
        window_class.hInstance = instance
        window_class.lpszClassName = self._class_name
        registered = user32.RegisterClassExW(ctypes.byref(window_class))
        if registered == 0 and ctypes.get_last_error() not in (0, 1410):
            self._ready.set()
            return
        hwnd = user32.CreateWindowExW(
            0,
            self._class_name,
            "EXO",
            0,
            0,
            0,
            0,
            0,
            0,
            None,
            instance,
            None,
        )
        self._hwnd = int(hwnd) if hwnd else 0
        if self._hwnd == 0:
            self._ready.set()
            return
        self._icon = _load_icon(self._icon_path)
        data = self._icon_data("EXO")
        self._added = bool(_shell32().Shell_NotifyIconW(_NIM_ADD, ctypes.byref(data)))
        self._ready.set()
        if not self._added:
            return
        message = _Message()
        while user32.GetMessageW(ctypes.byref(message), None, 0, 0) > 0:
            _ = user32.TranslateMessage(ctypes.byref(message))
            _ = user32.DispatchMessageW(ctypes.byref(message))

    def _show_context_menu(self, hwnd: int) -> None:
        """Show the right-click menu and report the chosen command.

        A nested click while the menu is already open is ignored so one
        right-click does not open the menu twice.
        """
        if sys.platform != "win32" or hwnd == 0 or self._menu_is_open:
            return
        self._menu_is_open = True
        selected = 0
        try:
            user32 = _user32()
            menu = user32.CreatePopupMenu()
            try:
                item_id = 1
                for command, label in taskbar_menu_entries():
                    if command == "":
                        _ = user32.AppendMenuW(menu, _MF_SEPARATOR, 0, None)
                        continue
                    _ = user32.AppendMenuW(menu, _MF_STRING, item_id, label)
                    item_id += 1
                cursor = _Point()
                _ = user32.GetCursorPos(ctypes.byref(cursor))
                _ = user32.SetForegroundWindow(hwnd)
                selected = int(
                    user32.TrackPopupMenu(
                        menu,
                        _TPM_RIGHTBUTTON | _TPM_NONOTIFY | _TPM_RETURNCMD,
                        cursor.x,
                        cursor.y,
                        0,
                        hwnd,
                        None,
                    )
                )
                _ = user32.PostMessageW(hwnd, _WM_NULL, 0, 0)
            finally:
                _ = user32.DestroyMenu(menu)
        finally:
            self._menu_is_open = False
        chosen = command_for_menu_id(selected)
        if chosen != "":
            self._on_command(chosen)

    def _icon_data(self, tooltip: str) -> _NotifyIconData:
        data = _NotifyIconData()
        data.cbSize = ctypes.sizeof(_NotifyIconData)
        data.hWnd = self._hwnd
        data.uID = 1
        data.uFlags = _NIF_MESSAGE | _NIF_ICON | _NIF_TIP
        data.uCallbackMessage = _WM_TRAY
        data.hIcon = self._icon
        data.szTip = tooltip
        return data
