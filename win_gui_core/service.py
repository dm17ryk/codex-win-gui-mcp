from __future__ import annotations

import os
import subprocess
import time
from pathlib import Path
from typing import Any

import psutil

from adapters.klogg_adapter import KloggAdapter
from adapters.qt_adapter import QtAdapter

from .artifacts import ArtifactManager
from .input import InputController, normalize_drag_path
from .logs import LogManager
from .screenshots import ScreenshotManager
from .session import SessionStore, Viewport
from .uia import UIAutomationService
from .windows import WindowManager


class WinGuiService:
    def __init__(self) -> None:
        self.app_exe = os.environ.get("APP_EXE", "")
        self.app_workdir = os.environ.get("APP_WORKDIR", "")
        self.app_log_dir = Path(os.environ.get("APP_LOG_DIR", "logs"))
        self.app_dump_dir = Path(os.environ["APP_DUMP_DIR"]) if os.environ.get("APP_DUMP_DIR") else None
        self.main_window_title_regex = os.environ.get("MAIN_WINDOW_TITLE_REGEX", ".*")
        self.qt_dump_arg = os.environ.get("APP_STATE_DUMP_ARG", "--dump-state-json")
        self.qt_automation_env = os.environ.get("QT_AUTOMATION_ENV_VAR", "KLOGG_AUTOMATION")
        self.artifacts_root = Path.cwd() / "artifacts" / "sessions"
        self.sessions = SessionStore(self.artifacts_root)
        self.windows = WindowManager(self.main_window_title_regex)
        self.input = InputController()
        self.screenshots = ScreenshotManager(self.windows)
        self.uia = UIAutomationService(self.input)
        self.logs = LogManager(self.app_log_dir, self.app_dump_dir)
        self.artifacts = ArtifactManager(self.sessions, self.logs)
        self.qt_adapter = QtAdapter(
            app_exe=self.app_exe,
            app_workdir=self.app_workdir,
            dump_arg=self.qt_dump_arg,
            automation_env_var=self.qt_automation_env,
        )
        self.klogg_adapter = KloggAdapter(self.qt_adapter)
        self._last_pid: int | None = None

    def ping(self) -> dict[str, Any]:
        return {"ok": True, "message": "win-gui MCP is alive"}

    def launch_app(self, args: list[str] | None = None) -> dict[str, Any]:
        if not self.app_exe:
            raise RuntimeError("APP_EXE is not set")
        env_args = os.environ.get("APP_ARGS", "").split() if os.environ.get("APP_ARGS") else []
        cmd = [self.app_exe, *env_args, *(args or [])]
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
        for current in reversed(targets):
            try:
                current.terminate()
                terminated.append(current.pid)
            except psutil.NoSuchProcess:
                pass
        _, alive = psutil.wait_procs(targets, timeout=timeout_sec)
        for current in alive:
            try:
                current.kill()
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

    def create_session(
        self,
        title_regex: str | None = None,
        pid: int | None = None,
        adapter: str | None = None,
        capture_mode: str = "window",
    ) -> dict[str, Any]:
        resolved_title = title_regex or self.main_window_title_regex
        resolved_pid = pid or self._last_pid
        hwnd: int | None = None
        target_pid: int | None = resolved_pid
        if capture_mode != "full_screen":
            window = self.windows.resolve_window(title_regex=resolved_title, pid=resolved_pid, timeout_sec=10.0)
            hwnd = int(window["hwnd"])
            target_pid = int(window["pid"])
        session = self.sessions.create(
            title_regex=resolved_title,
            pid=target_pid,
            hwnd=hwnd,
            capture_mode=capture_mode,  # type: ignore[arg-type]
            adapter=adapter,  # type: ignore[arg-type]
        )
        self.sessions.trace("session_created", session=session.to_dict())
        return {"ok": True, "session": session.to_dict()}

    def get_session(self) -> dict[str, Any]:
        return {"ok": True, "session": self.sessions.get().to_dict()}

    def refresh_session(self) -> dict[str, Any]:
        session = self.sessions.get()
        if session.capture_mode == "full_screen":
            self.sessions.trace("viewport_refreshed", session_id=session.session_id, mode="full_screen")
            return {"ok": True, "session": session.to_dict()}
        window = self.windows.resolve_window(title_regex=session.title_regex, pid=session.pid, timeout_sec=10.0)
        session.hwnd = int(window["hwnd"])
        session.pid = int(window["pid"])
        self.sessions.trace("viewport_refreshed", session_id=session.session_id, hwnd=session.hwnd, pid=session.pid)
        return {"ok": True, "session": session.to_dict()}

    def close_session(self) -> dict[str, Any]:
        return self.sessions.close()

    def enumerate_monitors(self) -> dict[str, Any]:
        return self.windows.enumerate_monitors()

    def restore_window(self, hwnd: int | None = None) -> dict[str, Any]:
        session = self.sessions.maybe_get()
        target_hwnd = hwnd or (session.hwnd if session else None)
        if target_hwnd is None:
            raise RuntimeError("No hwnd available to restore.")
        return self.windows.restore_window(target_hwnd)

    def wait_window_stable(self, timeout_sec: float = 5.0) -> dict[str, Any]:
        session = self.sessions.get()
        result = self.windows.wait_window_stable(title_regex=session.title_regex, pid=session.pid, timeout_sec=timeout_sec)
        self.sessions.trace("assertion", kind="wait_window_stable", result=result)
        return result

    def capture_screenshot(
        self,
        mode: str = "window",
        region: dict[str, int] | None = None,
        embed_base64: bool = False,
    ) -> dict[str, Any]:
        session = self.sessions.maybe_get()
        result = self.screenshots.capture(
            session=session,
            mode=mode,
            region=region,
            embed_base64=embed_base64,
            screenshots_dir=session.screenshots_dir if session else None,
        )
        if session is not None:
            session.last_screenshot_path = result["path"]
            self.sessions.set_viewport(self._viewport_from_result(result))
            self.sessions.trace("screenshot", path=result["path"], viewport=result["viewport"])
        return result

    def capture_region(
        self,
        x: int,
        y: int,
        width: int,
        height: int,
        absolute: bool = True,
        hwnd: int | None = None,
        embed_base64: bool = False,
    ) -> dict[str, Any]:
        if hwnd is not None:
            session = self.sessions.get()
            session.hwnd = hwnd
        region = {"x": x, "y": y, "width": width, "height": height, "absolute": absolute}
        return self.capture_screenshot(mode="region", region=region, embed_base64=embed_base64)

    def click_point(self, x: int, y: int, coord_space: str = "viewport", button: str = "left") -> dict[str, Any]:
        session = self.sessions.get()
        result = self.input.click_point(x, y, coord_space=coord_space, viewport=session.viewport, button=button)
        self.sessions.trace("action_result", action="click_point", result=result)
        return result

    def double_click_point(self, x: int, y: int, coord_space: str = "viewport", button: str = "left") -> dict[str, Any]:
        session = self.sessions.get()
        result = self.input.click_point(
            x,
            y,
            coord_space=coord_space,
            viewport=session.viewport,
            button=button,
            clicks=2,
        )
        self.sessions.trace("action_result", action="double_click_point", result=result)
        return result

    def drag_path(self, path: list[dict[str, int]], coord_space: str = "viewport", button: str = "left") -> dict[str, Any]:
        session = self.sessions.get()
        result = self.input.drag_path(
            normalize_drag_path(path),
            coord_space=coord_space,
            viewport=session.viewport,
            button=button,
        )
        self.sessions.trace("action_result", action="drag_path", result=result)
        return result

    def scroll_at(self, clicks: int, x: int | None = None, y: int | None = None, coord_space: str = "viewport") -> dict[str, Any]:
        session = self.sessions.get()
        result = self.input.scroll_at(clicks, coord_space=coord_space, viewport=session.viewport, x=x, y=y)
        self.sessions.trace("action_result", action="scroll_at", result=result)
        return result

    def type_text(self, text: str, interval: float = 0.01) -> dict[str, Any]:
        result = self.input.type_text(text, interval=interval)
        if self.sessions.maybe_get():
            self.sessions.trace("action_result", action="type_text", result=result)
        return result

    def send_hotkey(self, keys: list[str]) -> dict[str, Any]:
        result = self.input.send_hotkey(*keys)
        if self.sessions.maybe_get():
            self.sessions.trace("action_result", action="send_hotkey", result=result)
        return result

    def find_element(self, **kwargs: Any) -> dict[str, Any]:
        result = self.uia.find_element(**kwargs)
        if self.sessions.maybe_get():
            self.sessions.trace("uia_query", action="find_element", result=result)
        return result

    def wait_for_element(self, **kwargs: Any) -> dict[str, Any]:
        result = self.uia.wait_for_element(**kwargs)
        if self.sessions.maybe_get():
            self.sessions.trace("assertion", kind="wait_for_element", result=result)
        return result

    def wait_for_element_gone(self, **kwargs: Any) -> dict[str, Any]:
        result = self.uia.wait_for_element_gone(**kwargs)
        if self.sessions.maybe_get():
            self.sessions.trace("assertion", kind="wait_for_element_gone", result=result)
        return result

    def assert_element(self, **kwargs: Any) -> dict[str, Any]:
        result = self.uia.assert_element(**kwargs)
        if self.sessions.maybe_get():
            self.sessions.trace("assertion", kind="assert_element", result=result)
        return result

    def click_element(self, **kwargs: Any) -> dict[str, Any]:
        result = self.uia.click_element(**kwargs)
        if self.sessions.maybe_get():
            self.sessions.trace("action_result", action="click_element", result=result)
        return result

    def double_click_element(self, **kwargs: Any) -> dict[str, Any]:
        result = self.uia.double_click_element(**kwargs)
        if self.sessions.maybe_get():
            self.sessions.trace("action_result", action="double_click_element", result=result)
        return result

    def right_click_element(self, **kwargs: Any) -> dict[str, Any]:
        result = self.uia.right_click_element(**kwargs)
        if self.sessions.maybe_get():
            self.sessions.trace("action_result", action="right_click_element", result=result)
        return result

    def drag_element_to_point(self, *, x: int, y: int, coord_space: str = "viewport", **kwargs: Any) -> dict[str, Any]:
        session = self.sessions.get()
        result = self.uia.drag_element_to_point(x=x, y=y, coord_space=coord_space, viewport=session.viewport, **kwargs)
        self.sessions.trace("action_result", action="drag_element_to_point", result=result)
        return result

    def drag_element_to_element(self, *, source: dict[str, Any], target: dict[str, Any]) -> dict[str, Any]:
        session = self.sessions.get()
        result = self.uia.drag_element_to_element(source=source, target=target, viewport=session.viewport)
        self.sessions.trace("action_result", action="drag_element_to_element", result=result)
        return result

    def get_uia_tree(self, window_title_regex: str, max_depth: int = 3, max_children_per_node: int = 50) -> dict[str, Any]:
        session = self.sessions.maybe_get()
        output_path = None
        if session is not None:
            output_path = str(Path(session.artifact_dir) / "uia-tree.json")
        result = self.uia.get_uia_tree(
            window_title_regex=window_title_regex,
            max_depth=max_depth,
            max_children_per_node=max_children_per_node,
            output_path=output_path,
        )
        if session is not None:
            session.ui_tree_path = output_path
            self.sessions.trace("uia_query", action="get_uia_tree", result={"path": output_path})
        return result

    def assert_window_title(self, window_title_regex: str, expected_pattern: str) -> dict[str, Any]:
        result = self.uia.assert_window_title(window_title_regex, expected_pattern)
        if self.sessions.maybe_get():
            self.sessions.trace("assertion", kind="assert_window_title", result=result)
        return result

    def assert_status_text(self, window_title_regex: str, expected_text: str, timeout_sec: float = 2.0) -> dict[str, Any]:
        result = self.uia.assert_status_text(window_title_regex, expected_text, timeout_sec=timeout_sec)
        if self.sessions.maybe_get():
            self.sessions.trace("assertion", kind="assert_status_text", result=result)
        return result

    def tail_log(self, filename: str | None = None, lines: int = 200) -> dict[str, Any]:
        return self.logs.tail_log(filename=filename, lines=lines)

    def assert_log_contains(self, expected_text: str, filename: str | None = None, lines: int = 400) -> dict[str, Any]:
        result = self.logs.assert_log_contains(expected_text=expected_text, filename=filename, lines=lines)
        if self.sessions.maybe_get():
            self.sessions.trace("assertion", kind="assert_log_contains", result=result)
        return result

    def collect_recent_logs(self, minutes: int = 120, output_dir: str | None = None) -> dict[str, Any]:
        return self.logs.collect_recent_logs(minutes=minutes, output_dir=output_dir)

    def collect_event_logs(self, minutes: int = 60, output_dir: str | None = None) -> dict[str, Any]:
        return self.logs.collect_event_logs(minutes=minutes, output_dir=output_dir)

    def collect_dumps(self, output_dir: str | None = None) -> dict[str, Any]:
        return self.logs.collect_dumps(output_dir=output_dir)

    def get_process_tree(self, pid: int | None = None) -> dict[str, Any]:
        session = self.sessions.maybe_get()
        target_pid = pid or (session.pid if session else None)
        return self.logs.get_process_tree(pid=target_pid)

    def wait_process_idle(self, pid: int | None = None, cpu_threshold: float = 2.0, timeout_sec: float = 10.0) -> dict[str, Any]:
        session = self.sessions.maybe_get()
        target_pid = pid or (session.pid if session else None)
        result = self.logs.wait_process_idle(pid=target_pid, cpu_threshold=cpu_threshold, timeout_sec=timeout_sec)
        if self.sessions.maybe_get():
            self.sessions.trace("assertion", kind="wait_process_idle", result=result)
        return result

    def create_artifact_bundle(self, reason: str | None = None) -> dict[str, Any]:
        session = self.sessions.get()
        ui_tree = None
        if session.title_regex:
            try:
                ui_tree = self.get_uia_tree(window_title_regex=session.title_regex)["tree"]
            except Exception:
                ui_tree = None
        qt_state = None
        if session.adapter in {"qt", "klogg"}:
            try:
                qt_state = self.qt_adapter.dump_qt_state()
            except Exception:
                qt_state = None
        result = self.artifacts.create_bundle(session, reason=reason, ui_tree=ui_tree, qt_state=qt_state)
        self.sessions.trace("artifact_bundle", result=result)
        return result

    def list_artifacts(self) -> dict[str, Any]:
        return self.artifacts.list_artifacts()

    def dump_qt_state(self) -> dict[str, Any]:
        state = self.qt_adapter.dump_qt_state()
        if self.sessions.maybe_get():
            self.sessions.trace("adapter_call", adapter="qt", action="dump_qt_state")
        return {"ok": True, "state": state}

    def find_qt_object(self, object_name: str | None = None, accessible_name: str | None = None, role: str | None = None) -> dict[str, Any]:
        result = self.qt_adapter.find_qt_object(object_name=object_name, accessible_name=accessible_name, role=role)
        if self.sessions.maybe_get():
            self.sessions.trace("adapter_call", adapter="qt", action="find_qt_object", locator=result["locator"])
        return result

    def click_qt_object(self, object_name: str | None = None, accessible_name: str | None = None, role: str | None = None) -> dict[str, Any]:
        result = self.qt_adapter.click_qt_object(object_name=object_name, accessible_name=accessible_name, role=role)
        if self.sessions.maybe_get():
            self.sessions.trace("adapter_call", adapter="qt", action="click_qt_object", locator=result["locator"])
        return result

    def invoke_qt_action(self, action_name: str) -> dict[str, Any]:
        result = self.qt_adapter.invoke_qt_action(action_name)
        if self.sessions.maybe_get():
            self.sessions.trace("adapter_call", adapter="qt", action="invoke_qt_action", action_name=action_name)
        return result

    def set_qt_value(self, value: str, object_name: str | None = None, accessible_name: str | None = None) -> dict[str, Any]:
        result = self.qt_adapter.set_qt_value(object_name=object_name, accessible_name=accessible_name, value=value)
        if self.sessions.maybe_get():
            self.sessions.trace("adapter_call", adapter="qt", action="set_qt_value")
        return result

    def toggle_qt_control(self, object_name: str | None = None, accessible_name: str | None = None) -> dict[str, Any]:
        result = self.qt_adapter.toggle_qt_control(object_name=object_name, accessible_name=accessible_name)
        if self.sessions.maybe_get():
            self.sessions.trace("adapter_call", adapter="qt", action="toggle_qt_control")
        return result

    def klogg_open_log(self, path: str) -> dict[str, Any]:
        result = self.klogg_adapter.klogg_open_log(path)
        if self.sessions.maybe_get():
            self.sessions.trace("adapter_call", adapter="klogg", action="klogg_open_log", path=path)
        return result

    def klogg_search(self, text: str, regex: bool = False, case_sensitive: bool = False) -> dict[str, Any]:
        result = self.klogg_adapter.klogg_search(text=text, regex=regex, case_sensitive=case_sensitive)
        if self.sessions.maybe_get():
            self.sessions.trace("adapter_call", adapter="klogg", action="klogg_search", text=text)
        return result

    def klogg_get_state(self) -> dict[str, Any]:
        result = self.klogg_adapter.klogg_get_state()
        if self.sessions.maybe_get():
            self.sessions.trace("adapter_call", adapter="klogg", action="klogg_get_state")
        return result

    def klogg_get_active_tab(self) -> dict[str, Any]:
        result = self.klogg_adapter.klogg_get_active_tab()
        if self.sessions.maybe_get():
            self.sessions.trace("adapter_call", adapter="klogg", action="klogg_get_active_tab")
        return result

    def klogg_toggle_follow(self, enabled: bool | None = None) -> dict[str, Any]:
        result = self.klogg_adapter.klogg_toggle_follow(enabled=enabled)
        if self.sessions.maybe_get():
            self.sessions.trace("adapter_call", adapter="klogg", action="klogg_toggle_follow")
        return result

    def klogg_get_visible_range(self) -> dict[str, Any]:
        result = self.klogg_adapter.klogg_get_visible_range()
        if self.sessions.maybe_get():
            self.sessions.trace("adapter_call", adapter="klogg", action="klogg_get_visible_range")
        return result

    @staticmethod
    def _viewport_from_result(result: dict[str, Any]) -> Viewport:
        viewport = result["viewport"]
        return Viewport(
            mode=viewport["mode"],
            left=viewport["left"],
            top=viewport["top"],
            width=viewport["width"],
            height=viewport["height"],
            hwnd=viewport.get("hwnd"),
            pid=viewport.get("pid"),
            title=viewport.get("title"),
            monitor_index=viewport.get("monitor_index"),
            scale_x=viewport.get("scale_x", 1.0),
            scale_y=viewport.get("scale_y", 1.0),
            captured_at=viewport.get("captured_at", time.time()),
            coord_space=viewport.get("coord_space", "screen"),
        )
