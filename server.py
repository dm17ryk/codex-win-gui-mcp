from __future__ import annotations

from fastmcp import FastMCP

from win_gui_core.service import WinGuiService


mcp = FastMCP("win-gui")
service = WinGuiService()


@mcp.tool
def ping() -> dict:
    """Check whether the Windows GUI MCP server is responsive."""
    return service.ping()


@mcp.tool
def launch_app(args: list[str] | None = None) -> dict:
    """Launch the configured application with optional extra arguments."""
    return service.launch_app(args=args)


@mcp.tool
def close_app(pid: int | None = None, timeout_sec: float = 10.0) -> dict:
    """Close the configured application or an explicit process tree."""
    return service.close_app(pid=pid, timeout_sec=timeout_sec)


@mcp.tool
def restart_app(args: list[str] | None = None) -> dict:
    """Restart the configured application."""
    return service.restart_app(args=args)


@mcp.tool
def create_session(title_regex: str | None = None, pid: int | None = None, adapter: str | None = None, capture_mode: str = "window") -> dict:
    """Create or attach an active automation session for a window, region, or the full desktop."""
    return service.create_session(title_regex=title_regex, pid=pid, adapter=adapter, capture_mode=capture_mode)


@mcp.tool
def get_session() -> dict:
    """Return the active session metadata, including the last viewport and artifact paths."""
    return service.get_session()


@mcp.tool
def refresh_session() -> dict:
    """Refresh the active session by rebinding the target HWND and PID when needed."""
    return service.refresh_session()


@mcp.tool
def close_session() -> dict:
    """Close the active automation session without terminating the target application."""
    return service.close_session()


@mcp.tool
def enumerate_monitors() -> dict:
    """List the connected monitors and their desktop bounds."""
    return service.enumerate_monitors()


@mcp.tool
def restore_window(hwnd: int | None = None) -> dict:
    """Restore and foreground the session window or an explicit HWND."""
    return service.restore_window(hwnd=hwnd)


@mcp.tool
def wait_window_stable(timeout_sec: float = 5.0) -> dict:
    """Wait until the active session window stops moving or recreating."""
    return service.wait_window_stable(timeout_sec=timeout_sec)


@mcp.tool
def capture_screenshot(mode: str = "window", region: dict | None = None, embed_base64: bool = False) -> dict:
    """Capture a screenshot for the active session mode and return full viewport metadata."""
    return service.capture_screenshot(mode=mode, region=region, embed_base64=embed_base64)


@mcp.tool
def capture_region(
    x: int,
    y: int,
    width: int,
    height: int,
    absolute: bool = True,
    hwnd: int | None = None,
    embed_base64: bool = False,
) -> dict:
    """Capture an explicit region in screen coordinates or relative to the active viewport."""
    return service.capture_region(
        x=x,
        y=y,
        width=width,
        height=height,
        absolute=absolute,
        hwnd=hwnd,
        embed_base64=embed_base64,
    )


@mcp.tool
def click_point(x: int, y: int, coord_space: str = "viewport", button: str = "left") -> dict:
    """Click a point in viewport or desktop coordinates."""
    return service.click_point(x=x, y=y, coord_space=coord_space, button=button)


@mcp.tool
def double_click_point(x: int, y: int, coord_space: str = "viewport", button: str = "left") -> dict:
    """Double-click a point in viewport or desktop coordinates."""
    return service.double_click_point(x=x, y=y, coord_space=coord_space, button=button)


@mcp.tool
def drag_path(path: list[dict], coord_space: str = "viewport", button: str = "left") -> dict:
    """Drag along a point path expressed in viewport or desktop coordinates."""
    return service.drag_path(path=path, coord_space=coord_space, button=button)


@mcp.tool
def scroll_at(clicks: int, x: int | None = None, y: int | None = None, coord_space: str = "viewport") -> dict:
    """Scroll at a viewport-relative or desktop-relative point."""
    return service.scroll_at(clicks=clicks, x=x, y=y, coord_space=coord_space)


@mcp.tool
def type_text(text: str, interval: float = 0.01) -> dict:
    """Type text into the currently focused control."""
    return service.type_text(text=text, interval=interval)


@mcp.tool
def send_hotkey(keys: list[str]) -> dict:
    """Press a keyboard shortcut expressed as a list of key names."""
    return service.send_hotkey(keys=keys)


@mcp.tool
def find_element(
    window_title_regex: str,
    name: str | None = None,
    auto_id: str | None = None,
    control_type: str | None = None,
    found_index: int = 0,
    timeout_sec: float = 2.0,
) -> dict:
    """Find a UIA element in a target window by text, automation id, or control type."""
    return service.find_element(
        window_title_regex=window_title_regex,
        name=name,
        auto_id=auto_id,
        control_type=control_type,
        found_index=found_index,
        timeout_sec=timeout_sec,
    )


