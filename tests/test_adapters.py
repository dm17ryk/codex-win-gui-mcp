from __future__ import annotations

import unittest

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


if __name__ == "__main__":
    unittest.main()
