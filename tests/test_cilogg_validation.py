from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from win_gui_core.cilogg_validation import (
    CILoggFilteredWrapValidationConfig,
    CILoggValidationConfig,
    _measure_filtered_wrap_gap,
    _pick_clickable_target,
)


class CILoggValidationConfigTests(unittest.TestCase):
    def test_validate_requires_computer_use_key_when_enabled(self) -> None:
        config = CILoggValidationConfig(
            title_regex=r"(?i)cilogg",
            sample_log=Path(__file__),
            search_text="Test",
            launch_args=("-n",),
            require_computer_use=True,
            computer_use_goal="Inspect CILogg.",
        )
        service = mock.Mock()
        service.app_exe = "cilogg.exe"

        with mock.patch.dict(
            os.environ,
            {
                "APP_WORKDIR": "D:\\klogg",
                "APP_LOG_DIR": "D:\\klogg\\logs",
                "MAIN_WINDOW_TITLE_REGEX": "(?i)cilogg",
                "APP_STATE_DUMP_ARG": "--dump-state-json",
                "QT_AUTOMATION_ENV_VAR": "CILOGG_AUTOMATION",
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
                    "CILOGG_SAMPLE_LOG": str(sample),
                    "CILOGG_SMOKE_SEARCH_TEXT": "needle",
                    "MAIN_WINDOW_TITLE_REGEX": "(?i)cilogg",
                    "CILOGG_SMOKE_REQUIRE_COMPUTER_USE": "0",
                },
                clear=False,
            ):
                config = CILoggValidationConfig.from_env()
        self.assertEqual(config.sample_log, sample.resolve())
        self.assertEqual(config.search_text, "needle")
        self.assertFalse(config.require_computer_use)

    def test_filtered_wrap_config_uses_explicit_log(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            sample = Path(tmp) / "wrap.log"
            sample.write_text("Test", encoding="utf-8")
            with mock.patch.dict(
                os.environ,
                {
                    "CILOGG_FILTERED_WRAP_LOG": str(sample),
                    "CILOGG_FILTERED_WRAP_SEARCH_TEXT": "EHCI001VER|CRC",
                    "MAIN_WINDOW_TITLE_REGEX": "(?i)cilogg",
                    "CILOGG_FILTERED_WRAP_REQUIRE_COMPUTER_USE": "0",
                },
                clear=False,
            ):
                config = CILoggFilteredWrapValidationConfig.from_env()
        self.assertEqual(config.repro_log, sample.resolve())
        self.assertEqual(config.search_text, "EHCI001VER|CRC")
        self.assertFalse(config.require_computer_use)


class CILoggValidationSelectionTests(unittest.TestCase):
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

    def test_measure_filtered_wrap_gap_reports_large_empty_run(self) -> None:
        from PIL import Image

        with tempfile.TemporaryDirectory() as tmp:
            image_path = Path(tmp) / "wrap-gap.png"
            image = Image.new("RGB", (120, 80), (40, 40, 40))
            for y in range(8, 18):
                for x in range(8, 112):
                    image.putpixel((x, y), (220, 80, 80))
            image.save(image_path)

            state = {
                "objectName": "mainWindow",
                "children": [
                    {
                        "objectName": "filteredView",
                        "bounds": {"x": 0, "y": 0, "width": 120, "height": 80},
                        "children": [],
                    }
                ],
            }

            metrics = _measure_filtered_wrap_gap(image_path, state)

        self.assertGreater(metrics["max_empty_run"], 12)


if __name__ == "__main__":
    unittest.main()
