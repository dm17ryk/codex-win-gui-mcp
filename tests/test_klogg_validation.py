from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from win_gui_core.klogg_validation import (
    KloggValidationConfig,
    _pick_clickable_target,
)


class KloggValidationConfigTests(unittest.TestCase):
    def test_validate_requires_computer_use_key_when_enabled(self) -> None:
        config = KloggValidationConfig(
            title_regex="klogg",
            sample_log=Path(__file__),
            search_text="Test",
            launch_args=("-n", "-m"),
            require_computer_use=True,
            computer_use_goal="Inspect klogg.",
        )
        service = mock.Mock()
        service.app_exe = "klogg.exe"

        with mock.patch.dict(
            os.environ,
            {
                "APP_WORKDIR": "D:\\klogg",
                "APP_LOG_DIR": "D:\\klogg\\logs",
                "MAIN_WINDOW_TITLE_REGEX": "klogg",
                "APP_STATE_DUMP_ARG": "--dump-state-json",
                "QT_AUTOMATION_ENV_VAR": "KLOGG_AUTOMATION",
            },
            clear=False,
        ):
            with self.assertRaisesRegex(RuntimeError, "OPENAI_API_KEY"):
                config.validate(service)

    def test_from_env_uses_explicit_sample_log(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            sample = Path(tmp) / "sample.log"
            sample.write_text("Test", encoding="utf-8")
            with mock.patch.dict(
                os.environ,
                {
                    "KLOGG_SAMPLE_LOG": str(sample),
                    "KLOGG_SMOKE_SEARCH_TEXT": "needle",
                    "MAIN_WINDOW_TITLE_REGEX": "klogg",
                    "KLOGG_SMOKE_REQUIRE_COMPUTER_USE": "0",
                },
                clear=False,
            ):
                config = KloggValidationConfig.from_env()
        self.assertEqual(config.sample_log, sample.resolve())
        self.assertEqual(config.search_text, "needle")
        self.assertFalse(config.require_computer_use)


class KloggValidationSelectionTests(unittest.TestCase):
    def test_pick_clickable_target_prefers_named_object(self) -> None:
        state = {
            "objectName": "mainWindow",
            "children": [
                {
                    "objectName": "infoLine",
                    "role": "widget",
                    "visible": True,
                    "enabled": True,
                    "bounds": {"x": 1, "y": 2, "width": 120, "height": 24},
                    "children": [],
                },
                {
                    "objectName": "someButton",
                    "role": "widget",
                    "visible": True,
                    "enabled": True,
                    "bounds": {"x": 1, "y": 2, "width": 12, "height": 12},
                    "children": [],
                },
            ],
        }
        target = _pick_clickable_target(state)
        self.assertEqual(target["objectName"], "infoLine")


if __name__ == "__main__":
    unittest.main()