@mcp.tool
def wait_for_element(
    window_title_regex: str,
    name: str | None = None,
    auto_id: str | None = None,
    control_type: str | None = None,
    found_index: int = 0,
    timeout_sec: float = 2.0,
) -> dict:
    """Wait until a UIA element becomes available."""
    return service.wait_for_element(
        window_title_regex=window_title_regex,
        name=name,
        auto_id=auto_id,
        control_type=control_type,
        found_index=found_index,
        timeout_sec=timeout_sec,
    )


@mcp.tool
def wait_for_element_gone(
    window_title_regex: str,
    name: str | None = None,
    auto_id: str | None = None,
    control_type: str | None = None,
    found_index: int = 0,
    timeout_sec: float = 2.0,
) -> dict:
    """Wait until a UIA element is no longer present."""
    return service.wait_for_element_gone(
        window_title_regex=window_title_regex,
        name=name,
        auto_id=auto_id,
        control_type=control_type,
        found_index=found_index,
        timeout_sec=timeout_sec,
    )


@mcp.tool
def assert_element(
    window_title_regex: str,
    name: str | None = None,
    auto_id: str | None = None,
    control_type: str | None = None,
    found_index: int = 0,
    timeout_sec: float = 2.0,
) -> dict:
    """Assert that a UIA element is present."""
    return service.assert_element(
        window_title_regex=window_title_regex,
        name=name,
        auto_id=auto_id,
        control_type=control_type,
        found_index=found_index,
        timeout_sec=timeout_sec,
    )


@mcp.tool
def click_element(
    window_title_regex: str,
    name: str | None = None,
    auto_id: str | None = None,
    control_type: str | None = None,
    found_index: int = 0,
    timeout_sec: float = 2.0,
    button: str = "left",
) -> dict:
    """Click a UIA element."""
    return service.click_element(
        window_title_regex=window_title_regex,
        name=name,
        auto_id=auto_id,
        control_type=control_type,
        found_index=found_index,
        timeout_sec=timeout_sec,
        button=button,
    )


@mcp.tool
def double_click_element(
    window_title_regex: str,
    name: str | None = None,
    auto_id: str | None = None,
    control_type: str | None = None,
    found_index: int = 0,
    timeout_sec: float = 2.0,
) -> dict:
    """Double-click a UIA element."""
    return service.double_click_element(
        window_title_regex=window_title_regex,
        name=name,
        auto_id=auto_id,
        control_type=control_type,
        found_index=found_index,
        timeout_sec=timeout_sec,
    )


@mcp.tool
def right_click_element(
    window_title_regex: str,
    name: str | None = None,
    auto_id: str | None = None,
    control_type: str | None = None,
    found_index: int = 0,
    timeout_sec: float = 2.0,
) -> dict:
    """Right-click a UIA element."""
    return service.right_click_element(
        window_title_regex=window_title_regex,
        name=name,
        auto_id=auto_id,
        control_type=control_type,
        found_index=found_index,
        timeout_sec=timeout_sec,
    )


@mcp.tool
def drag_element_to_point(
    window_title_regex: str,
    x: int,
    y: int,
    coord_space: str = "viewport",
    name: str | None = None,
    auto_id: str | None = None,
    control_type: str | None = None,
    found_index: int = 0,
    timeout_sec: float = 2.0,
) -> dict:
    """Drag an element to a target point."""
    return service.drag_element_to_point(
        window_title_regex=window_title_regex,
        x=x,
        y=y,
        coord_space=coord_space,
        name=name,
        auto_id=auto_id,
        control_type=control_type,
        found_index=found_index,
        timeout_sec=timeout_sec,
    )


@mcp.tool
def drag_element_to_element(source: dict, target: dict) -> dict:
    """Drag one UIA element onto another UIA element."""
    return service.drag_element_to_element(source=source, target=target)


@mcp.tool
def get_uia_tree(window_title_regex: str, max_depth: int = 3, max_children_per_node: int = 50) -> dict:
    """Serialize part of the UIA tree for a target window."""
    return service.get_uia_tree(window_title_regex=window_title_regex, max_depth=max_depth, max_children_per_node=max_children_per_node)


@mcp.tool
def assert_window_title(window_title_regex: str, expected_pattern: str) -> dict:
    """Assert that a target window title matches a regular expression."""
    return service.assert_window_title(window_title_regex=window_title_regex, expected_pattern=expected_pattern)


@mcp.tool
def assert_status_text(window_title_regex: str, expected_text: str, timeout_sec: float = 2.0) -> dict:
    """Assert that a target window exposes status text containing the expected substring."""
    return service.assert_status_text(window_title_regex=window_title_regex, expected_text=expected_text, timeout_sec=timeout_sec)


