from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from loops.computer_use import ComputerUseRunner

from .errors import AdapterError, AssertionFailedError
from .service import WinGuiService


DEFAULT_SEARCH_TEXT = "Test"
DEFAULT_LAUNCH_ARGS = ("-n", "-l", "-dddd")
DEFAULT_FILTERED_WRAP_LOG = Path(r"D:\Essence_SC\kloggs\com1_115200_2026-03-24_13-31-15.log")
DEFAULT_FILTERED_WRAP_SEARCH = "EHCI001VER|CRC"
FILTERED_WRAP_MAX_EMPTY_GAP_ROWS = 12
DEFAULT_COMPUTER_USE_GOAL = (
    "Inspect the active CILogg window. Confirm the visible log filename, whether the word "
    '"{search_text}" appears to be the current search, and whether follow mode looks enabled. '
    "Perform one bounded debug-oriented interaction by focusing a visible search or toolbar control "
    "if needed, then summarize the observed state in plain text without closing the app."
)


@dataclass
class CILoggValidationConfig:
    title_regex: str
    sample_log: Path
    search_text: str
    launch_args: tuple[str, ...]
    require_computer_use: bool
    computer_use_goal: str

    @classmethod
    def from_env(cls) -> "CILoggValidationConfig":
        sample_log = _resolve_sample_log()
        title_regex = os.environ.get("MAIN_WINDOW_TITLE_REGEX", "").strip() or "(?i)cilogg"
        search_text = os.environ.get("CILOGG_SMOKE_SEARCH_TEXT", DEFAULT_SEARCH_TEXT)
        launch_args_raw = os.environ.get("CILOGG_SMOKE_LAUNCH_ARGS")
        if launch_args_raw is None:
            launch_args_raw = "" if os.environ.get("APP_ARGS") else " ".join(DEFAULT_LAUNCH_ARGS)
        launch_args = tuple(part for part in launch_args_raw.split() if part)
        require_computer_use = os.environ.get("CILOGG_SMOKE_REQUIRE_COMPUTER_USE", "1") != "0"
        goal_template = os.environ.get("CILOGG_SMOKE_COMPUTER_GOAL", DEFAULT_COMPUTER_USE_GOAL)
        computer_use_goal = goal_template.format(search_text=search_text, sample_log=sample_log.name)
        return cls(
            title_regex=title_regex,
            sample_log=sample_log,
            search_text=search_text,
            launch_args=launch_args,
            require_computer_use=require_computer_use,
            computer_use_goal=computer_use_goal,
        )

    def validate(self, service: WinGuiService) -> None:
        problems: list[str] = []
        if not service.app_exe:
            problems.append("APP_EXE is not set.")
        if not os.environ.get("APP_WORKDIR"):
            problems.append("APP_WORKDIR is not set.")
        if not os.environ.get("APP_LOG_DIR"):
            problems.append("APP_LOG_DIR is not set.")
        if not os.environ.get("MAIN_WINDOW_TITLE_REGEX"):
            problems.append("MAIN_WINDOW_TITLE_REGEX is not set.")
        if not os.environ.get("APP_STATE_DUMP_ARG"):
            problems.append("APP_STATE_DUMP_ARG is not set.")
        if not os.environ.get("QT_AUTOMATION_ENV_VAR"):
            problems.append("QT_AUTOMATION_ENV_VAR is not set.")
        if not self.sample_log.exists():
            problems.append(f"Sample log does not exist: {self.sample_log}")
        if self.require_computer_use and not os.environ.get("OPENAI_API_KEY"):
            problems.append("OPENAI_API_KEY is required for computer-use validation.")
        if problems:
            raise RuntimeError("Invalid CILogg validation environment:\n- " + "\n- ".join(problems))


