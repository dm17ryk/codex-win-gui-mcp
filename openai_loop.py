from __future__ import annotations

import argparse
import json

from loops.computer_use import ComputerUseRunner


def main() -> int:
    parser = argparse.ArgumentParser(description="Run an OpenAI Computer Use loop against a Windows desktop target.")
    parser.add_argument("goal", help="Natural-language task for the model.")
    parser.add_argument("--window-title", default=None, help="Regex of the target window title.")
    parser.add_argument("--full-screen", action="store_true", help="Capture the whole screen instead of a single window.")
    args = parser.parse_args()

    final_response = ComputerUseRunner().run(goal=args.goal, window_title=args.window_title, full_screen=args.full_screen)
    output_text = getattr(final_response, "output_text", None)
    if output_text:
        print(output_text)
    else:
        print(json.dumps(final_response.model_dump(), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
