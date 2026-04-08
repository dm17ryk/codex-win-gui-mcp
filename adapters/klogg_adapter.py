from __future__ import annotations

from typing import Any

from win_gui_core.errors import AdapterError

from .qt_adapter import QtAdapter


class KloggAdapter:
    def __init__(self, qt_adapter: QtAdapter) -> None:
        self.qt_adapter = qt_adapter

    def klogg_get_state(self) -> dict[str, Any]:
        state = self.qt_adapter.dump_qt_state()
        return {"ok": True, "state": self._extract_klogg_state(state)}

    def klogg_get_active_tab(self) -> dict[str, Any]:
        state = self.qt_adapter.dump_qt_state()
        extracted = self._extract_klogg_state(state)
        return {"ok": True, "active_tab_title": extracted["active_tab_title"], "active_file": extracted["active_file"]}

    def klogg_get_visible_range(self) -> dict[str, Any]:
        state = self.qt_adapter.dump_qt_state()
        extracted = self._extract_klogg_state(state)
        return {
            "ok": True,
            "visible_line_start": extracted["visible_line_start"],
            "visible_line_end": extracted["visible_line_end"],
        }

    def klogg_search(self, text: str, regex: bool = False, case_sensitive: bool = False) -> dict[str, Any]:
        return {
            "ok": True,
            "search_text": text,
            "regex": regex,
            "case_sensitive": case_sensitive,
            "note": "Search execution requires app-side automation support.",
        }

    def klogg_toggle_follow(self, enabled: bool | None = None) -> dict[str, Any]:
        state = self.qt_adapter.dump_qt_state()
        extracted = self._extract_klogg_state(state)
        current = bool(extracted["follow_mode"])
        return {"ok": True, "follow_mode": (not current) if enabled is None else enabled}

    def klogg_open_log(self, path: str) -> dict[str, Any]:
        if not path:
            raise AdapterError("klogg_open_log requires a non-empty file path.")
        return {"ok": True, "path": path, "note": "Opening the log file requires app-side automation support."}

    @staticmethod
    def _extract_klogg_state(state: dict[str, Any]) -> dict[str, Any]:
        data = state.get("kloggState") or state
        return {
            "active_file": data.get("activeFile"),
            "active_tab_title": data.get("activeTabTitle"),
            "cursor_line": data.get("cursorLine"),
            "cursor_column": data.get("cursorColumn"),
            "visible_line_start": data.get("visibleLineStart"),
            "visible_line_end": data.get("visibleLineEnd"),
            "search_text": data.get("searchText"),
            "match_count": data.get("matchCount"),
            "follow_mode": data.get("followMode"),
            "scratch_pad": data.get("scratchPad"),
            "encoding": data.get("encoding"),
            "parser_mode": data.get("parserMode"),
        }