class CILoggValidationRunner:
    def __init__(self, service: WinGuiService | None = None, config: CILoggValidationConfig | None = None) -> None:
        self.service = service or WinGuiService()
        self.config = config or CILoggValidationConfig.from_env()
        self._launch_pid: int | None = None

    def run(self) -> dict[str, Any]:
        self.config.validate(self.service)
        report: dict[str, Any] = {"ok": False, "semantic": {}, "computer_use": None}
        launch: dict[str, Any] | None = None
        try:
            launch = self.service.restart_app(args=list(self.config.launch_args))
            self._launch_pid = int(launch["pid"])
            semantic = self._run_semantic_matrix()
            report["semantic"] = semantic
            report["semantic_bundle"] = self._capture_bundle("cilogg-semantic-smoke")

            if self.config.require_computer_use:
                computer_use = self._run_computer_use()
                report["computer_use"] = computer_use
                report["computer_use_bundle"] = self._capture_bundle("cilogg-computer-use")

            report["ok"] = True
            return report
        except Exception as exc:
            report["error"] = {"type": type(exc).__name__, "message": str(exc)}
            report["failure_bundle"] = self._capture_bundle(f"cilogg-validation-failure:{type(exc).__name__}")
            raise
        finally:
            if launch and launch.get("pid"):
                try:
                    self.service.close_app(pid=int(launch["pid"]))
                except Exception:
                    pass

    def _run_semantic_matrix(self) -> dict[str, Any]:
        launch_session = self.service.create_session(
            title_regex=self.config.title_regex,
            pid=self._launch_pid,
            adapter="cilogg",
            capture_mode="window",
        )
        self.service.wait_window_stable(timeout_sec=10.0)
        self.service.capture_screenshot(mode="window")
        self.service.wait_process_idle(timeout_sec=10.0)

        initial_dump = self.service.dump_qt_state()["state"]
        _require_snapshot_shape(initial_dump)

        self.service.cilogg_open_log(str(self.config.sample_log))
        self.service.wait_window_stable(timeout_sec=10.0)
        self.service.wait_process_idle(timeout_sec=10.0)

        state_after_open = self.service.cilogg_get_state()["state"]
        active_file = str(state_after_open.get("active_file") or "")
        if not active_file or Path(active_file).name.lower() != self.config.sample_log.name.lower():
            raise AssertionFailedError(
                f"CILogg did not report the expected active file. Got {active_file!r}, expected {self.config.sample_log.name!r}."
            )

        search = self.service.cilogg_search(self.config.search_text)
        search_state = self._wait_for_search_state(search["state"])
        if search_state.get("search_text") != self.config.search_text:
            raise AssertionFailedError("CILogg search state did not retain the expected search text.")
        if int(search_state.get("match_count") or 0) <= 0:
            raise AssertionFailedError("CILogg search did not produce any matches.")

        follow_enabled = self.service.cilogg_toggle_follow(enabled=True)
        if not follow_enabled["state"].get("follow_mode"):
            raise AssertionFailedError("CILogg follow mode did not become enabled.")
        follow_disabled = self.service.cilogg_toggle_follow(enabled=False)
        if follow_disabled["state"].get("follow_mode"):
            raise AssertionFailedError("CILogg follow mode did not become disabled.")

        visible_range = self.service.cilogg_get_visible_range()
        if visible_range.get("visible_line_start") is None or visible_range.get("visible_line_end") is None:
            raise AssertionFailedError("CILogg visible range did not expose both bounds.")

        fallback_click = self._run_qt_fallback_click()

        return {
            "session": launch_session["session"],
            "active_file": active_file,
            "search": search,
            "follow_enabled": follow_enabled,
            "follow_disabled": follow_disabled,
            "visible_range": visible_range,
            "fallback_click": fallback_click,
        }

    def _run_qt_fallback_click(self) -> dict[str, Any]:
        state = self.service.dump_qt_state()["state"]
        target = _pick_clickable_target(state)
        if target.get("objectName"):
            result = self.service.click_qt_object(object_name=str(target["objectName"]))
        elif target.get("accessibleName"):
            result = self.service.click_qt_object(accessible_name=str(target["accessibleName"]))
        else:
            raise AdapterError("No suitable Qt fallback target was available.")
        self.service.capture_screenshot(mode="window")
        return {"target": target, "result": result}

    def _run_computer_use(self) -> dict[str, Any]:
        runner = ComputerUseRunner(service=self.service)
        response = runner.run(
            goal=self.config.computer_use_goal,
            window_title=self.config.title_regex,
            full_screen=False,
            pid=self._launch_pid,
        )
        summary = getattr(response, "output_text", None)
        if not summary:
            summary = json.dumps(response.model_dump(), indent=2)
        if not str(summary).strip():
            raise AssertionFailedError("Computer-use validation returned an empty summary.")
        return {"ok": True, "summary": summary}

    def _wait_for_search_state(
        self,
        initial_state: dict[str, Any],
        *,
        timeout_sec: float = 10.0,
    ) -> dict[str, Any]:
        deadline = time.time() + timeout_sec
        state = initial_state
        while time.time() < deadline:
            search_text = state.get("search_text")
            match_count = int(state.get("match_count") or 0)
            if search_text == self.config.search_text and not state.get("search_in_progress") and match_count > 0:
                return state
            time.sleep(0.25)
            state = self.service.cilogg_get_state()["state"]
        return state

    def _capture_bundle(self, reason: str) -> dict[str, Any] | None:
        try:
            return self.service.create_artifact_bundle(reason=reason)
        except Exception as exc:
            return {"ok": False, "error": str(exc), "reason": reason}


