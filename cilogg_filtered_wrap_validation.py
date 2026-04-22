from __future__ import annotations

import json

from win_gui_core.cilogg_validation import CILoggFilteredWrapValidationRunner


def main() -> int:
    result = CILoggFilteredWrapValidationRunner().run()
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
