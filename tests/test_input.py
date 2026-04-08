from __future__ import annotations

import unittest

from win_gui_core.errors import CoordinateTranslationError
from win_gui_core.input import normalize_drag_path, normalize_key, viewport_to_screen
from win_gui_core.session import Viewport


class InputTests(unittest.TestCase):
    def test_viewport_to_screen_translates_window_coordinates(self) -> None:
        viewport = Viewport(
            mode="window",
            left=100,
            top=50,
            width=800,
            height=600,
            hwnd=1,
            pid=2,
            title="Sample",
            monitor_index=None,
            coord_space="viewport",
        )
        self.assertEqual(viewport_to_screen(20, 30, viewport), (120, 80))

    def test_viewport_to_screen_rejects_points_outside_bounds(self) -> None:
        viewport = Viewport(
            mode="window",
            left=0,
            top=0,
            width=100,
            height=100,
            hwnd=1,
            pid=2,
            title="Sample",
            monitor_index=None,
            coord_space="viewport",
        )
        with self.assertRaises(CoordinateTranslationError):
            viewport_to_screen(120, 10, viewport)

    def test_normalize_drag_path_supports_dicts_and_tuples(self) -> None:
        path = [{"x": 1, "y": 2}, (3, 4)]
        self.assertEqual(normalize_drag_path(path), [(1, 2), (3, 4)])

    def test_normalize_key_aliases_control(self) -> None:
        self.assertEqual(normalize_key("CTRL"), "ctrl")


if __name__ == "__main__":
    unittest.main()
