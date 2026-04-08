from __future__ import annotations

import tempfile
import time
import unittest
from pathlib import Path

from win_gui_core.logs import LogManager


class LogManagerTests(unittest.TestCase):
    def test_resolve_log_path_returns_newest_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            first = root / "first.log"
            second = root / "nested" / "second.log"
            second.parent.mkdir()
            first.write_text("older", encoding="utf-8")
            time.sleep(0.01)
            second.write_text("newer", encoding="utf-8")
            manager = LogManager(root)
            self.assertEqual(manager.resolve_log_path(), second)

    def test_collect_recent_logs_preserves_relative_paths(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "logs"
            output = Path(tmp) / "out"
            nested = root / "nested"
            nested.mkdir(parents=True)
            (nested / "app.log").write_text("hello", encoding="utf-8")
            (nested / "app.exe").write_text("binary", encoding="utf-8")
            manager = LogManager(root)
            result = manager.collect_recent_logs(minutes=60, output_dir=str(output))
            self.assertTrue(result["ok"])
            self.assertTrue((output / "nested" / "app.log").exists())
            self.assertFalse((output / "nested" / "app.exe").exists())


if __name__ == "__main__":
    unittest.main()
