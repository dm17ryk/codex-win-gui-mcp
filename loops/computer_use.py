from __future__ import annotations

import json
import os
import time
from typing import Any, Iterable

from openai import OpenAI

from win_gui_core.errors import WinGuiError
from win_gui_core.input import normalize_drag_path, with_modifiers
from win_gui_core.service import WinGuiService


class ComputerUseRunner:
    def __init__(self, service: WinGuiService | None = None, client: OpenAI | None = None) -> None:
        self.service = service or WinGuiService()
        self.client = client or OpenAI()

    def run(self, *, goal: str, window_title: str | None, full_screen: bool) -> Any:
        capture_mode = "full_screen" if full_screen else "window"
        self.service.create_session(title_regex=window_title, capture_mode=capture_mode)
        response = self._send_first_request(goal)
        while True:
            computer_call = self._find_computer_call(response)
            if computer_call is None:
                return response
            actions = self._field(computer_call, "actions", [])
            self.service.sessions.update(last_response_id=response.id)
            self.service.sessions.trace("model_actions", actions=[self._action_to_dict(action) for action in actions])
            self._execute_actions(actions)
            screenshot = self.service.capture_screenshot(mode=capture_mode, embed_base64=True)
            response = self._send_screenshot(response, self._field(computer_call, "call_id"), screenshot)

    def _send_first_request(self, goal: str):
        return self.client.responses.create(
            model=os.environ.get("OPENAI_COMPUTER_MODEL", "gpt-5.4"),
            tools=[{"type": "computer"}],
            input=goal,
        )

    def _send_screenshot(self, response: Any, call_id: str, screenshot: dict[str, Any]):
        viewport_text = json.dumps(screenshot["viewport"], ensure_ascii=True)
        return self.client.responses.create(
            model=os.environ.get("OPENAI_COMPUTER_MODEL", "gpt-5.4"),
            tools=[{"type": "computer"}],
            previous_response_id=response.id,
            input=[
                {
                    "type": "computer_call_output",
                    "call_id": call_id,
                    "output": {
                        "type": "computer_screenshot",
                        "image_url": f"data:image/png;base64,{screenshot['image_base64']}",
                        "detail": "original",
                    },
                },
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "input_text",
                            "text": f"Viewport metadata for the current screenshot: {viewport_text}",
                        }
                    ],
                },
            ],
        )

    def _find_computer_call(self, response: Any):
        for item in response.output:
            if self._field(item, "type") == "computer_call":
                return item
        return None

    def _execute_actions(self, actions: Iterable[Any]) -> None:
        for action in actions:
            action_type = self._field(action, "type")
            try:
                if action_type in {"wait", "screenshot"}:
                    if action_type == "wait":
                        time.sleep(2)
                    continue
                if action_type == "keypress":
                    for key in self._field(action, "keys", []):
                        self.service.send_hotkey([key])
                    continue
                if action_type == "type":
                    self.service.type_text(self._field(action, "text", ""))
                    continue
                keys = self._field(action, "keys", None)
                with with_modifiers(keys):
                    if action_type == "move":
                        session = self.service.sessions.get()
                        self.service.input.move_to(
                            int(self._field(action, "x")),
                            int(self._field(action, "y")),
                            coord_space="viewport",
                            viewport=session.viewport,
                        )
                    elif action_type == "click":
                        self.service.click_point(
                            int(self._field(action, "x")),
                            int(self._field(action, "y")),
                            coord_space="viewport",
                            button=self._field(action, "button", "left"),
                        )
                    elif action_type == "double_click":
                        self.service.double_click_point(
                            int(self._field(action, "x")),
                            int(self._field(action, "y")),
                            coord_space="viewport",
                            button=self._field(action, "button", "left"),
                        )
                    elif action_type == "drag":
                        path = normalize_drag_path(self._field(action, "path", []))
                        self.service.drag_path(
                            [{"x": x, "y": y} for x, y in path],
                            coord_space="viewport",
                            button=self._field(action, "button", "left"),
                        )
                    elif action_type == "scroll":
                        scroll_y = int(self._field(action, "scrollY", 0))
                        clicks = max(1, abs(round(scroll_y / 100)))
                        self.service.scroll_at(
                            clicks if scroll_y > 0 else -clicks,
                            x=self._field(action, "x"),
                            y=self._field(action, "y"),
                            coord_space="viewport",
                        )
                    else:
                        raise ValueError(f"Unsupported action type: {action_type}")
            except Exception as exc:
                if self.service.sessions.maybe_get():
                    self.service.sessions.trace(
                        "error",
                        action=self._action_to_dict(action),
                        error=str(exc),
                        error_type=type(exc).__name__,
                    )
                if isinstance(exc, WinGuiError):
                    raise
                raise RuntimeError(f"Computer use action failed: {exc}") from exc

    @staticmethod
    def _field(obj: Any, name: str, default: Any = None) -> Any:
        if isinstance(obj, dict):
            return obj.get(name, default)
        return getattr(obj, name, default)

    @classmethod
    def _action_to_dict(cls, action: Any) -> dict[str, Any]:
        if isinstance(action, dict):
            return action
        payload = {}
        for key in ("type", "x", "y", "text", "button", "path", "keys", "scrollY"):
            value = getattr(action, key, None)
            if value is not None:
                payload[key] = value
        return payload
