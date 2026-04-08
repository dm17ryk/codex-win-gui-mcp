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
DEFAULT_LAUNCH_ARGS = ("-n", "-m", "-l", "-dddd")
DEFAULT_COMPUTER_USE_GOAL = (
    "Inspect the active klogg window. Confirm the visible log filename, whether the word "
    '"{search_text}" appears to be the current search, and whether follow mode looks enabled. '
    "Perform one bounded debug-oriented interaction by focusing a visible search or toolbar control "
    "if needed, then summarize the observed state in plain text without closing the app."
)


@dataclass
class KloggValidationConfig:
    title_regex: str
    sample_log: Path
    search_text: str
    launch_args: tuple[str, ...]
    require_computer_use: bool
    computer_use_goal: str

    @classmethod
    def from_env(cls) -> "KloggValidationConfig":
        sample_log = _resolve_sample_log()
        title_regex = os.environ.get("MAIN_WINDOW_TITLE_REGEX", "").strip() or "klogg"
        search_text = os.environ.get("KLOGG_SMOKE_SEARCH_TEXT", DEFAULT_SEARCH_TEXT)
        launch_args_raw = os.environ.get("KLOGG_SMOKE_LAUNCH_ARGS")
        if launch_args_raw is None:
            launch_args_raw = "" if os.environ.get("APP_ARGS") else " ".join(DEFAULT_LAUNCH_ARGS)
        launch_args = tuple(part for part in launch_args_raw.split() if part)
        require_computer_use = os.environ.get("KLOGG_SMOKE_REQUIRE_COMPUTER_USE", "1") != "0"
        goal_template = os.environ.get("KLOGG_SMOKE_COMPUTER_GOAL", DEFAULT_COMPUTER_USE_GOAL)
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
            raise RuntimeError("Invalid klogg validation environment:\n- " + "\n- ".join(problems))


class KloggValidationRunner:
    def __init__(self, service: WinGuiService | None = None, config: KloggValidationConfig | None = None) -> None:
        self.service = service or WinGuiService()
        self.config = config or KloggValidationConfig.from_env()
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
            report["semantic_bundle"] = self._capture_bundle("klogg-semantic-smoke")

            if self.config.require_computer_use:
                computer_use = self._run_computer_use()
                report["computer_use"] = computer_use
                report["computer_use_bundle"] = self._capture_bundle("klogg-computer-use")

            report["ok"] = True
            return report
        except Exception as exc:
            report["error"] = {"type": type(exc).__name__, "message": str(exc)}
            report["failure_bundle"] = self._capture_bundle(f"klogg-validation-failure:{type(exc).__name__}")
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
            adapter="klogg",
            capture_mode="window",
        )
        self.service.wait_window_stable(timeout_sec=10.0)
        self.service.capture_screenshot(mode="window")
        self.service.wait_process_idle(timeout_sec=10.0)

        initial_dump = self.service.dump_qt_state()["state"]
        _require_snapshot_shape(initial_dump)

        self.service.klogg_open_log(str(self.config.sample_log))
        self.service.wait_window_stable(timeout_sec=10.0)
        self.service.wait_process_idle(timeout_sec=10.0)

        state_after_open = self.service.klogg_get_state()["state"]
        active_file = str(state_after_open.get("active_file") or "")
        if not active_file or Path(active_file).name.lower() != self.config.sample_log.name.lower():
            raise AssertionFailedError(
                f"klogg did not report the expected active file. Got {active_file!r}, expected {self.config.sample_log.name!r}."
            )

        search = self.service.klogg_search(self.config.search_text)
        search_state = self._wait_for_search_state(search["state"])
        if search_state.get("search_text") != self.config.search_text:
            raise AssertionFailedError("klogg search state did not retain the expected search text.")
        if int(search_state.get("match_count") or 0) <= 0:
            raise AssertionFailedError("klogg search did not produce any matches.")

        follow_enabled = self.service.klogg_toggle_follow(enabled=True)
        if not follow_enabled["state"].get("follow_mode"):
            raise AssertionFailedError("klogg follow mode did not become enabled.")
        follow_disabled = self.service.klogg_toggle_follow(enabled=False)
        if follow_disabled["state"].get("follow_mode"):
            raise AssertionFailedError("klogg follow mode did not become disabled.")

        visible_range = self.service.klogg_get_visible_range()
        if visible_range.get("visible_line_start") is None or visible_range.get("visible_line_end") is None:
            raise AssertionFailedError("klogg visible range did not expose both bounds.")

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
            state = self.service.klogg_get_state()["state"]
        return state

    def _capture_bundle(self, reason: str) -> dict[str, Any] | None:
        try:
            return self.service.create_artifact_bundle(reason=reason)
        except Exception as exc:
            return {"ok": False, "error": str(exc), "reason": reason}


def _resolve_sample_log() -> Path:
    if os.environ.get("KLOGG_SAMPLE_LOG"):
        return Path(os.environ["KLOGG_SAMPLE_LOG"]).expanduser().resolve()
    repo_root = Path(__file__).resolve().parents[1]
    sibling_sample = repo_root.parent / "klogg" / "test_data" / "ansi_colors_example.txt"
    if sibling_sample.exists():
        return sibling_sample.resolve()
    return Path("ansi_colors_example.txt").resolve()


def _require_snapshot_shape(state: dict[str, Any]) -> None:
    for key in ("windowInfo", "actions", "kloggState"):
        if key not in state:
            raise AssertionFailedError(f"Qt state dump is missing the required {key!r} field.")


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
