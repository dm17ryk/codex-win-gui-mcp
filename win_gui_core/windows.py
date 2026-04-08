from __future__ import annotations

import re
import time
from dataclasses import dataclass
from typing import Any

import mss
import win32con
import win32gui
import win32process

from .errors import FocusError, WindowResolutionError


@dataclass
class WindowInfo:
    hwnd: int
    title: str
    class_name: str
    pid: int
    rect: tuple[int, int, int, int]
    visible: bool

    def as_dict(self) -> dict[str, Any]:
        left, top, right, bottom = self.rect
        return {
            "hwnd": self.hwnd,
            "title": self.title,
            "class_name": self.class_name,
            "pid": self.pid,
            "visible": self.visible,
            "left": left,
            "top": top,
            "right": right,
            "bottom": bottom,
            "width": max(0, right - left),
            "height": max(0, bottom - top),
        }


class WindowManager:
    def __init__(self, main_window_title_regex: str) -> None:
        self.main_window_title_regex = main_window_title_regex or ".*"

    def list_windows(self) -> list[dict[str, Any]]:
        windows: list[WindowInfo] = []

        def callback(hwnd: int, _lparam: int) -> bool:
            try:
                title = win32gui.GetWindowText(hwnd)
                class_name = win32gui.GetClassName(hwnd)
                visible = bool(win32gui.IsWindowVisible(hwnd))
                rect = win32gui.GetWindowRect(hwnd)
                _, pid = win32process.GetWindowThreadProcessId(hwnd)
                if title or visible:
                    windows.append(
                        WindowInfo(
                            hwnd=hwnd,
                            title=title,
                            class_name=class_name,
                            pid=pid,
                            rect=rect,
                            visible=visible,
                        )
                    )
            except Exception:
                pass
            return True

        win32gui.EnumWindows(callback, 0)
        return [window.as_dict() for window in windows]

    def wait_main_window(
        self,
        title_regex: str | None = None,
        timeout_sec: float = 20.0,
        pid: int | None = None,
    ) -> dict[str, Any]:
        pattern = re.compile(title_regex or self.main_window_title_regex)
        deadline = time.time() + timeout_sec
        while time.time() < deadline:
            for info in self.list_windows():
                if not info["visible"]:
                    continue
                if pid is not None and info["pid"] != pid:
                    continue
                if pattern.search(info["title"] or ""):
                    return {"ok": True, "window": info}
            time.sleep(0.2)
        return {
            "ok": False,
            "error": f"No visible window matched /{pattern.pattern}/ within {timeout_sec:.1f}s",
        }

    def resolve_window(self, *, title_regex: str | None, pid: int | None, timeout_sec: float = 5.0) -> dict[str, Any]:
        result = self.wait_main_window(title_regex=title_regex, timeout_sec=timeout_sec, pid=pid)
        if not result.get("ok"):
            raise WindowResolutionError(result["error"])
        return result["window"]

    def get_window_rect(self, hwnd: int) -> dict[str, Any]:
        left, top, right, bottom = win32gui.GetWindowRect(hwnd)
        return {
            "hwnd": hwnd,
            "left": left,
            "top": top,
            "right": right,
            "bottom": bottom,
            "width": max(0, right - left),
            "height": max(0, bottom - top),
        }

    @staticmethod
    def is_window(hwnd: int | None) -> bool:
        return bool(hwnd) and bool(win32gui.IsWindow(hwnd))

    def focus_window(self, hwnd: int) -> dict[str, Any]:
        try:
            if win32gui.IsIconic(hwnd):
                win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
            win32gui.SetForegroundWindow(hwnd)
        except Exception as exc:
            raise FocusError(f"Unable to focus hwnd {hwnd}: {exc}") from exc
        return {"ok": True, "hwnd": hwnd}

    def restore_window(self, hwnd: int) -> dict[str, Any]:
        try:
            win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
            win32gui.SetForegroundWindow(hwnd)
        except Exception as exc:
            raise FocusError(f"Unable to restore hwnd {hwnd}: {exc}") from exc
        return {"ok": True, "hwnd": hwnd}

    def move_window(self, hwnd: int, x: int, y: int, width: int, height: int) -> dict[str, Any]:
        win32gui.MoveWindow(hwnd, x, y, width, height, True)
        return {"ok": True, "hwnd": hwnd, "x": x, "y": y, "width": width, "height": height}

    def enumerate_monitors(self) -> dict[str, Any]:
        monitors: list[dict[str, Any]] = []
        with mss.mss() as sct:
            for index, monitor in enumerate(sct.monitors[1:], start=1):
                monitors.append(
                    {
                        "index": index,
                        "left": monitor["left"],
                        "top": monitor["top"],
                        "width": monitor["width"],
                        "height": monitor["height"],
                    }
                )
        return {"ok": True, "monitors": monitors}

    def primary_monitor_bbox(self) -> dict[str, int]:
        with mss.mss() as sct:
            monitor = sct.monitors[1]
        return {
            "left": monitor["left"],
            "top": monitor["top"],
            "width": monitor["width"],
            "height": monitor["height"],
        }

    def wait_window_stable(
        self,
        *,
        title_regex: str | None,
        pid: int | None,
        timeout_sec: float = 5.0,
        stable_for_sec: float = 1.0,
    ) -> dict[str, Any]:
        deadline = time.time() + timeout_sec
        last_signature: tuple[Any, ...] | None = None
        stable_since: float | None = None
        while time.time() < deadline:
            window = self.resolve_window(title_regex=title_regex, pid=pid, timeout_sec=0.5)
            rect = self.get_window_rect(window["hwnd"])
            signature = (
                window["hwnd"],
                window["pid"],
                window["title"],
                rect["left"],
                rect["top"],
                rect["width"],
                rect["height"],
            )
            if signature == last_signature:
                stable_since = stable_since or time.time()
                if time.time() - stable_since >= stable_for_sec:
                    return {"ok": True, "window": window, "rect": rect, "stable_for_sec": stable_for_sec}
            else:
                last_signature = signature
                stable_since = time.time()
            time.sleep(0.2)
        raise WindowResolutionError("Window did not remain stable within the requested timeout.")
