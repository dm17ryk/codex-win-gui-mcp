from __future__ import annotations

import json
import time
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Literal

from .errors import SessionNotInitializedError


CoordSpace = Literal["screen", "viewport"]
CaptureMode = Literal["full_screen", "window", "region"]
AdapterKind = Literal["qt", "cilogg"] | None


@dataclass
class Viewport:
    mode: CaptureMode
    left: int
    top: int
    width: int
    height: int
    hwnd: int | None
    pid: int | None
    title: str | None
    monitor_index: int | None
    scale_x: float = 1.0
    scale_y: float = 1.0
    captured_at: float = 0.0
    coord_space: CoordSpace = "screen"

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["right"] = self.left + self.width
        data["bottom"] = self.top + self.height
        return data


@dataclass
class TargetSession:
    session_id: str
    title_regex: str | None
    pid: int | None
    hwnd: int | None
    viewport: Viewport | None
    capture_mode: CaptureMode
    trace_path: str
    last_screenshot_path: str | None = None
    last_response_id: str | None = None
    adapter: AdapterKind = None
    adapter_state: dict[str, Any] = field(default_factory=dict)
    artifact_dir: str = ""
    screenshots_dir: str = ""
    ui_tree_path: str | None = None
    bundle_manifest_path: str | None = None
    last_bundle_dir: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "session_id": self.session_id,
            "title_regex": self.title_regex,
            "pid": self.pid,
            "hwnd": self.hwnd,
            "capture_mode": self.capture_mode,
            "trace_path": self.trace_path,
            "last_screenshot_path": self.last_screenshot_path,
            "last_response_id": self.last_response_id,
            "adapter": self.adapter,
            "adapter_state": self.adapter_state,
            "artifact_dir": self.artifact_dir,
            "screenshots_dir": self.screenshots_dir,
            "ui_tree_path": self.ui_tree_path,
            "bundle_manifest_path": self.bundle_manifest_path,
            "last_bundle_dir": self.last_bundle_dir,
            "viewport": self.viewport.to_dict() if self.viewport else None,
        }


@dataclass
class SessionTraceEvent:
    ts: float
    type: str
    data: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {"ts": self.ts, "type": self.type, **self.data}


class SessionStore:
    def __init__(self, artifacts_root: Path) -> None:
        self._artifacts_root = artifacts_root
        self._artifacts_root.mkdir(parents=True, exist_ok=True)
        self._active: TargetSession | None = None

    def create(
        self,
        *,
        title_regex: str | None,
        pid: int | None,
        hwnd: int | None,
        capture_mode: CaptureMode,
        adapter: AdapterKind,
    ) -> TargetSession:
        session_id = uuid.uuid4().hex[:12]
        session_dir = self._artifacts_root / session_id
        screenshots_dir = session_dir / "screenshots"
        screenshots_dir.mkdir(parents=True, exist_ok=True)
        trace_path = session_dir / "trace.jsonl"
        session = TargetSession(
            session_id=session_id,
            title_regex=title_regex,
            pid=pid,
            hwnd=hwnd,
            viewport=None,
            capture_mode=capture_mode,
            trace_path=str(trace_path),
            adapter=adapter,
            artifact_dir=str(session_dir),
            screenshots_dir=str(screenshots_dir),
        )
        self._active = session
        return session

    def get(self) -> TargetSession:
        if self._active is None:
            raise SessionNotInitializedError("No active session. Call create_session() first.")
        return self._active

    def maybe_get(self) -> TargetSession | None:
        return self._active

    def close(self) -> dict[str, Any]:
        session = self._active
        self._active = None
        return {"ok": True, "closed_session_id": session.session_id if session else None}

    def set_viewport(self, viewport: Viewport) -> TargetSession:
        session = self.get()
        session.viewport = viewport
        if viewport.hwnd is not None:
            session.hwnd = viewport.hwnd
        if viewport.pid is not None:
            session.pid = viewport.pid
        return session

    def update(self, **changes: Any) -> TargetSession:
        session = self.get()
        for key, value in changes.items():
            setattr(session, key, value)
        return session

    def trace(self, event_type: str, **data: Any) -> SessionTraceEvent:
        session = self.get()
        event = SessionTraceEvent(ts=time.time(), type=event_type, data=data)
        trace_path = Path(session.trace_path)
        trace_path.parent.mkdir(parents=True, exist_ok=True)
        with trace_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(event.to_dict(), ensure_ascii=True, default=str) + "\n")
        return event
