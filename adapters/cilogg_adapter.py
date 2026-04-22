from __future__ import annotations

from typing import Any

from win_gui_core.errors import AdapterError

from .qt_adapter import QtAdapter


class CILoggAdapter:
    def __init__(self, qt_adapter: QtAdapter) -> None:
        self.qt_adapter = qt_adapter

    def cilogg_get_state(self) -> dict[str, Any]:
        state = self.qt_adapter.dump_qt_state()
        return {"ok": True, "state": self._extract_cilogg_state(state)}

    def cilogg_get_active_tab(self) -> dict[str, Any]:
        state = self.qt_adapter.dump_qt_state()
        extracted = self._extract_cilogg_state(state)
        return {"ok": True, "active_tab_title": extracted["active_tab_title"], "active_file": extracted["active_file"]}

    def cilogg_get_visible_range(self) -> dict[str, Any]:
        state = self.qt_adapter.dump_qt_state()
        extracted = self._extract_cilogg_state(state)
        return {
            "ok": True,
            "visible_line_start": extracted["visible_line_start"],
            "visible_line_end": extracted["visible_line_end"],
        }

    def cilogg_search(self, text: str, regex: bool = False, case_sensitive: bool = False) -> dict[str, Any]:
        if not text:
            raise AdapterError("cilogg_search requires a non-empty search expression.")
        args = ["command", "--action", "search", "--text", text]
        if regex:
            args.append("--regex")
        if case_sensitive:
            args.append("--case-sensitive")
        result = self.qt_adapter.run_app_command(args)
        extracted = self._extract_cilogg_state(result) if result else self._extract_cilogg_state(self.qt_adapter.dump_qt_state())
        return {
            "ok": True,
            "search_text": text,
            "regex": regex,
            "case_sensitive": case_sensitive,
            "state": extracted,
        }

    def cilogg_toggle_follow(self, enabled: bool | None = None) -> dict[str, Any]:
        state = self.qt_adapter.dump_qt_state()
        extracted = self._extract_cilogg_state(state)
        current = bool(extracted["follow_mode"])
        target_state = (not current) if enabled is None else enabled
        result = self.qt_adapter.run_app_command(
            ["command", "--action", "set_follow_mode", "--enabled" if target_state else "--disabled"]
        )
        next_state = self._extract_cilogg_state(result) if result else self._extract_cilogg_state(self.qt_adapter.dump_qt_state())
        return {"ok": True, "follow_mode": target_state, "state": next_state}

    def cilogg_open_log(self, path: str) -> dict[str, Any]:
        if not path:
            raise AdapterError("cilogg_open_log requires a non-empty file path.")
        self.qt_adapter.run_app_command(["command", "--action", "open_file", "--file", path])
        return {"ok": True, "path": path}

    @staticmethod
    def _extract_cilogg_state(state: dict[str, Any]) -> dict[str, Any]:
        data = state.get("ciloggState") or state
        return {
            "active_file": data.get("activeFile"),
            "active_tab_title": data.get("activeTabTitle"),
            "cursor_line": data.get("cursorLine"),
            "cursor_column": data.get("cursorColumn"),
            "visible_line_start": data.get("visibleLineStart"),
            "visible_line_end": data.get("visibleLineEnd"),
            "main_visible_line_start": data.get("mainVisibleLineStart"),
            "main_visible_line_end": data.get("mainVisibleLineEnd"),
            "filtered_visible_line_start": data.get("filteredVisibleLineStart"),
            "filtered_visible_line_end": data.get("filteredVisibleLineEnd"),
            "search_text": data.get("searchText"),
            "match_count": data.get("matchCount"),
            "search_in_progress": data.get("searchInProgress"),
            "follow_mode": data.get("followMode"),
            "text_wrap_enabled": data.get("textWrapEnabled"),
            "focused_view_object_name": data.get("focusedViewObjectName"),
            "loading_in_progress": data.get("loadingInProgress"),
            "startup_ready": data.get("startupReady"),
            "window_id": data.get("windowId"),
            "window_index": data.get("windowIndex"),
            "scratch_pad": data.get("scratchPad"),
            "encoding": data.get("encoding"),
            "parser_mode": data.get("parserMode"),
        }
