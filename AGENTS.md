# Repository Guidelines

## Project Structure & Module Organization
This repository is a small Python MCP server for Windows GUI automation. Core modules live at the repo root: `server.py` exposes FastMCP tools, `win_gui_core.py` contains the desktop harness, and `openai_loop.py` runs a local OpenAI-driven control loop. Operational docs are in `README.md` and `LOCAL_ENVIRONMENT_SETUP.md`. Helper scripts for app launch, state reset, WinAppDriver startup, and log collection live in `scripts/`. Example environment and Codex config files are `.env.example` and `user_config.toml.example`.

## Build, Test, and Development Commands
Use PowerShell from the repository root.

- `py -3.11 -m venv .venv` creates the local virtual environment.
- `.\.venv\Scripts\python.exe -m pip install -r requirements.txt` installs FastMCP, OpenAI, and Windows automation dependencies.
- `.\.venv\Scripts\python.exe .\server.py` starts the MCP server locally.
- `.\.venv\Scripts\python.exe .\openai_loop.py --window-title "MyApp" "Open Settings"` runs a direct computer-use repro loop.
- `.\scripts\run-app.ps1`, `.\scripts\reset-state.ps1`, and `.\scripts\collect-logs.ps1` support local debugging workflows.

## Coding Style & Naming Conventions
Follow the existing Python style: 4-space indentation, type hints where practical, `snake_case` for functions and variables, and short docstrings on MCP tool functions. Keep modules focused: tool definitions in `server.py`, platform logic in `win_gui_core.py`, orchestration in `openai_loop.py`. Match existing naming like `wait_main_window` and `capture_screenshot`. Prefer small, explicit helpers over deeply nested control flow.

## Testing Guidelines
There is no committed automated test suite yet, so every change needs a manual smoke test. At minimum, verify imports with `.\.venv\Scripts\python.exe -m py_compile server.py win_gui_core.py openai_loop.py` and exercise the changed flow against a local Windows app. If you add automated tests, place them under `tests/` and use `test_*.py` names.

## Commit & Pull Request Guidelines
The current history uses short imperative subjects (`initial commit`). Keep commits focused and similarly concise, for example `add hwnd filter to screenshot capture`. PRs should include a brief summary, any required environment-variable or script changes, manual verification steps, and screenshots or collected logs when the UI behavior changed.

## Security & Configuration Tips
Do not commit real app paths, `.env` values, API keys, or local Codex config. Keep new settings documented in `.env.example` or `user_config.toml.example` so contributors can reproduce the environment safely.
