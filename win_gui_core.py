from __future__ import annotations

import base64
import io
import os
import re
import shutil
import subprocess
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

import mss
import psutil
import pyautogui
import win32con
import win32gui
import win32process
from PIL import Image
from pywinauto import Desktop
from pywinauto.findwindows import ElementNotFoundError, WindowNotFoundError


pyautogui.FAILSAFE = True
pyautogui.PAUSE = 0.03


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


class DesktopHarness:
    def __init__(self) -> None:
        self.app_exe = os.environ.get("APP_EXE", "")
        self.app_workdir = os.environ.get("APP_WORKDIR", "")
        self.app_log_dir = Path(os.environ.get("APP_LOG_DIR", "logs"))
        self.app_state_dir = Path(os.environ.get("APP_STATE_DIR", "state"))
        self.main_window_title_regex = os.environ.get("MAIN_WINDOW_TITLE_REGEX", ".*")
        self._last_pid: int | None = None
        self._desktop = Desktop(backend="uia")

    def launch_app(self, args: list[str] | None = None) -> dict[str, Any]:
        if not self.app_exe:
            raise RuntimeError("APP_EXE is not set")
        cmd = [self.app_exe, *(args or [])]
        proc = subprocess.Popen(
            cmd,
            cwd=self.app_workdir or None,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=subprocess.CREATE_NEW_PROCESS_GROUP,
        )
        self._last_pid = proc.pid
        return {"ok": True, "pid": proc.pid, "cmd": cmd}

    def close_app(self, pid: int | None = None, timeout_sec: float = 10.0) -> dict[str, Any]:
        target_pid = pid or self._last_pid
        if not target_pid:
            return {"ok": True, "terminated": [], "note": "no pid set"}
        proc = psutil.Process(target_pid)
        targets = [proc, *proc.children(recursive=True)]
        terminated: list[int] = []
        for p in reversed(targets):
            try:
                p.terminate()
                terminated.append(p.pid)
            except psutil.NoSuchProcess:
                pass
        _, alive = psutil.wait_procs(targets, timeout=timeout_sec)
        for p in alive:
            try:
                p.kill()
            except psutil.NoSuchProcess:
                pass
        return {"ok": True, "terminated": terminated}

    def restart_app(self, args: list[str] | None = None) -> dict[str, Any]:
        try:
            self.close_app()
        except Exception:
            pass
        time.sleep(1.0)
        return self.launch_app(args=args)

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
        return [w.as_dict() for w in windows]

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
                if pid and info["pid"] != pid:
                    continue
                if pattern.search(info["title"] or ""):
                    return {"ok": True, "window": info}
            time.sleep(0.2)
        return {
            "ok": False,
            "error": f"No visible window matched /{pattern.pattern}/ within {timeout_sec:.1f}s",
        }

    def focus_window(self, hwnd: int) -> dict[str, Any]:
        if win32gui.IsIconic(hwnd):
            win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
        win32gui.SetForegroundWindow(hwnd)
        return {"ok": True, "hwnd": hwnd}

    def move_window(self, hwnd: int, x: int, y: int, width: int, height: int) -> dict[str, Any]:
        win32gui.MoveWindow(hwnd, x, y, width, height, True)
        return {"ok": True, "hwnd": hwnd, "x": x, "y": y, "width": width, "height": height}

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

    def capture_screenshot(
        self,
        *,
        full_screen: bool = False,
        hwnd: int | None = None,
        title_regex: str | None = None,
        embed_base64: bool = False,
        output_dir: str | None = None,
    ) -> dict[str, Any]:
        bbox: dict[str, int]
        if full_screen:
            bbox = self._primary_monitor_bbox()
        else:
            hwnd = hwnd or self._resolve_hwnd_from_title(title_regex or self.main_window_title_regex)
            rect = self.get_window_rect(hwnd)
            bbox = {
                "left": rect["left"],
                "top": rect["top"],
                "width": rect["width"],
                "height": rect["height"],
            }
        with mss.mss() as sct:
            shot = sct.grab(bbox)
            img = Image.frombytes("RGB", shot.size, shot.rgb)
        out_dir = Path(output_dir) if output_dir else Path(tempfile.gettempdir()) / "codex-win-gui"
        out_dir.mkdir(parents=True, exist_ok=True)
        path = out_dir / f"screenshot-{int(time.time() * 1000)}.png"
        img.save(path)
        result: dict[str, Any] = {
            "ok": True,
            "path": str(path),
            "width": img.size[0],
            "height": img.size[1],
            "full_screen": full_screen,
        }
        if embed_base64:
            buf = io.BytesIO()
            img.save(buf, format="PNG")
            result["image_base64"] = base64.b64encode(buf.getvalue()).decode("ascii")
        return result

    def click_xy(
        self,
        x: int,
        y: int,
        *,
        button: str = "left",
        absolute: bool = True,
        hwnd: int | None = None,
    ) -> dict[str, Any]:
        tx, ty = self._resolve_point(x, y, absolute=absolute, hwnd=hwnd)
        pyautogui.click(tx, ty, button=button)
        return {"ok": True, "x": tx, "y": ty, "button": button}

    def double_click_xy(
        self,
        x: int,
        y: int,
        *,
        button: str = "left",
        absolute: bool = True,
        hwnd: int | None = None,
    ) -> dict[str, Any]:
        tx, ty = self._resolve_point(x, y, absolute=absolute, hwnd=hwnd)
        pyautogui.doubleClick(tx, ty, button=button)
        return {"ok": True, "x": tx, "y": ty, "button": button}

    def drag_mouse(
        self,
        x1: int,
        y1: int,
        x2: int,
        y2: int,
        *,
        absolute: bool = True,
        hwnd: int | None = None,
        duration: float = 0.25,
        button: str = "left",
    ) -> dict[str, Any]:
        sx, sy = self._resolve_point(x1, y1, absolute=absolute, hwnd=hwnd)
        ex, ey = self._resolve_point(x2, y2, absolute=absolute, hwnd=hwnd)
        pyautogui.moveTo(sx, sy)
        pyautogui.dragTo(ex, ey, duration=duration, button=button)
        return {"ok": True, "start": [sx, sy], "end": [ex, ey], "button": button}

    def move_mouse(self, x: int, y: int) -> dict[str, Any]:
        pyautogui.moveTo(x, y)
        return {"ok": True, "x": x, "y": y}

    def scroll(self, clicks: int, *, x: int | None = None, y: int | None = None) -> dict[str, Any]:
        if x is not None and y is not None:
            pyautogui.moveTo(x, y)
        pyautogui.scroll(clicks)
        return {"ok": True, "clicks": clicks, "x": x, "y": y}

    def type_text(self, text: str, interval: float = 0.01) -> dict[str, Any]:
        pyautogui.write(text, interval=interval)
        return {"ok": True, "typed": len(text)}

    def send_hotkey(self, *keys: str) -> dict[str, Any]:
        normalized = [self._normalize_key(k) for k in keys if k]
        if not normalized:
            raise ValueError("At least one key is required")
        pyautogui.hotkey(*normalized)
        return {"ok": True, "keys": normalized}

    def find_element(
        self,
        window_title_regex: str,
        *,
        name: str | None = None,
        auto_id: str | None = None,
        control_type: str | None = None,
        found_index: int = 0,
        timeout_sec: float = 2.0,
    ) -> dict[str, Any]:
        wrapper = self._resolve_element(
            window_title_regex=window_title_regex,
            name=name,
            auto_id=auto_id,
            control_type=control_type,
            found_index=found_index,
            timeout_sec=timeout_sec,
        )
        return self._element_to_dict(wrapper)

    def click_element(
        self,
        window_title_regex: str,
        *,
        name: str | None = None,
        auto_id: str | None = None,
        control_type: str | None = None,
        found_index: int = 0,
        timeout_sec: float = 2.0,
        button: str = "left",
    ) -> dict[str, Any]:
        wrapper = self._resolve_element(
            window_title_regex=window_title_regex,
            name=name,
            auto_id=auto_id,
            control_type=control_type,
            found_index=found_index,
            timeout_sec=timeout_sec,
        )
        wrapper.set_focus()
        wrapper.click_input(button=button)
        out = self._element_to_dict(wrapper)
        out["ok"] = True
        out["button"] = button
        return out

    def get_uia_tree(
        self,
        window_title_regex: str,
        *,
        max_depth: int = 3,
        max_children_per_node: int = 50,
    ) -> dict[str, Any]:
        window = self._resolve_window(window_title_regex)
        wrapper = window.wrapper_object()
        return {
            "ok": True,
            "tree": self._serialize_wrapper(
                wrapper,
                depth=0,
                max_depth=max_depth,
                max_children_per_node=max_children_per_node,
            ),
        }

    def tail_log(self, filename: str | None = None, lines: int = 200) -> dict[str, Any]:
        path = self._resolve_log_path(filename)
        if not path or not path.exists():
            return {"ok": False, "error": "log file not found"}
        content = path.read_text(encoding="utf-8", errors="ignore").splitlines()[-lines:]
        return {"ok": True, "path": str(path), "content": "\n".join(content)}

    def collect_recent_logs(self, minutes: int = 120, output_dir: str | None = None) -> dict[str, Any]:
        if not self.app_log_dir.exists():
            return {"ok": False, "error": f"log dir not found: {self.app_log_dir}"}
        cutoff = time.time() - minutes * 60
        out_dir = Path(output_dir) if output_dir else Path.cwd() / "artifacts" / f"logs-{int(time.time())}"
        out_dir.mkdir(parents=True, exist_ok=True)
        copied: list[str] = []
        for item in sorted(self.app_log_dir.glob("**/*")):
            if not item.is_file():
                continue
            if item.stat().st_mtime < cutoff:
                continue
            destination = out_dir / item.name
            shutil.copy2(item, destination)
            copied.append(str(destination))
        return {"ok": True, "output_dir": str(out_dir), "files": copied}

    def _resolve_hwnd_from_title(self, title_regex: str) -> int:
        result = self.wait_main_window(title_regex=title_regex, timeout_sec=0.1)
        if result.get("ok"):
            return int(result["window"]["hwnd"])
        raise RuntimeError(result["error"])

    def _primary_monitor_bbox(self) -> dict[str, int]:
        with mss.mss() as sct:
            monitor = sct.monitors[1]
        return {
            "left": monitor["left"],
            "top": monitor["top"],
            "width": monitor["width"],
            "height": monitor["height"],
        }

    def _resolve_point(self, x: int, y: int, *, absolute: bool, hwnd: int | None) -> tuple[int, int]:
        if absolute or hwnd is None:
            return int(x), int(y)
        rect = self.get_window_rect(hwnd)
        return int(rect["left"] + x), int(rect["top"] + y)

    def _resolve_window(self, window_title_regex: str):
        spec = self._desktop.window(title_re=window_title_regex)
        spec.wait("exists visible ready", timeout=10)
        return spec

    def _resolve_element(
        self,
        *,
        window_title_regex: str,
        name: str | None,
        auto_id: str | None,
        control_type: str | None,
        found_index: int,
        timeout_sec: float,
    ):
        if not any([name, auto_id, control_type]):
            raise ValueError("At least one of name, auto_id, or control_type must be set")
        window = self._resolve_window(window_title_regex)
        criteria: dict[str, Any] = {"found_index": found_index}
        if name:
            criteria["title"] = name
        if auto_id:
            criteria["auto_id"] = auto_id
        if control_type:
            criteria["control_type"] = control_type
        spec = window.child_window(**criteria)
        spec.wait("exists ready", timeout=timeout_sec)
        return spec.wrapper_object()

    def _serialize_wrapper(
        self,
        wrapper,
        *,
        depth: int,
        max_depth: int,
        max_children_per_node: int,
    ) -> dict[str, Any]:
        info = wrapper.element_info
        rect = wrapper.rectangle()
        node: dict[str, Any] = {
            "name": getattr(info, "name", ""),
            "control_type": getattr(info, "control_type", ""),
            "automation_id": getattr(info, "automation_id", ""),
            "class_name": getattr(info, "class_name", ""),
            "rectangle": {
                "left": rect.left,
                "top": rect.top,
                "right": rect.right,
                "bottom": rect.bottom,
                "width": rect.width(),
                "height": rect.height(),
            },
            "children": [],
        }
        if depth >= max_depth:
            return node
        try:
            children = wrapper.children()
        except Exception:
            children = []
        for child in list(children)[:max_children_per_node]:
            try:
                node["children"].append(
                    self._serialize_wrapper(
                        child,
                        depth=depth + 1,
                        max_depth=max_depth,
                        max_children_per_node=max_children_per_node,
                    )
                )
            except Exception:
                continue
        return node

    def _element_to_dict(self, wrapper) -> dict[str, Any]:
        info = wrapper.element_info
        rect = wrapper.rectangle()
        return {
            "name": getattr(info, "name", ""),
            "control_type": getattr(info, "control_type", ""),
            "automation_id": getattr(info, "automation_id", ""),
            "class_name": getattr(info, "class_name", ""),
            "rectangle": {
                "left": rect.left,
                "top": rect.top,
                "right": rect.right,
                "bottom": rect.bottom,
                "width": rect.width(),
                "height": rect.height(),
                "center_x": rect.left + rect.width() // 2,
                "center_y": rect.top + rect.height() // 2,
            },
        }

    def _resolve_log_path(self, filename: str | None) -> Path | None:
        if filename:
            path = self.app_log_dir / filename
            return path if path.exists() else None
        if not self.app_log_dir.exists():
            return None
        files = [p for p in self.app_log_dir.glob("**/*") if p.is_file()]
        if not files:
            return None
        files.sort(key=lambda p: p.stat().st_mtime, reverse=True)
        return files[0]

    @staticmethod
    def _normalize_key(key: str) -> str:
        aliases = {
            "CTRL": "ctrl",
            "CONTROL": "ctrl",
            "SHIFT": "shift",
            "ALT": "alt",
            "META": "win",
            "CMD": "win",
            "SUPER": "win",
            "ENTER": "enter",
            "RETURN": "enter",
            "ESC": "esc",
            "ESCAPE": "esc",
            "SPACE": "space",
            "TAB": "tab",
            "BACKSPACE": "backspace",
            "DELETE": "delete",
            "INSERT": "insert",
            "HOME": "home",
            "END": "end",
            "PAGEUP": "pageup",
            "PAGEDOWN": "pagedown",
            "ARROWLEFT": "left",
            "ARROWRIGHT": "right",
            "ARROWUP": "up",
            "ARROWDOWN": "down",
        }
        upper = key.strip().upper()
        return aliases.get(upper, key.strip().lower())
