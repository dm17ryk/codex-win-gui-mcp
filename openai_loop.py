from __future__ import annotations

import argparse
import base64
import json
import os
import sys
import time
from contextlib import contextmanager
from typing import Any, Iterable

import pyautogui
from openai import OpenAI

from win_gui_core import DesktopHarness


client = OpenAI()
harness = DesktopHarness()
pyautogui.FAILSAFE = True
pyautogui.PAUSE = 0.03


KEY_ALIASES = {
    "CTRL": "ctrl",
    "CONTROL": "ctrl",
    "SHIFT": "shift",
    "ALT": "alt",
    "META": "win",
    "CMD": "win",
    "SUPER": "win",
    "ENTER": "enter",
    "RETURN": "enter",
    "ESC": "esc",
    "ESCAPE": "esc",
    "SPACE": "space",
    "TAB": "tab",
    "BACKSPACE": "backspace",
    "DELETE": "delete",
    "INSERT": "insert",
    "HOME": "home",
    "END": "end",
    "PAGEUP": "pageup",
    "PAGEDOWN": "pagedown",
    "ARROWLEFT": "left",
    "ARROWRIGHT": "right",
    "ARROWUP": "up",
    "ARROWDOWN": "down",
}


def field(obj: Any, name: str, default: Any = None) -> Any:
    if isinstance(obj, dict):
        return obj.get(name, default)
    return getattr(obj, name, default)


@contextmanager
def with_modifiers(keys: Iterable[str] | None):
    normalized = [normalize_key(k) for k in (keys or [])]
    for key in normalized:
        pyautogui.keyDown(key)
    try:
        yield
    finally:
        for key in reversed(normalized):
            pyautogui.keyUp(key)


def normalize_key(key: str) -> str:
    upper = key.strip().upper()
    return KEY_ALIASES.get(upper, key.strip().lower())


def normalize_drag_path(path: Any) -> list[tuple[int, int]]:
    points: list[tuple[int, int]] = []
    for item in path:
        if isinstance(item, dict):
            points.append((int(item["x"]), int(item["y"])))
        elif hasattr(item, "x") and hasattr(item, "y"):
            points.append((int(item.x), int(item.y)))
        else:
            x, y = item
            points.append((int(x), int(y)))
    return points


def execute_actions(actions: Iterable[Any]) -> None:
    for action in actions:
        action_type = field(action, "type")
        if action_type in {"wait", "screenshot"}:
            if action_type == "wait":
                time.sleep(2)
            continue

        if action_type == "keypress":
            for key in field(action, "keys", []):
                pyautogui.press(normalize_key(key))
            continue

        if action_type == "type":
            pyautogui.write(field(action, "text", ""), interval=0.01)
            continue

        keys = field(action, "keys", None)
        with with_modifiers(keys):
            if action_type == "move":
                pyautogui.moveTo(int(field(action, "x")), int(field(action, "y")))
            elif action_type == "click":
                pyautogui.click(
                    int(field(action, "x")),
                    int(field(action, "y")),
                    button=field(action, "button", "left"),
                )
            elif action_type == "double_click":
                pyautogui.doubleClick(
                    int(field(action, "x")),
                    int(field(action, "y")),
                    button=field(action, "button", "left"),
                )
            elif action_type == "drag":
                path = normalize_drag_path(field(action, "path", []))
                if len(path) < 2:
                    raise ValueError("drag action requires at least two path points")
                start_x, start_y = path[0]
                pyautogui.moveTo(start_x, start_y)
                pyautogui.mouseDown(button=field(action, "button", "left"))
                try:
                    for x, y in path[1:]:
                        pyautogui.moveTo(x, y)
                finally:
                    pyautogui.mouseUp(button=field(action, "button", "left"))
            elif action_type == "scroll":
                x = int(field(action, "x", pyautogui.position().x))
                y = int(field(action, "y", pyautogui.position().y))
                pyautogui.moveTo(x, y)
                scroll_y = int(field(action, "scrollY", 0))
                clicks = max(1, abs(round(scroll_y / 100)))
                pyautogui.scroll(clicks if scroll_y > 0 else -clicks)
            else:
                raise ValueError(f"Unsupported action type: {action_type}")


def send_first_request(goal: str):
    return client.responses.create(
        model=os.environ.get("OPENAI_COMPUTER_MODEL", "gpt-5.4"),
        tools=[{"type": "computer"}],
        input=goal,
    )



def send_screenshot(response: Any, call_id: str, screenshot_base64: str):
    return client.responses.create(
        model=os.environ.get("OPENAI_COMPUTER_MODEL", "gpt-5.4"),
        tools=[{"type": "computer"}],
        previous_response_id=response.id,
        input=[
            {
                "type": "computer_call_output",
                "call_id": call_id,
                "output": {
                    "type": "computer_screenshot",
                    "image_url": f"data:image/png;base64,{screenshot_base64}",
                    "detail": "original",
                },
            }
        ],
    )



def find_computer_call(response: Any):
    for item in response.output:
        if field(item, "type") == "computer_call":
            return item
    return None



def computer_use_loop(goal: str, window_title: str | None, full_screen: bool) -> Any:
    response = send_first_request(goal)
    while True:
        computer_call = find_computer_call(response)
        if computer_call is None:
            return response
        execute_actions(field(computer_call, "actions", []))
        screenshot = harness.capture_screenshot(
            full_screen=full_screen,
            title_regex=window_title,
            embed_base64=True,
        )
        response = send_screenshot(response, field(computer_call, "call_id"), screenshot["image_base64"])



def main() -> int:
    parser = argparse.ArgumentParser(description="Run an OpenAI Computer Use loop against a Windows desktop target.")
    parser.add_argument("goal", help="Natural-language task for the model.")
    parser.add_argument("--window-title", default=os.environ.get("MAIN_WINDOW_TITLE_REGEX"), help="Regex of the target window title.")
    parser.add_argument("--full-screen", action="store_true", help="Capture the whole screen instead of a single window.")
    args = parser.parse_args()

    final_response = computer_use_loop(args.goal, args.window_title, args.full_screen)
    output_text = getattr(final_response, "output_text", None)
    if output_text:
        print(output_text)
    else:
        print(json.dumps(final_response.model_dump(), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