@dataclass
class CILoggFilteredWrapValidationConfig:
    title_regex: str
    repro_log: Path
    search_text: str
    launch_args: tuple[str, ...]
    require_computer_use: bool
    computer_use_goal: str

    @classmethod
    def from_env(cls) -> "CILoggFilteredWrapValidationConfig":
        title_regex = os.environ.get("MAIN_WINDOW_TITLE_REGEX", "").strip() or "(?i)cilogg"
        launch_args_raw = os.environ.get("CILOGG_SMOKE_LAUNCH_ARGS")
        if launch_args_raw is None:
            launch_args_raw = "" if os.environ.get("APP_ARGS") else " ".join(DEFAULT_LAUNCH_ARGS)
        launch_args = tuple(part for part in launch_args_raw.split() if part)
        repro_log = Path(
            os.environ.get("CILOGG_FILTERED_WRAP_LOG", str(DEFAULT_FILTERED_WRAP_LOG))
        ).expanduser().resolve()
        search_text = os.environ.get("CILOGG_FILTERED_WRAP_SEARCH_TEXT", DEFAULT_FILTERED_WRAP_SEARCH)
        require_computer_use = os.environ.get("CILOGG_FILTERED_WRAP_REQUIRE_COMPUTER_USE", "0") != "0"
        goal_template = os.environ.get(
            "CILOGG_FILTERED_WRAP_COMPUTER_GOAL",
            (
                "Inspect the active CILogg filtered pane after word wrap has been enabled. "
                'Decide whether a large blank gap is visible below a wrapped long filtered record for the search "{search_text}". '
                "Do one bounded debug-oriented interaction if needed, then summarize the result plainly without closing the app."
            ),
        )
        return cls(
            title_regex=title_regex,
            repro_log=repro_log,
            search_text=search_text,
            launch_args=launch_args,
            require_computer_use=require_computer_use,
            computer_use_goal=goal_template.format(search_text=search_text, repro_log=repro_log.name),
        )

    def validate(self, service: WinGuiService) -> None:
        problems: list[str] = []
        if not service.app_exe:
            problems.append("APP_EXE is not set.")
        if not os.environ.get("APP_WORKDIR"):
            problems.append("APP_WORKDIR is not set.")
        if not os.environ.get("APP_LOG_DIR"):
            problems.append("APP_LOG_DIR is not set.")
        if not os.environ.get("MAIN_WINDOW_TITLE_REGEX"):
            problems.append("MAIN_WINDOW_TITLE_REGEX is not set.")
        if not os.environ.get("APP_STATE_DUMP_ARG"):
            problems.append("APP_STATE_DUMP_ARG is not set.")
        if not os.environ.get("QT_AUTOMATION_ENV_VAR"):
            problems.append("QT_AUTOMATION_ENV_VAR is not set.")
        if not self.repro_log.exists():
            problems.append(f"Filtered-wrap repro log does not exist: {self.repro_log}")
        if self.require_computer_use and not os.environ.get("OPENAI_API_KEY"):
            problems.append("OPENAI_API_KEY is required for computer-use validation.")
        if problems:
            raise RuntimeError("Invalid filtered-wrap validation environment:\n- " + "\n- ".join(problems))


