from __future__ import annotations

import os
import sys
import unittest

from win_gui_core.cilogg_validation import CILoggFilteredWrapValidationRunner


@unittest.skipUnless(sys.platform == "win32", "Windows-only smoke tests")
@unittest.skipUnless(
    os.environ.get("WIN_GUI_CILOGG_FILTERED_WRAP_SMOKE") == "1",
    "Set WIN_GUI_CILOGG_FILTERED_WRAP_SMOKE=1 to run the live filtered-wrap validation.",
)
class CILoggFilteredWrapLiveTests(unittest.TestCase):
    def test_filtered_wrap_validation(self) -> None:
        result = CILoggFilteredWrapValidationRunner().run()
        self.assertTrue(result["ok"])
        self.assertIn("bug_bundle", result)


if __name__ == "__main__":
    unittest.main()
