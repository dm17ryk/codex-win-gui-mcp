from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from win_gui_core.session import SessionStore, Viewport


class SessionStoreTests(unittest.TestCase):
    def test_session_create_and_update_viewport(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = SessionStore(Path(tmp))
            session = store.create(title_regex="MyApp", pid=10, hwnd=20, capture_mode="window", adapter=None)
            viewport = Viewport(
                mode="window",
                left=1,
                top=2,
                width=3,
                height=4,
                hwnd=20,
                pid=10,
                title="MyApp",
                monitor_index=None,
                coord_space="viewport",
            )
            store.set_viewport(viewport)
            self.assertEqual(store.get().viewport.left, 1)
            self.assertEqual(session.session_id, store.get().session_id)

    def test_trace_file_is_created(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = SessionStore(Path(tmp))
            session = store.create(title_regex="MyApp", pid=10, hwnd=20, capture_mode="window", adapter=None)
            store.trace("session_created", session_id=session.session_id)
            self.assertTrue(Path(session.trace_path).exists())


if __name__ == "__main__":
    unittest.main()
