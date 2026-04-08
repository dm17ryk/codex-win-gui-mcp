from __future__ import annotations

import sys
import time
import unittest
from unittest import mock
from types import SimpleNamespace

class _DummyMSS:
    monitors = [None, {"left": 0, "top": 0, "width": 1920, "height": 1080}]

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def grab(self, bbox):
        width = max(1, int(bbox["width"]))
        height = max(1, int(bbox["height"]))
        return SimpleNamespace(size=(width, height), rgb=b"\x00" * width * height * 3)


class _DummyDesktop:
    def __init__(self, *args, **kwargs):
        pass

    def window(self, *args, **kwargs):
        raise RuntimeError("UIA desktop access is not available in this unit test.")


_dummy_image_module = SimpleNamespace(
    frombytes=lambda *args, **kwargs: SimpleNamespace(save=lambda *save_args, **save_kwargs: None)
)

sys.modules.setdefault(
    "pyautogui",
    SimpleNamespace(
        click=lambda *args, **kwargs: None,
        moveTo=lambda *args, **kwargs: None,
        mouseDown=lambda *args, **kwargs: None,
        mouseUp=lambda *args, **kwargs: None,
        scroll=lambda *args, **kwargs: None,
        write=lambda *args, **kwargs: None,
        hotkey=lambda *args, **kwargs: None,
        press=lambda *args, **kwargs: None,
        position=lambda: SimpleNamespace(x=0, y=0),
    ),
)
sys.modules.setdefault("mss", SimpleNamespace(mss=_DummyMSS))
sys.modules.setdefault("PIL", SimpleNamespace(Image=_dummy_image_module))
sys.modules.setdefault("PIL.Image", _dummy_image_module)
sys.modules.setdefault("pywinauto", SimpleNamespace(Desktop=_DummyDesktop))

from win_gui_core.errors import AdapterError
from win_gui_core.service import WinGuiService
from win_gui_core.session import Viewport


class ServiceQtFallbackTests(unittest.TestCase):
    def _create_service_with_viewport(self) -> tuple[WinGuiService, Viewport]:
        service = WinGuiService()
        service.sessions.create(title_regex="klogg", pid=123, hwnd=None, capture_mode="window", adapter="qt")
        viewport = Viewport(
            mode="window",
            left=100,
            top=200,
            width=800,
            height=600,
            hwnd=None,
            pid=123,
            title="klogg",
            monitor_index=None,
            captured_at=time.time(),
            coord_space="screen",
        )
        service.sessions.set_viewport(viewport)
        return service, viewport

    def test_click_qt_object_uses_widget_bounds(self) -> None:
        service, viewport = self._create_service_with_viewport()
        service.qt_adapter.click_qt_object = mock.Mock(  # type: ignore[method-assign]
            return_value={
                "ok": True,
                "locator": {"object_name": "searchButton"},
                "object": {"objectName": "searchButton", "bounds": {"x": 10, "y": 20, "width": 30, "height": 40}},
            }
        )
        service.input.click_point = mock.Mock(return_value={"ok": True, "x": 25, "y": 40})  # type: ignore[method-assign]

        result = service.click_qt_object(object_name="searchButton")

        service.input.click_point.assert_called_once_with(25, 40, coord_space="viewport", viewport=viewport, button="left")  # type: ignore[attr-defined]
        self.assertTrue(result["ok"])
        self.assertEqual(result["click"]["x"], 25)

    def test_invoke_qt_action_falls_back_to_clickable_widget(self) -> None:
        service, viewport = self._create_service_with_viewport()
        service.qt_adapter.invoke_qt_action = mock.Mock(side_effect=AdapterError("semantic invoke failed"))  # type: ignore[method-assign]
        service.qt_adapter.dump_qt_state = mock.Mock(  # type: ignore[method-assign]
            return_value={
                "actions": [{"objectName": "followAction", "text": "Follow File"}],
                "children": [
                    {
                        "objectName": "followButton",
                        "accessibleName": "Follow File",
                        "role": "widget",
                        "bounds": {"x": 8, "y": 12, "width": 24, "height": 18},
                        "children": [],
                    }
                ],
            }
        )
        service.input.click_point = mock.Mock(return_value={"ok": True, "x": 20, "y": 21})  # type: ignore[method-assign]

        result = service.invoke_qt_action("followAction")

        service.input.click_point.assert_called_once_with(20, 21, coord_space="viewport", viewport=viewport, button="left")  # type: ignore[attr-defined]
        self.assertEqual(result["fallback"], "click")
        self.assertTrue(result["ok"])

    def test_wait_window_stable_refreshes_session_hwnd(self) -> None:
        service, _viewport = self._create_service_with_viewport()
        service.windows.wait_window_stable = mock.Mock(  # type: ignore[method-assign]
            return_value={
                "ok": True,
                "window": {"hwnd": 456, "pid": 789, "title": "klogg"},
                "rect": {"left": 10, "top": 20, "width": 300, "height": 200},
            }
        )

        result = service.wait_window_stable()

        session = service.sessions.get()
        self.assertEqual(result["window"]["hwnd"], 456)
        self.assertEqual(session.hwnd, 456)
        self.assertEqual(session.pid, 789)
        self.assertIsNotNone(session.viewport)
        self.assertEqual(session.viewport.hwnd, 456)


if __name__ == "__main__":
    unittest.main()
