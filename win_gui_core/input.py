from __future__ import annotations

from contextlib import contextmanager
from typing import Any, Iterable

import pyautogui

from .errors import CoordinateTranslationError, SessionNotInitializedError
from .session import CoordSpace, Viewport


pyautogui.FAILSAFE = True
pyautogui.PAUSE = 0.03


KEY_ALIASES = {
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


def normalize_key(key: str) -> str:
    upper = key.strip().upper()
    return KEY_ALIASES.get(upper, key.strip().lower())


def normalize_drag_path(path: Any) -> list[tuple[int, int]]:
    points: list[tuple[int, int]] = []
    for item in path:
        if isinstance(item, dict):
            points.append((int(item["x"]), int(item["y"])))
        elif hasattr(item, "x") and hasattr(item, "y"):
            points.append((int(item.x), int(item.y)))
        else:
            x, y = item
            points.append((int(x), int(y)))
    return points


def viewport_to_screen(x: int, y: int, viewport: Viewport) -> tuple[int, int]:
    if x < 0 or y < 0:
        raise CoordinateTranslationError("Viewport coordinates must be non-negative.")
    if x > viewport.width or y > viewport.height:
        raise CoordinateTranslationError(
            f"Viewport coordinates {(x, y)} fall outside {(viewport.width, viewport.height)}."
        )
    return (
        int(viewport.left + x * viewport.scale_x),
        int(viewport.top + y * viewport.scale_y),
    )


@contextmanager
def with_modifiers(keys: Iterable[str] | None):
    normalized = [normalize_key(key) for key in (keys or [])]
    for key in normalized:
        pyautogui.keyDown(key)
    try:
        yield
    finally:
        for key in reversed(normalized):
            pyautogui.keyUp(key)


class InputController:
    def resolve_point(self, x: int, y: int, *, coord_space: CoordSpace, viewport: Viewport | None) -> tuple[int, int]:
        if coord_space == "screen":
            return int(x), int(y)
        if viewport is None:
            raise SessionNotInitializedError("Viewport-relative actions require an active session viewport.")
        return viewport_to_screen(int(x), int(y), viewport)

    def move_to(self, x: int, y: int, *, coord_space: CoordSpace, viewport: Viewport | None) -> dict[str, Any]:
        tx, ty = self.resolve_point(x, y, coord_space=coord_space, viewport=viewport)
        pyautogui.moveTo(tx, ty)
        return {"ok": True, "x": tx, "y": ty, "coord_space": coord_space}

    def click_point(
        self,
        x: int,
        y: int,
        *,
        coord_space: CoordSpace,
        viewport: Viewport | None,
        button: str = "left",
        clicks: int = 1,
    ) -> dict[str, Any]:
        tx, ty = self.resolve_point(x, y, coord_space=coord_space, viewport=viewport)
        pyautogui.click(tx, ty, button=button, clicks=clicks)
        return {"ok": True, "x": tx, "y": ty, "coord_space": coord_space, "button": button, "clicks": clicks}

    def drag_path(
        self,
        path: list[tuple[int, int]],
        *,
        coord_space: CoordSpace,
        viewport: Viewport | None,
        button: str = "left",
    ) -> dict[str, Any]:
        if len(path) < 2:
            raise CoordinateTranslationError("Drag actions require at least two points.")
        translated = [self.resolve_point(x, y, coord_space=coord_space, viewport=viewport) for x, y in path]
        start_x, start_y = translated[0]
        pyautogui.moveTo(start_x, start_y)
        pyautogui.mouseDown(button=button)
        try:
            for x, y in translated[1:]:
                pyautogui.moveTo(x, y)
        finally:
            pyautogui.mouseUp(button=button)
        return {"ok": True, "path": translated, "coord_space": coord_space, "button": button}

    def scroll_at(
        self,
        clicks: int,
        *,
        coord_space: CoordSpace,
        viewport: Viewport | None,
        x: int | None = None,
        y: int | None = None,
    ) -> dict[str, Any]:
        if x is not None and y is not None:
            tx, ty = self.resolve_point(x, y, coord_space=coord_space, viewport=viewport)
            pyautogui.moveTo(tx, ty)
        else:
            position = pyautogui.position()
            tx, ty = position.x, position.y
        pyautogui.scroll(clicks)
        return {"ok": True, "clicks": clicks, "x": tx, "y": ty, "coord_space": coord_space}

    def type_text(self, text: str, interval: float = 0.01) -> dict[str, Any]:
        pyautogui.write(text, interval=interval)
        return {"ok": True, "typed": len(text)}

    def send_hotkey(self, *keys: str) -> dict[str, Any]:
        normalized = [normalize_key(key) for key in keys if key]
        if not normalized:
            raise ValueError("At least one hotkey is required.")
        pyautogui.hotkey(*normalized)
        return {"ok": True, "keys": normalized}
