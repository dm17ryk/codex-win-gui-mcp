from __future__ import annotations

import base64
import io
import time
from pathlib import Path
from typing import Any

import mss
from PIL import Image

from .errors import ScreenshotError, SessionNotInitializedError
from .session import TargetSession, Viewport
from .windows import WindowManager


class ScreenshotManager:
    def __init__(self, window_manager: WindowManager) -> None:
        self.window_manager = window_manager

    def capture(
        self,
        *,
        session: TargetSession | None,
        mode: str,
        region: dict[str, int] | None = None,
        embed_base64: bool = False,
        screenshots_dir: str | None = None,
    ) -> dict[str, Any]:
        viewport = self._resolve_viewport(session=session, mode=mode, region=region)
        bbox = {
            "left": viewport.left,
            "top": viewport.top,
            "width": viewport.width,
            "height": viewport.height,
        }
        try:
            with mss.mss() as sct:
                shot = sct.grab(bbox)
                image = Image.frombytes("RGB", shot.size, shot.rgb)
        except Exception as exc:
            raise ScreenshotError(f"Unable to capture screenshot: {exc}") from exc

        output_dir = Path(screenshots_dir or Path.cwd() / "artifacts" / "screenshots")
        output_dir.mkdir(parents=True, exist_ok=True)
        path = output_dir / f"screenshot-{int(time.time() * 1000)}.png"
        image.save(path)
        result: dict[str, Any] = {
            "ok": True,
            "path": str(path),
            "viewport": viewport.to_dict(),
        }
        if embed_base64:
            buffer = io.BytesIO()
            image.save(buffer, format="PNG")
            result["image_base64"] = base64.b64encode(buffer.getvalue()).decode("ascii")
        return result

    def _resolve_viewport(
        self,
        *,
        session: TargetSession | None,
        mode: str,
        region: dict[str, int] | None,
    ) -> Viewport:
        captured_at = time.time()
        if mode == "full_screen":
            bbox = self.window_manager.primary_monitor_bbox()
            return Viewport(
                mode="full_screen",
                left=bbox["left"],
                top=bbox["top"],
                width=bbox["width"],
                height=bbox["height"],
                hwnd=None,
                pid=None,
                title=None,
                monitor_index=1,
                captured_at=captured_at,
                coord_space="screen",
            )
        if session is None:
            raise SessionNotInitializedError("A session is required for window or region screenshots.")
        if mode == "window":
            if session.hwnd is None:
                raise ScreenshotError("The active session does not have a resolved hwnd.")
            rect = self.window_manager.get_window_rect(session.hwnd)
            return Viewport(
                mode="window",
                left=rect["left"],
                top=rect["top"],
                width=rect["width"],
                height=rect["height"],
                hwnd=session.hwnd,
                pid=session.pid,
                title=session.title_regex,
                monitor_index=None,
                captured_at=captured_at,
                coord_space="viewport",
            )
        if mode == "region":
            if region is None:
                raise ScreenshotError("Region mode requires an explicit region payload.")
            if region.get("absolute", False):
                left = int(region["x"])
                top = int(region["y"])
            else:
                base_viewport = session.viewport
                if base_viewport is None:
                    raise ScreenshotError("Relative region capture requires an existing viewport.")
                left = int(base_viewport.left + region["x"])
                top = int(base_viewport.top + region["y"])
            return Viewport(
                mode="region",
                left=left,
                top=top,
                width=int(region["width"]),
                height=int(region["height"]),
                hwnd=session.hwnd,
                pid=session.pid,
                title=session.title_regex,
                monitor_index=None,
                captured_at=captured_at,
                coord_space="viewport",
            )
        raise ScreenshotError(f"Unsupported capture mode: {mode}")
