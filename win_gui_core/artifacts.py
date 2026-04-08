from __future__ import annotations

import json
import shutil
import time
from pathlib import Path
from typing import Any

from .logs import LogManager
from .session import SessionStore, TargetSession


class ArtifactManager:
    def __init__(self, session_store: SessionStore, log_manager: LogManager) -> None:
        self._session_store = session_store
        self._logs = log_manager

    def list_artifacts(self) -> dict[str, Any]:
        root = Path.cwd() / "artifacts" / "sessions"
        root.mkdir(parents=True, exist_ok=True)
        sessions = []
        for item in sorted(root.iterdir()):
            if item.is_dir():
                sessions.append({"session_id": item.name, "path": str(item)})
        return {"ok": True, "sessions": sessions}

    def create_bundle(
        self,
        session: TargetSession,
        *,
        reason: str | None = None,
        ui_tree: dict[str, Any] | None = None,
        qt_state: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        bundle_dir = Path(session.artifact_dir) / f"bundle-{int(time.time())}"
        bundle_dir.mkdir(parents=True, exist_ok=True)
        copied_logs = self._logs.collect_recent_logs(output_dir=str(bundle_dir / "logs"))
        dumps = self._logs.collect_dumps(output_dir=str(bundle_dir / "dumps"))

        if session.last_screenshot_path:
            screenshot_target = bundle_dir / "last-screenshot.png"
            shutil.copy2(session.last_screenshot_path, screenshot_target)

        trace_target = bundle_dir / "trace.jsonl"
        if Path(session.trace_path).exists():
            shutil.copy2(session.trace_path, trace_target)

        if ui_tree is not None:
            ui_tree_path = bundle_dir / "uia-tree.json"
            ui_tree_path.write_text(json.dumps(ui_tree, indent=2), encoding="utf-8")
            session.ui_tree_path = str(ui_tree_path)

        if qt_state is not None:
            qt_state_path = bundle_dir / "qt-state.json"
            qt_state_path.write_text(json.dumps(qt_state, indent=2), encoding="utf-8")

        manifest = {
            "session_id": session.session_id,
            "reason": reason,
            "created_at": time.time(),
            "trace_path": str(trace_target),
            "last_screenshot_path": session.last_screenshot_path,
            "logs": copied_logs,
            "dumps": dumps,
            "ui_tree_path": session.ui_tree_path,
            "adapter": session.adapter,
        }
        manifest_path = bundle_dir / "bundle-manifest.json"
        manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
        session.bundle_manifest_path = str(manifest_path)
        session.last_bundle_dir = str(bundle_dir)
        self._session_store.update(bundle_manifest_path=session.bundle_manifest_path, last_bundle_dir=session.last_bundle_dir)
        return {"ok": True, "bundle_dir": str(bundle_dir), "manifest_path": str(manifest_path), "manifest": manifest}