@mcp.tool
def tail_log(filename: str | None = None, lines: int = 200) -> dict:
    """Read the last lines from the newest log or a named log file."""
    return service.tail_log(filename=filename, lines=lines)


@mcp.tool
def assert_log_contains(expected_text: str, filename: str | None = None, lines: int = 400) -> dict:
    """Assert that the newest or named log contains the expected text."""
    return service.assert_log_contains(expected_text=expected_text, filename=filename, lines=lines)


@mcp.tool
def collect_recent_logs(minutes: int = 120, output_dir: str | None = None) -> dict:
    """Copy recently modified logs while preserving their relative directory structure."""
    return service.collect_recent_logs(minutes=minutes, output_dir=output_dir)


@mcp.tool
def wait_process_idle(pid: int | None = None, cpu_threshold: float = 2.0, timeout_sec: float = 10.0) -> dict:
    """Wait until a process tree becomes mostly idle."""
    return service.wait_process_idle(pid=pid, cpu_threshold=cpu_threshold, timeout_sec=timeout_sec)


@mcp.tool
def create_artifact_bundle(reason: str | None = None) -> dict:
    """Collect screenshots, traces, logs, dumps, and state snapshots into a bundle."""
    return service.create_artifact_bundle(reason=reason)


@mcp.tool
def list_artifacts() -> dict:
    """List the stored session artifact directories."""
    return service.list_artifacts()


@mcp.tool
def collect_event_logs(minutes: int = 60, output_dir: str | None = None) -> dict:
    """Collect recent Windows Application event log entries."""
    return service.collect_event_logs(minutes=minutes, output_dir=output_dir)


@mcp.tool
def collect_dumps(output_dir: str | None = None) -> dict:
    """Collect crash dumps from the configured dump directory."""
    return service.collect_dumps(output_dir=output_dir)


@mcp.tool
def get_process_tree(pid: int | None = None) -> dict:
    """Return the target process tree rooted at the session PID or an explicit PID."""
    return service.get_process_tree(pid=pid)


@mcp.tool
def dump_qt_state() -> dict:
    """Run the target application's Qt state dump endpoint and return the parsed JSON."""
    return service.dump_qt_state()


@mcp.tool
def find_qt_object(object_name: str | None = None, accessible_name: str | None = None, role: str | None = None) -> dict:
    """Find an instrumented Qt object by objectName, accessibleName, or role."""
    return service.find_qt_object(object_name=object_name, accessible_name=accessible_name, role=role)


@mcp.tool
def click_qt_object(object_name: str | None = None, accessible_name: str | None = None, role: str | None = None) -> dict:
    """Resolve an instrumented Qt object intended for click-style interaction."""
    return service.click_qt_object(object_name=object_name, accessible_name=accessible_name, role=role)


@mcp.tool
def invoke_qt_action(action_name: str) -> dict:
    """Resolve an instrumented Qt action by name."""
    return service.invoke_qt_action(action_name=action_name)


@mcp.tool
def set_qt_value(value: str, object_name: str | None = None, accessible_name: str | None = None) -> dict:
    """Resolve an instrumented Qt value-bearing control."""
    return service.set_qt_value(value=value, object_name=object_name, accessible_name=accessible_name)


@mcp.tool
def toggle_qt_control(object_name: str | None = None, accessible_name: str | None = None) -> dict:
    """Resolve an instrumented Qt toggle control."""
    return service.toggle_qt_control(object_name=object_name, accessible_name=accessible_name)


@mcp.tool
def klogg_open_log(path: str) -> dict:
    """Prepare an instrumented klogg instance to open a log file."""
    return service.klogg_open_log(path=path)


@mcp.tool
def klogg_search(text: str, regex: bool = False, case_sensitive: bool = False) -> dict:
    """Execute or describe a klogg search request."""
    return service.klogg_search(text=text, regex=regex, case_sensitive=case_sensitive)


@mcp.tool
def klogg_get_state() -> dict:
    """Return the normalized instrumented klogg state snapshot."""
    return service.klogg_get_state()


@mcp.tool
def klogg_get_active_tab() -> dict:
    """Return the current klogg tab metadata."""
    return service.klogg_get_active_tab()


@mcp.tool
def klogg_toggle_follow(enabled: bool | None = None) -> dict:
    """Toggle or set klogg follow mode."""
    return service.klogg_toggle_follow(enabled=enabled)


@mcp.tool
def klogg_get_visible_range() -> dict:
    """Return the visible klogg line range."""
    return service.klogg_get_visible_range()


if __name__ == "__main__":
    mcp.run()