class CILoggFilteredWrapValidationRunner:
    def __init__(
        self,
        service: WinGuiService | None = None,
        config: CILoggFilteredWrapValidationConfig | None = None,
    ) -> None:
        self.service = service or WinGuiService()
        self.config = config or CILoggFilteredWrapValidationConfig.from_env()
        self._launch_pid: int | None = None

    def run(self) -> dict[str, Any]:
        self.config.validate(self.service)
        report: dict[str, Any] = {"ok": False, "bug_validation": {}, "computer_use": None}
        launch: dict[str, Any] | None = None
        try:
            launch = self.service.restart_app(args=list(self.config.launch_args))
            self._launch_pid = int(launch["pid"])
            report["bug_validation"] = self._run_bug_validation()
            report["bug_bundle"] = self._capture_bundle("cilogg-filtered-wrap-gap")

            if self.config.require_computer_use:
                report["computer_use"] = self._run_computer_use()
                report["computer_use_bundle"] = self._capture_bundle("cilogg-filtered-wrap-gap-computer-use")

            report["ok"] = True
            return report
        except Exception as exc:
            report["error"] = {"type": type(exc).__name__, "message": str(exc)}
            report["failure_bundle"] = self._capture_bundle(f"cilogg-filtered-wrap-failure:{type(exc).__name__}")
            raise
        finally:
            if launch and launch.get("pid"):
                try:
                    self.service.close_app(pid=int(launch["pid"]))
                except Exception:
                    pass

    def _run_bug_validation(self) -> dict[str, Any]:
        session = self.service.create_session(
            title_regex=self.config.title_regex,
            pid=self._launch_pid,
            adapter="cilogg",
            capture_mode="window",
        )
        self.service.wait_window_stable(timeout_sec=10.0)
        self.service.cilogg_open_log(str(self.config.repro_log))
        self.service.wait_window_stable(timeout_sec=10.0)
        self.service.wait_process_idle(timeout_sec=10.0)

        self.service.invoke_qt_action("textWrapAction")
        self._ensure_text_wrap_enabled()
        self.service.cilogg_search(self.config.search_text, regex=True)
        state = self._wait_for_search_state()
        self.service.click_qt_object(object_name="filteredView")
        self.service.send_hotkey(["ctrl", "end"])
        self.service.wait_window_stable(timeout_sec=5.0)
        screenshot = self.service.capture_screenshot(mode="window")

        qt_state = self.service.dump_qt_state()["state"]
        normalized_state = self.service.cilogg_get_state()["state"]
        visual_gap = _measure_filtered_wrap_gap(Path(screenshot["path"]), qt_state)

        if not normalized_state.get("text_wrap_enabled"):
            raise AssertionFailedError("CILogg did not report text wrap as enabled.")
        if normalized_state.get("filtered_visible_line_start") is None:
            raise AssertionFailedError("CILogg did not report the filtered visible start line.")
        if normalized_state.get("filtered_visible_line_end") is None:
            raise AssertionFailedError("CILogg did not report the filtered visible end line.")
        if int(normalized_state.get("match_count") or 0) <= 0:
            raise AssertionFailedError("Filtered-wrap validation did not produce any matches.")
        if visual_gap["max_empty_run"] > FILTERED_WRAP_MAX_EMPTY_GAP_ROWS:
            raise AssertionFailedError(
                "Filtered wrap screenshot still shows a large blank gap below the rendered content."
            )

        return {
            "session": session["session"],
            "search_text": self.config.search_text,
            "repro_log": str(self.config.repro_log),
            "state": normalized_state,
            "visual_gap": visual_gap,
            "focus_warning": None
            if normalized_state.get("focused_view_object_name") == "filteredView"
            else "filteredView focus was not reflected in ciloggState; using filtered visible range as the validation oracle.",
            "qt_state_keys": sorted(qt_state.keys()),
        }

    def _wait_for_search_state(self, timeout_sec: float = 10.0) -> dict[str, Any]:
        deadline = time.time() + timeout_sec
        state = self.service.cilogg_get_state()["state"]
        while time.time() < deadline:
            if (
                state.get("search_text") == self.config.search_text
                and not state.get("search_in_progress")
                and int(state.get("match_count") or 0) > 0
            ):
                return state
            time.sleep(0.25)
            state = self.service.cilogg_get_state()["state"]
        return state

    def _ensure_text_wrap_enabled(self, timeout_sec: float = 5.0) -> dict[str, Any]:
        state = self.service.cilogg_get_state()["state"]
        if state.get("text_wrap_enabled"):
            return state

        self.service.click_qt_object(object_name="logMainView")
        self.service.send_hotkey(["w"])

        deadline = time.time() + timeout_sec
        while time.time() < deadline:
            state = self.service.cilogg_get_state()["state"]
            if state.get("text_wrap_enabled"):
                return state
            time.sleep(0.25)

        raise AssertionFailedError("CILogg did not report text wrap as enabled.")

    def _run_computer_use(self) -> dict[str, Any]:
        runner = ComputerUseRunner(service=self.service)
        response = runner.run(
            goal=self.config.computer_use_goal,
            window_title=self.config.title_regex,
            full_screen=False,
            pid=self._launch_pid,
        )
        summary = getattr(response, "output_text", None)
        if not summary:
            summary = json.dumps(response.model_dump(), indent=2)
        if not str(summary).strip():
            raise AssertionFailedError("Filtered-wrap computer-use validation returned an empty summary.")
        return {"ok": True, "summary": summary}

    def _capture_bundle(self, reason: str) -> dict[str, Any] | None:
        try:
            return self.service.create_artifact_bundle(reason=reason)
        except Exception as exc:
            return {"ok": False, "error": str(exc), "reason": reason}


