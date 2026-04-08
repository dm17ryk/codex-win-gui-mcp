from __future__ import annotations

import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from adapters.klogg_adapter import KloggAdapter
from adapters.qt_adapter import QtAdapter


class AdapterParsingTests(unittest.TestCase):
    def test_qt_find_object_matches_object_name(self) -> None:
        adapter = QtAdapter(app_exe="", app_workdir="", dump_arg="--dump-state-json", automation_env_var="KLOGG_AUTOMATION")
        state = {
            "children": [
                {"objectName": "searchLineEdit", "accessibleName": "Search", "role": "LineEdit", "children": []}
            ]
        }
        result = adapter.find_qt_object(object_name="searchLineEdit", state=state)
        self.assertEqual(result["object"]["accessibleName"], "Search")

    def test_klogg_state_is_normalized(self) -> None:
        state = {
            "kloggState": {
                "activeFile": "sample.log",
                "activeTabTitle": "sample.log",
                "cursorLine": 10,
                "cursorColumn": 4,
                "visibleLineStart": 1,
                "visibleLineEnd": 100,
                "searchText": "error",
                "matchCount": 12,
                "followMode": True,
                "scratchPad": False,
                "encoding": "utf-8",
                "parserMode": "default",
            }
        }
        adapter = KloggAdapter(qt_adapter=QtAdapter(app_exe="", app_workdir="", dump_arg="", automation_env_var=""))
        parsed = adapter._extract_klogg_state(state)
        self.assertEqual(parsed["active_file"], "sample.log")
        self.assertEqual(parsed["match_count"], 12)

    def test_dump_qt_state_reads_file_payload(self) -> None:
        adapter = QtAdapter(
            app_exe="klogg.exe",
            app_workdir="",
            dump_arg="--dump-state-json",
            automation_env_var="KLOGG_AUTOMATION",
        )

        def fake_run(*, cmd: list[str], env: dict[str, str]) -> subprocess.CompletedProcess[str]:
            dump_path = Path(cmd[-1])
            dump_path.write_text(json.dumps({"objectName": "mainWindow", "kloggState": {"activeFile": "sample.log"}}), encoding="utf-8")
            return subprocess.CompletedProcess(cmd, 0, "", "")

        adapter._run_subprocess = fake_run  # type: ignore[method-assign]
        state = adapter.dump_qt_state()
        self.assertEqual(state["kloggState"]["activeFile"], "sample.log")

    def test_invoke_qt_action_uses_app_command(self) -> None:
        adapter = QtAdapter(
            app_exe="klogg.exe",
            app_workdir="",
            dump_arg="--dump-state-json",
            automation_env_var="KLOGG_AUTOMATION",
        )
        adapter.run_app_command = mock.Mock(return_value={"followMode": True})  # type: ignore[method-assign]
        state = {"actions": [{"objectName": "followAction", "text": "Follow File"}]}

        result = adapter.invoke_qt_action("followAction", state=state)

        adapter.run_app_command.assert_called_once_with(  # type: ignore[attr-defined]
            ["command", "--action", "invoke_action", "--object-name", "followAction"]
        )
        self.assertTrue(result["ok"])

    def test_klogg_open_log_executes_command(self) -> None:
        qt = QtAdapter(app_exe="", app_workdir="", dump_arg="", automation_env_var="")
        qt.run_app_command = mock.Mock(return_value={})  # type: ignore[method-assign]
        adapter = KloggAdapter(qt_adapter=qt)

        result = adapter.klogg_open_log("sample.log")

        qt.run_app_command.assert_called_once_with(["command", "--action", "open_file", "--file", "sample.log"])  # type: ignore[attr-defined]
        self.assertEqual(result["path"], "sample.log")

    def test_klogg_search_executes_command(self) -> None:
        qt = QtAdapter(app_exe="", app_workdir="", dump_arg="", automation_env_var="")
        qt.run_app_command = mock.Mock(return_value={"searchText": "error", "matchCount": 3})  # type: ignore[method-assign]
        adapter = KloggAdapter(qt_adapter=qt)

        result = adapter.klogg_search("error", regex=True, case_sensitive=True)

        qt.run_app_command.assert_called_once_with(  # type: ignore[attr-defined]
            ["command", "--action", "search", "--text", "error", "--regex", "--case-sensitive"]
        )
        self.assertEqual(result["state"]["match_count"], 3)

    def test_klogg_toggle_follow_executes_command(self) -> None:
        qt = QtAdapter(app_exe="", app_workdir="", dump_arg="", automation_env_var="")
        qt.dump_qt_state = mock.Mock(return_value={"kloggState": {"followMode": False}})  # type: ignore[method-assign]
        qt.run_app_command = mock.Mock(return_value={"followMode": True})  # type: ignore[method-assign]
        adapter = KloggAdapter(qt_adapter=qt)

        result = adapter.klogg_toggle_follow()

        qt.run_app_command.assert_called_once_with(["command", "--action", "set_follow_mode", "--enabled"])  # type: ignore[attr-defined]
        self.assertTrue(result["follow_mode"])


if __name__ == "__main__":
    unittest.main()
