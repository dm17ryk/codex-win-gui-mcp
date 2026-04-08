from __future__ import annotations

import json

from win_gui_core.klogg_validation import KloggValidationRunner


def main() -> int:
    result = KloggValidationRunner().run()
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