def _resolve_sample_log() -> Path:
    if os.environ.get("CILOGG_SAMPLE_LOG"):
        return Path(os.environ["CILOGG_SAMPLE_LOG"]).expanduser().resolve()
    repo_root = Path(__file__).resolve().parents[1]
    sibling_sample = repo_root.parent / "klogg" / "test_data" / "ansi_colors_example.txt"
    if sibling_sample.exists():
        return sibling_sample.resolve()
    return Path("ansi_colors_example.txt").resolve()


def _require_snapshot_shape(state: dict[str, Any]) -> None:
    for key in ("windowInfo", "actions", "ciloggState"):
        if key not in state:
            raise AssertionFailedError(f"Qt state dump is missing the required {key!r} field.")


def _measure_filtered_wrap_gap(screenshot_path: Path, state: dict[str, Any]) -> dict[str, Any]:
    from collections import Counter

    from PIL import Image

    node = _find_node_by_object_name(state, "filteredView")
    if node is None:
        raise AssertionFailedError("Qt state dump did not include filteredView bounds.")

    bounds = node.get("bounds") or {}
    x = int(bounds.get("x") or 0)
    y = int(bounds.get("y") or 0)
    width = int(bounds.get("width") or 0)
    height = int(bounds.get("height") or 0)
    if width <= 32 or height <= 24:
        raise AssertionFailedError("Qt state dump reported invalid filteredView bounds.")

    image = Image.open(screenshot_path).convert("RGB")
    crop = image.crop((x + 4, y + 4, x + width - 18, y + height - 4))
    pixels = [crop.getpixel((column, row)) for row in range(crop.height) for column in range(crop.width)]
    background, _count = Counter(pixels).most_common(1)[0]

    max_empty_run = 0
    current_run = 0
    for row in range(crop.height):
        row_pixels = [crop.getpixel((column, row)) for column in range(crop.width)]
        background_like = sum(
            1
            for pixel in row_pixels
            if sum(abs(pixel[index] - background[index]) for index in range(3)) < 18
        )
        ink = sum(
            1
            for pixel in row_pixels
            if sum(abs(pixel[index] - background[index]) for index in range(3)) >= 40
        )
        background_fraction = background_like / max(1, crop.width)
        ink_fraction = ink / max(1, crop.width)
        is_empty = background_fraction > 0.93 and ink_fraction < 0.04
        if is_empty:
            current_run += 1
            max_empty_run = max(max_empty_run, current_run)
        else:
            current_run = 0

    return {
        "screenshot_path": str(screenshot_path),
        "filtered_view_bounds": {"x": x, "y": y, "width": width, "height": height},
        "crop_size": {"width": crop.width, "height": crop.height},
        "background_rgb": list(background),
        "max_empty_run": max_empty_run,
        "max_allowed_empty_run": FILTERED_WRAP_MAX_EMPTY_GAP_ROWS,
    }


def _find_node_by_object_name(state: dict[str, Any], object_name: str) -> dict[str, Any] | None:
    queue = [state]
    while queue:
        node = queue.pop(0)
        if node.get("objectName") == object_name:
            return node
        queue.extend(node.get("children", []))
    return None


def _pick_clickable_target(state: dict[str, Any]) -> dict[str, Any]:
    preferred_object_names = ("mainToolBar", "infoLine", "mainTabWidget")
    preferred_roles = {"lineedit", "widget", "toolbar", "tabbar", "tabwidget", "logview"}

    nodes = _flatten_qt_tree(state)
    for object_name in preferred_object_names:
        for node in nodes:
            if node.get("objectName") == object_name and _is_clickable(node):
                return node

    for node in nodes:
        if node.get("role") in preferred_roles and _is_clickable(node):
            return node

    raise AdapterError("No clickable Qt object was found for fallback validation.")


def _flatten_qt_tree(root: dict[str, Any]) -> list[dict[str, Any]]:
    queue = [root]
    nodes: list[dict[str, Any]] = []
    while queue:
        node = queue.pop(0)
        nodes.append(node)
        queue.extend(node.get("children", []))
    return nodes


def _is_clickable(node: dict[str, Any]) -> bool:
    bounds = node.get("bounds")
    if not isinstance(bounds, dict):
        return False
    return (
        bool(node.get("visible", True))
        and bool(node.get("enabled", True))
        and int(bounds.get("width", 0)) > 0
        and int(bounds.get("height", 0)) > 0
    )
