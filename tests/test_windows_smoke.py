from __future__ import annotations

import os
import sys
import unittest

from win_gui_core.service import WinGuiService


@unittest.skipUnless(sys.platform == "win32", "Windows-only smoke tests")
@unittest.skipUnless(os.environ.get("WIN_GUI_SMOKE") == "1", "Set WIN_GUI_SMOKE=1 to run integration smoke tests")
class WindowsSmokeTests(unittest.TestCase):
    def test_launch_create_session_close_flow(self) -> None:
        service = WinGuiService()
        launch = service.launch_app()
        self.assertTrue(launch["ok"])
        session = service.create_session()
        self.assertTrue(session["ok"])
        close = service.close_app(pid=launch["pid"])
        self.assertTrue(close["ok"])

    def test_capture_screenshot_returns_viewport(self) -> None:
        service = WinGuiService()
        service.create_session()
        shot = service.capture_screenshot()
        self.assertTrue(shot["ok"])
        self.assertIn("viewport", shot)


if __name__ == "__main__":
    unittest.main()
