from __future__ import annotations

import os
import sys
import unittest

from win_gui_core.cilogg_validation import CILoggValidationRunner


@unittest.skipUnless(sys.platform == "win32", "Windows-only smoke tests")
@unittest.skipUnless(
    os.environ.get("WIN_GUI_CILOGG_SMOKE") == "1",
    "Set WIN_GUI_CILOGG_SMOKE=1 to run the live CILogg validation matrix.",
)
class CILoggLiveSmokeTests(unittest.TestCase):
    def test_full_validation_matrix(self) -> None:
        result = CILoggValidationRunner().run()
        self.assertTrue(result["ok"])
        self.assertIn("semantic_bundle", result)
        self.assertIn("computer_use_bundle", result)


if __name__ == "__main__":
    unittest.main()
