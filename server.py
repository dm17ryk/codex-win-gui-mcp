from __future__ import annotations

from fastmcp import FastMCP

from win_gui_core import DesktopHarness


mcp = FastMCP("win-gui")
harness = DesktopHarness()


@mcp.tool
def ping() -> dict:
    return {"ok": True, "message": "win-gui MCP is alive"}


@mcp.tool
def launch_app(args: list[str] | None = None) -> dict:
    """Launch the configured Windows GUI application."""
    return harness.launch_app(args=args)


@mcp.tool
def close_app(pid: int | None = None) -> dict:
    """Close the configured app (or a specific pid)."""
    return harness.close_app(pid=pid)


@mcp.tool
def restart_app(args: list[str] | None = None) -> dict:
    """Restart the configured app."""
    return harness.restart_app(args=args)


@mcp.tool
def list_windows() -> list[dict]:
    """List top-level windows visible to the current desktop session."""
    return harness.list_windows()


@mcp.tool
def wait_main_window(title_regex: str | None = None, timeout_sec: float = 20.0, pid: int | None = None) -> dict:
    """Wait until a visible top-level window matches the regex."""
    return harness.wait_main_window(title_regex=title_regex, timeout_sec=timeout_sec, pid=pid)


@mcp.tool
def focus_window(hwnd: int) -> dict:
    """Bring a window to foreground."""
    return harness.focus_window(hwnd=hwnd)


@mcp.tool
def move_window(hwnd: int, x: int, y: int, width: int, height: int) -> dict:
    """Move/resize a window using Win32, not by dragging the title bar."""
    return harness.move_window(hwnd=hwnd, x=x, y=y, width=width, height=height)


@mcp.tool
def capture_screenshot(
    full_screen: bool = False,
    hwnd: int | None = None,
    title_regex: str | None = None,
    embed_base64: bool = False,
) -> dict:
    """Capture the full screen or a single window. Set embed_base64=true when the model needs pixels inline."""
    return harness.capture_screenshot(
        full_screen=full_screen,
        hwnd=hwnd,
        title_regex=title_regex,
        embed_base64=embed_base64,
    )


@mcp.tool
def click_xy(x: int, y: int, button: str = "left", absolute: bool = True, hwnd: int | None = None) -> dict:
    """Click at absolute screen coordinates or window-relative coordinates."""
    return harness.click_xy(x=x, y=y, button=button, absolute=absolute, hwnd=hwnd)


@mcp.tool
def double_click_xy(x: int, y: int, button: str = "left", absolute: bool = True, hwnd: int | None = None) -> dict:
    """Double-click at absolute screen coordinates or window-relative coordinates."""
    return harness.double_click_xy(x=x, y=y, button=button, absolute=absolute, hwnd=hwnd)


@mcp.tool
def drag_mouse(
    x1: int,
    y1: int,
    x2: int,
    y2: int,
    absolute: bool = True,
    hwnd: int | None = None,
    duration: float = 0.25,
    button: str = "left",
) -> dict:
    """Drag the mouse between two points."""
    return harness.drag_mouse(
        x1=x1,
        y1=y1,
        x2=x2,
        y2=y2,
        absolute=absolute,
        hwnd=hwnd,
        duration=duration,
        button=button,
    )


@mcp.tool
def move_mouse(x: int, y: int) -> dict:
    """Move the mouse cursor to absolute screen coordinates."""
    return harness.move_mouse(x=x, y=y)


@mcp.tool
def scroll(clicks: int, x: int | None = None, y: int | None = None) -> dict:
    """Scroll the wheel; positive is up, negative is down."""
    return harness.scroll(clicks=clicks, x=x, y=y)


@mcp.tool
def type_text(text: str, interval: float = 0.01) -> dict:
    """Type text into the currently focused control."""
    return harness.type_text(text=text, interval=interval)


@mcp.tool
def send_hotkey(keys: list[str]) -> dict:
    """Press a keyboard shortcut such as [\"ctrl\", \"shift\", \"p\"]."""
    return harness.send_hotkey(*keys)


@mcp.tool
def find_element(
    window_title_regex: str,
    name: str | None = None,
    auto_id: str | None = None,
    control_type: str | None = None,
    found_index: int = 0,
    timeout_sec: float = 2.0,
) -> dict:
    """Find a UIA element in the target window."""
    return harness.find_element(
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
    """Click a UIA element by name, automation id, or control type."""
    return harness.click_element(
        window_title_regex=window_title_regex,
        name=name,
        auto_id=auto_id,
        control_type=control_type,
        found_index=found_index,
        timeout_sec=timeout_sec,
        button=button,
    )


@mcp.tool
def get_uia_tree(window_title_regex: str, max_depth: int = 3, max_children_per_node: int = 50) -> dict:
    """Serialize part of the UIA tree for a target window."""
    return harness.get_uia_tree(
        window_title_regex=window_title_regex,
        max_depth=max_depth,
        max_children_per_node=max_children_per_node,
    )


@mcp.tool
def tail_log(filename: str | None = None, lines: int = 200) -> dict:
    """Read the last N lines from the newest log or a specific log file."""
    return harness.tail_log(filename=filename, lines=lines)


@mcp.tool
def collect_recent_logs(minutes: int = 120, output_dir: str | None = None) -> dict:
    """Copy recently modified logs into an artifacts directory."""
    return harness.collect_recent_logs(minutes=minutes, output_dir=output_dir)


if __name__ == "__main__":
    mcp.run()
