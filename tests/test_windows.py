from __future__ import annotations

import unittest
from unittest import mock

from win_gui_core.errors import FocusError
from win_gui_core.windows import WindowManager


class WindowManagerTests(unittest.TestCase):
    def test_focus_window_returns_warning_for_visible_window_when_foreground_fails(self) -> None:
        manager = WindowManager(r"(?i)cilogg")

        with (
            mock.patch("win_gui_core.windows.win32gui.IsWindow", return_value=True),
            mock.patch("win_gui_core.windows.win32gui.IsIconic", return_value=False),
            mock.patch("win_gui_core.windows.win32gui.IsWindowVisible", return_value=True),
            mock.patch("win_gui_core.windows.win32gui.ShowWindow"),
            mock.patch("win_gui_core.windows.win32gui.BringWindowToTop"),
            mock.patch(
                "win_gui_core.windows.win32gui.SetForegroundWindow",
                side_effect=RuntimeError("blocked"),
            ),
            mock.patch.object(manager, "_force_focus_window", side_effect=RuntimeError("still blocked")),
        ):
            result = manager.focus_window(123)

        self.assertTrue(result["ok"])
        self.assertEqual(result["hwnd"], 123)
        self.assertIn("warning", result)

    def test_focus_window_raises_for_invalid_hwnd(self) -> None:
        manager = WindowManager(r"(?i)cilogg")

        with mock.patch("win_gui_core.windows.win32gui.IsWindow", return_value=False):
            with self.assertRaises(FocusError):
                manager.focus_window(0)


if __name__ == "__main__":
    unittest.main()
