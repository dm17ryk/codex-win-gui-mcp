from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from win_gui_core.artifacts import ArtifactManager
from win_gui_core.logs import LogManager
from win_gui_core.session import SessionStore


class ArtifactTests(unittest.TestCase):
    def test_bundle_writes_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            logs_dir = root / "logs"
            logs_dir.mkdir()
            (logs_dir / "app.log").write_text("hello", encoding="utf-8")
            store = SessionStore(root / "sessions")
            session = store.create(title_regex="MyApp", pid=1, hwnd=2, capture_mode="window", adapter=None)
            store.trace("unit_test", status="ready")
            screenshot = Path(session.screenshots_dir) / "last.png"
            screenshot.write_bytes(b"png")
            session.last_screenshot_path = str(screenshot)
            manager = ArtifactManager(store, LogManager(logs_dir))
            result = manager.create_bundle(
                session,
                reason="unit-test",
                ui_tree={"name": "root"},
                qt_state={"windowInfo": {}, "actions": [], "kloggState": {}},
                process_tree={"ok": True, "root": {"pid": 1}},
            )
            self.assertTrue(result["ok"])
            self.assertTrue(Path(result["manifest_path"]).exists())
            manifest = result["manifest"]
            self.assertTrue(Path(manifest["trace_path"]).exists())
            self.assertTrue(Path(manifest["last_screenshot_path"]).exists())
            self.assertTrue(Path(manifest["ui_tree_path"]).exists())
            self.assertTrue(Path(manifest["qt_state_path"]).exists())
            self.assertTrue(Path(manifest["process_tree_path"]).exists())


if __name__ == "__main__":
    unittest.main()
