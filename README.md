# Codex Windows GUI MCP

This repository provides a session-first Windows GUI automation harness for Codex and other MCP clients. It is built around four pieces:

- a thin MCP server in [server.py](/D:/Essence_SC/lsrc/codex-win-gui-mcp/server.py);
- a modular harness package in [win_gui_core](/D:/Essence_SC/lsrc/codex-win-gui-mcp/win_gui_core);
- Qt and CILogg adapter helpers in [adapters](/D:/Essence_SC/lsrc/codex-win-gui-mcp/adapters);
- a local Computer Use loop in [openai_loop.py](/D:/Essence_SC/lsrc/codex-win-gui-mcp/openai_loop.py) and [loops/computer_use.py](/D:/Essence_SC/lsrc/codex-win-gui-mcp/loops/computer_use.py).

## 1. Install prerequisites

```powershell
winget install Codex -s msstore
winget install --id Git.Git
winget install --id Python.Python.3.11
winget install --id Microsoft.DotNet.SDK.10
```

Optional for WebDriver-style Windows UI tests:

```powershell
.\scripts\start-winappdriver.ps1
```

## 2. Create and populate the virtual environment

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

## 3. Configure the target app

Use `.env.example` as the baseline. In practice these are the main settings:

- `APP_EXE`
- `APP_WORKDIR`
- `APP_ARGS`
- `APP_LOG_DIR`
- `APP_STATE_DIR`
- `APP_DUMP_DIR`
- `MAIN_WINDOW_TITLE_REGEX`
- `OPENAI_API_KEY`
- `OPENAI_COMPUTER_MODEL`
- `APP_STATE_DUMP_ARG`
- `QT_AUTOMATION_ENV_VAR`

Model guidance:

- `gpt-5.4` is a good default.
- `computer-use-preview` is the specialized option when the workflow is heavily vision-driven.

## 4. Wire the MCP server into Codex

Merge [user_config.toml.example](/D:/Essence_SC/lsrc/codex-win-gui-mcp/user_config.toml.example) into `%USERPROFILE%\.codex\config.toml`.

Keep Win GUI MCP registration user-local. Do not commit project-scoped Codex MCP registration for this workflow.

Adjust:

- the Python interpreter path;
- the [server.py](/D:/Essence_SC/lsrc/codex-win-gui-mcp/server.py) path;
- the app-specific environment variables.

## 5. Session-first workflow

The preferred flow is:

1. `launch_app` or an external app-start action.
2. `create_session`.
3. `wait_window_stable`.
4. `find_element` / `click_element` / adapter tools first.
5. `capture_screenshot` and `click_point` / `drag_path` only when semantics are missing.
6. `assert_*` helpers after every meaningful step.
7. `create_artifact_bundle` when you need a full debugging package.

## 6. Coordinate-space rules

- `full_screen` screenshots produce desktop-space coordinates.
- `window` and `region` screenshots produce viewport-relative coordinates.
- `click_point`, `double_click_point`, `drag_path`, and `scroll_at` translate viewport coordinates through the active session viewport before calling `pyautogui`.

This matters because screenshot-space and desktop-space are not interchangeable when the target window is not at `(0, 0)`.

## 7. Main MCP tools

The current MCP surface is session-first:

- `create_session`
- `get_session`
- `refresh_session`
- `close_session`
- `enumerate_monitors`
- `restore_window`
- `wait_window_stable`
- `capture_screenshot`
- `capture_region`
- `click_point`
- `double_click_point`
- `drag_path`
- `scroll_at`
- `type_text`
- `send_hotkey`
- `find_element`
- `wait_for_element`
- `wait_for_element_gone`
- `assert_element`
- `click_element`
- `double_click_element`
- `right_click_element`
- `drag_element_to_point`
- `drag_element_to_element`
- `assert_window_title`
- `assert_status_text`
- `assert_log_contains`
- `wait_process_idle`
- `create_artifact_bundle`
- `list_artifacts`
- `collect_event_logs`
- `collect_dumps`
- `get_process_tree`
- `dump_qt_state`
- `find_qt_object`
- `click_qt_object`
- `invoke_qt_action`
- `set_qt_value`
- `toggle_qt_control`
- `cilogg_open_log`
- `cilogg_search`
- `cilogg_get_state`
- `cilogg_get_active_tab`
- `cilogg_toggle_follow`
- `cilogg_get_visible_range`

## 8. Qt and CILogg instrumentation

This repo now assumes deep instrumentation is allowed for Qt targets.

Recommended target-app support:

- stable `objectName` values on important widgets and `QAction`s;
- `accessibleName` on icon-only or ambiguous controls;
- optional `accessibleDescription`;
- an automation mode such as `CILOGG_AUTOMATION=1`;
- a state dump endpoint, with `--dump-state-json <path>` used by default in this repo.

Useful CILogg state fields:

- `activeFile`
- `activeTabTitle`
- `cursorLine`
- `cursorColumn`
- `visibleLineStart`
- `visibleLineEnd`
- `searchText`
- `matchCount`
- `followMode`
- `scratchPad`
- `encoding`
- `parserMode`

## 9. Artifact and trace layout

Each session writes to `artifacts/sessions/<session_id>/`.

Typical contents:

- `trace.jsonl`
- `screenshots/*.png`
- `bundle-*/bundle-manifest.json`
- copied logs
- copied dumps
- UI tree snapshots
- optional Qt state dumps

## 10. Local environment actions

See [LOCAL_ENVIRONMENT_SETUP.md](/D:/Essence_SC/lsrc/codex-win-gui-mcp/LOCAL_ENVIRONMENT_SETUP.md).

## 11. CILogg validation workflow

For the full `CILogg <-> codex-win-gui-mcp` validation matrix, use:

```powershell
.\scripts\run-cilogg-validation.ps1 -CILoggRoot C:\src\klogg -Config RelWithDebInfo
```

This runs:

- the fast unit/regression checks for adapters, service fallback, and validation scaffolding;
- the live semantic CILogg smoke flow;
- one bounded OpenAI computer-use debugging scenario.

Detailed prerequisites, env values, artifact expectations, and failure triage are in [dev_tasks/cilogg_validation.md](/D:/Essence_SC/lsrc/codex-win-gui-mcp/dev_tasks/cilogg_validation.md).

## 12. Direct Computer Use loop

```powershell
.\.venv\Scripts\python.exe .\openai_loop.py --window-title "MyApp" "Open the Settings window, switch to Advanced, and tell me whether the Save button becomes disabled."
```

Use `--full-screen` only when the task genuinely spans the desktop rather than one pinned target window.

## 13. Safety notes

- Run destructive scenarios in an isolated Windows VM or disposable user profile.
- Prefer semantic/UIA interactions over blind coordinate clicks.
- Review destructive steps with a human in the loop.
- `pyautogui` fail-safe is enabled; moving the cursor to the top-left corner interrupts execution.
