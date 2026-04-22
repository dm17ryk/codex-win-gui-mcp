from __future__ import annotations

import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from adapters.cilogg_adapter import CILoggAdapter
from adapters.qt_adapter import QtAdapter


class AdapterParsingTests(unittest.TestCase):
    def test_qt_find_object_matches_object_name(self) -> None:
        adapter = QtAdapter(app_exe="", app_workdir="", dump_arg="--dump-state-json", automation_env_var="CILOGG_AUTOMATION")
        state = {
            "children": [
                {"objectName": "searchLineEdit", "accessibleName": "Search", "role": "LineEdit", "children": []}
            ]
        }
        result = adapter.find_qt_object(object_name="searchLineEdit", state=state)
        self.assertEqual(result["object"]["accessibleName"], "Search")

    def test_cilogg_state_is_normalized(self) -> None:
        state = {
            "ciloggState": {
                "activeFile": "sample.log",
                "activeTabTitle": "sample.log",
                "cursorLine": 10,
                "cursorColumn": 4,
                "visibleLineStart": 1,
                "visibleLineEnd": 100,
                "mainVisibleLineStart": 2,
                "mainVisibleLineEnd": 80,
                "filteredVisibleLineStart": 9,
                "filteredVisibleLineEnd": 12,
                "searchText": "error",
                "matchCount": 12,
                "followMode": True,
                "textWrapEnabled": True,
                "focusedViewObjectName": "filteredView",
                "scratchPad": False,
                "encoding": "utf-8",
                "parserMode": "default",
            }
        }
        adapter = CILoggAdapter(qt_adapter=QtAdapter(app_exe="", app_workdir="", dump_arg="", automation_env_var=""))
        parsed = adapter._extract_cilogg_state(state)
        self.assertEqual(parsed["active_file"], "sample.log")
        self.assertEqual(parsed["match_count"], 12)
        self.assertEqual(parsed["filtered_visible_line_end"], 12)
        self.assertTrue(parsed["text_wrap_enabled"])
        self.assertEqual(parsed["focused_view_object_name"], "filteredView")

    def test_dump_qt_state_reads_file_payload(self) -> None:
        adapter = QtAdapter(
            app_exe="cilogg.exe",
            app_workdir="",
            dump_arg="--dump-state-json",
            automation_env_var="CILOGG_AUTOMATION",
        )

        def fake_run(*, cmd: list[str], env: dict[str, str]) -> subprocess.CompletedProcess[str]:
            dump_path = Path(cmd[-1])
            dump_path.write_text(json.dumps({"objectName": "mainWindow", "ciloggState": {"activeFile": "sample.log"}}), encoding="utf-8")
            return subprocess.CompletedProcess(cmd, 0, "", "")

        adapter._run_subprocess = fake_run  # type: ignore[method-assign]
        state = adapter.dump_qt_state()
        self.assertEqual(state["ciloggState"]["activeFile"], "sample.log")

    def test_dump_qt_state_retries_until_json_is_complete(self) -> None:
        adapter = QtAdapter(
            app_exe="cilogg.exe",
            app_workdir="",
            dump_arg="--dump-state-json",
            automation_env_var="CILOGG_AUTOMATION",
        )
        dump_path: Path | None = None
        read_count = 0

        def fake_run(*, cmd: list[str], env: dict[str, str]) -> subprocess.CompletedProcess[str]:
            nonlocal dump_path
            dump_path = Path(cmd[-1])
            dump_path.write_text("", encoding="utf-8")
            return subprocess.CompletedProcess(cmd, 0, "", "")

        def fake_read_text(*args: object, **kwargs: object) -> str:
            nonlocal read_count
            read_count += 1
            if read_count == 1:
                return ""
            return json.dumps({"objectName": "mainWindow", "ciloggState": {"activeFile": "sample.log"}})

        adapter._run_subprocess = fake_run  # type: ignore[method-assign]

        with (
            mock.patch("adapters.qt_adapter.time.sleep") as sleep,
            mock.patch("pathlib.Path.read_text", side_effect=fake_read_text),
        ):
            state = adapter.dump_qt_state()

        self.assertIsNotNone(dump_path)
        self.assertEqual(state["ciloggState"]["activeFile"], "sample.log")
        sleep.assert_called_once_with(0.1)

    def test_invoke_qt_action_uses_app_command(self) -> None:
        adapter = QtAdapter(
            app_exe="cilogg.exe",
            app_workdir="",
            dump_arg="--dump-state-json",
            automation_env_var="CILOGG_AUTOMATION",
        )
        adapter.run_app_command = mock.Mock(return_value={"followMode": True})  # type: ignore[method-assign]
        state = {"actions": [{"objectName": "followAction", "text": "Follow File"}]}

        result = adapter.invoke_qt_action("followAction", state=state)

        adapter.run_app_command.assert_called_once_with(  # type: ignore[attr-defined]
            ["command", "--action", "invoke_action", "--object-name", "followAction"]
        )
        self.assertTrue(result["ok"])

    def test_run_app_command_retries_transient_primary_contact_failure(self) -> None:
        adapter = QtAdapter(
            app_exe="cilogg.exe",
            app_workdir="",
            dump_arg="--dump-state-json",
            automation_env_var="CILOGG_AUTOMATION",
        )
        attempts = [
            subprocess.CompletedProcess(
                ["cilogg.exe", "command", "--action", "get_info"],
                1,
                "",
                "Failed to contact the primary CILogg instance.",
            ),
            subprocess.CompletedProcess(
                ["cilogg.exe", "command", "--action", "get_info"],
                0,
                '{"windows":[]}',
                "",
            ),
        ]
        adapter._run_subprocess = mock.Mock(side_effect=attempts)  # type: ignore[method-assign]

        with mock.patch("adapters.qt_adapter.time.sleep") as sleep:
            result = adapter.run_app_command(["command", "--action", "get_info"])

        self.assertEqual(result["windows"], [])
        self.assertEqual(adapter._run_subprocess.call_count, 2)  # type: ignore[attr-defined]
        sleep.assert_called_once_with(1.0)

    def test_cilogg_open_log_executes_command(self) -> None:
        qt = QtAdapter(app_exe="", app_workdir="", dump_arg="", automation_env_var="")
        qt.run_app_command = mock.Mock(return_value={})  # type: ignore[method-assign]
        adapter = CILoggAdapter(qt_adapter=qt)

        result = adapter.cilogg_open_log("sample.log")

        qt.run_app_command.assert_called_once_with(["command", "--action", "open_file", "--file", "sample.log"])  # type: ignore[attr-defined]
        self.assertEqual(result["path"], "sample.log")

    def test_cilogg_search_executes_command(self) -> None:
        qt = QtAdapter(app_exe="", app_workdir="", dump_arg="", automation_env_var="")
        qt.run_app_command = mock.Mock(return_value={"searchText": "error", "matchCount": 3})  # type: ignore[method-assign]
        adapter = CILoggAdapter(qt_adapter=qt)

        result = adapter.cilogg_search("error", regex=True, case_sensitive=True)

        qt.run_app_command.assert_called_once_with(  # type: ignore[attr-defined]
            ["command", "--action", "search", "--text", "error", "--regex", "--case-sensitive"]
        )
        self.assertEqual(result["state"]["match_count"], 3)

    def test_cilogg_toggle_follow_executes_command(self) -> None:
        qt = QtAdapter(app_exe="", app_workdir="", dump_arg="", automation_env_var="")
        qt.dump_qt_state = mock.Mock(return_value={"ciloggState": {"followMode": False}})  # type: ignore[method-assign]
        qt.run_app_command = mock.Mock(return_value={"followMode": True})  # type: ignore[method-assign]
        adapter = CILoggAdapter(qt_adapter=qt)

        result = adapter.cilogg_toggle_follow()

        qt.run_app_command.assert_called_once_with(["command", "--action", "set_follow_mode", "--enabled"])  # type: ignore[attr-defined]
        self.assertTrue(result["follow_mode"])


if __name__ == "__main__":
    unittest.main()
