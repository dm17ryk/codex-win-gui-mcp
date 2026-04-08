from __future__ import annotations

import re
import time
from pathlib import Path
from typing import Any

from pywinauto import Desktop

from .errors import AssertionFailedError, UIAutomationError
from .input import InputController


class UIAutomationService:
    def __init__(self, input_controller: InputController) -> None:
        self._desktop = Desktop(backend="uia")
        self._input = input_controller

    def find_element(
        self,
        window_title_regex: str,
        *,
        name: str | None = None,
        auto_id: str | None = None,
        control_type: str | None = None,
        found_index: int = 0,
        timeout_sec: float = 2.0,
    ) -> dict[str, Any]:
        wrapper = self._resolve_element(
            window_title_regex=window_title_regex,
            name=name,
            auto_id=auto_id,
            control_type=control_type,
            found_index=found_index,
            timeout_sec=timeout_sec,
        )
        return self._element_to_dict(wrapper)

    def wait_for_element(self, **kwargs: Any) -> dict[str, Any]:
        return {"ok": True, "element": self.find_element(**kwargs)}

    def wait_for_element_gone(
        self,
        window_title_regex: str,
        *,
        name: str | None = None,
        auto_id: str | None = None,
        control_type: str | None = None,
        found_index: int = 0,
        timeout_sec: float = 2.0,
    ) -> dict[str, Any]:
        deadline = time.time() + timeout_sec
        while time.time() < deadline:
            try:
                self._resolve_element(
                    window_title_regex=window_title_regex,
                    name=name,
                    auto_id=auto_id,
                    control_type=control_type,
                    found_index=found_index,
                    timeout_sec=0.5,
                )
            except UIAutomationError:
                return {"ok": True}
            time.sleep(0.2)
        raise AssertionFailedError("Element remained visible past the requested timeout.")

    def assert_element(self, **kwargs: Any) -> dict[str, Any]:
        element = self.find_element(**kwargs)
        return {"ok": True, "element": element}

    def click_element(self, button: str = "left", **kwargs: Any) -> dict[str, Any]:
        wrapper = self._resolve_element(**kwargs)
        wrapper.set_focus()
        wrapper.click_input(button=button)
        result = self._element_to_dict(wrapper)
        result["ok"] = True
        result["button"] = button
        return result

    def double_click_element(self, **kwargs: Any) -> dict[str, Any]:
        result = self.click_element(button="left", **kwargs)
        result["double_click"] = True
        return result

    def right_click_element(self, **kwargs: Any) -> dict[str, Any]:
        return self.click_element(button="right", **kwargs)

    def drag_element_to_point(
        self,
        *,
        window_title_regex: str,
        x: int,
        y: int,
        coord_space: str,
        viewport,
        **kwargs: Any,
    ) -> dict[str, Any]:
        wrapper = self._resolve_element(window_title_regex=window_title_regex, **kwargs)
        rect = wrapper.rectangle()
        path = [
            (rect.left + rect.width() // 2, rect.top + rect.height() // 2),
            (x, y),
        ]
        translated_coord_space = "screen" if coord_space == "screen" else coord_space
        return self._input.drag_path(path, coord_space=translated_coord_space, viewport=viewport, button="left")

    def drag_element_to_element(
        self,
        *,
        source: dict[str, Any],
        target: dict[str, Any],
        viewport,
    ) -> dict[str, Any]:
        source_wrapper = self._resolve_element(**source)
        target_wrapper = self._resolve_element(**target)
        start = source_wrapper.rectangle()
        end = target_wrapper.rectangle()
        path = [
            (start.left + start.width() // 2, start.top + start.height() // 2),
            (end.left + end.width() // 2, end.top + end.height() // 2),
        ]
        return self._input.drag_path(path, coord_space="screen", viewport=viewport, button="left")

    def get_uia_tree(
        self,
        window_title_regex: str,
        *,
        max_depth: int = 3,
        max_children_per_node: int = 50,
        output_path: str | None = None,
    ) -> dict[str, Any]:
        window = self._resolve_window(window_title_regex)
        wrapper = window.wrapper_object()
        tree = self._serialize_wrapper(wrapper, depth=0, max_depth=max_depth, max_children_per_node=max_children_per_node)
        if output_path:
            path = Path(output_path)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(str(tree), encoding="utf-8")
        return {"ok": True, "tree": tree, "path": output_path}

    def assert_window_title(self, window_title_regex: str, expected_pattern: str) -> dict[str, Any]:
        window = self._resolve_window(window_title_regex)
        title = window.window_text()
        if not re.search(expected_pattern, title or ""):
            raise AssertionFailedError(f"Window title {title!r} did not match /{expected_pattern}/.")
        return {"ok": True, "title": title}

    def assert_status_text(self, window_title_regex: str, expected_text: str, timeout_sec: float = 2.0) -> dict[str, Any]:
        deadline = time.time() + timeout_sec
        while time.time() < deadline:
            try:
                status = self._resolve_element(
                    window_title_regex=window_title_regex,
                    control_type="Text",
                    found_index=0,
                    timeout_sec=0.5,
                )
                current = getattr(status.element_info, "name", "") or status.window_text()
                if expected_text in current:
                    return {"ok": True, "text": current}
            except UIAutomationError:
                pass
            time.sleep(0.2)
        raise AssertionFailedError(f"Unable to find status text containing {expected_text!r}.")

    def _resolve_window(self, window_title_regex: str):
        try:
            spec = self._desktop.window(title_re=window_title_regex)
            spec.wait("exists visible ready", timeout=10)
        except Exception as exc:
            raise UIAutomationError(f"Unable to resolve window /{window_title_regex}/: {exc}") from exc
        return spec

    def _resolve_element(
        self,
        *,
        window_title_regex: str,
        name: str | None = None,
        auto_id: str | None = None,
        control_type: str | None = None,
        found_index: int = 0,
        timeout_sec: float = 2.0,
    ):
        if not any([name, auto_id, control_type]):
            raise UIAutomationError("At least one of name, auto_id, or control_type must be set.")
        window = self._resolve_window(window_title_regex)
        criteria: dict[str, Any] = {"found_index": found_index}
        if name:
            criteria["title"] = name
        if auto_id:
            criteria["auto_id"] = auto_id
        if control_type:
            criteria["control_type"] = control_type
        try:
            spec = window.child_window(**criteria)
            spec.wait("exists ready", timeout=timeout_sec)
            return spec.wrapper_object()
        except Exception as exc:
            raise UIAutomationError(f"Unable to resolve element in /{window_title_regex}/: {exc}") from exc

    def _serialize_wrapper(
        self,
        wrapper,
        *,
        depth: int,
        max_depth: int,
        max_children_per_node: int,
    ) -> dict[str, Any]:
        info = wrapper.element_info
        rect = wrapper.rectangle()
        node: dict[str, Any] = {
            "name": getattr(info, "name", ""),
            "control_type": getattr(info, "control_type", ""),
            "automation_id": getattr(info, "automation_id", ""),
            "class_name": getattr(info, "class_name", ""),
            "rectangle": {
                "left": rect.left,
                "top": rect.top,
                "right": rect.right,
                "bottom": rect.bottom,
                "width": rect.width(),
                "height": rect.height(),
            },
            "children": [],
        }
        if depth >= max_depth:
            return node
        try:
            children = wrapper.children()
        except Exception:
            children = []
        for child in list(children)[:max_children_per_node]:
            try:
                node["children"].append(
                    self._serialize_wrapper(
                        child,
                        depth=depth + 1,
                        max_depth=max_depth,
                        max_children_per_node=max_children_per_node,
                    )
                )
            except Exception:
                continue
        return node

    def _element_to_dict(self, wrapper) -> dict[str, Any]:
        info = wrapper.element_info
        rect = wrapper.rectangle()
        return {
            "name": getattr(info, "name", ""),
            "control_type": getattr(info, "control_type", ""),
            "automation_id": getattr(info, "automation_id", ""),
            "class_name": getattr(info, "class_name", ""),
            "rectangle": {
                "left": rect.left,
                "top": rect.top,
                "right": rect.right,
                "bottom": rect.bottom,
                "width": rect.width(),
                "height": rect.height(),
                "center_x": rect.left + rect.width() // 2,
                "center_y": rect.top + rect.height() // 2,
            },
        }
