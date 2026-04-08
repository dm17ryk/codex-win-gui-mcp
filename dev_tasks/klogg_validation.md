# Klogg Validation Workflow

## Purpose

This task guide validates the live `klogg <-> codex-win-gui-mcp` workflow across three layers:

1. semantic klogg MCP commands;
2. Qt click-style fallback interaction;
3. one bounded OpenAI computer-use debugging scenario.

The output of a successful run is a JSON summary plus session artifact bundles under `artifacts/sessions/<session_id>/`.

## Prerequisites

- Windows host.
- `klogg` built in `RelWithDebInfo` or another chosen config.
- `windeployqt` already run for the chosen `klogg.exe`.
- `codex-win-gui-mcp` virtual environment created and dependencies installed.
- `OPENAI_API_KEY` set when computer-use validation is enabled.

## Required Environment

Set these values before the live run:

- `APP_EXE`
  Example: `C:\src\klogg\build_root\output\RelWithDebInfo\klogg.exe`
- `APP_WORKDIR`
  Example: `C:\src\klogg\build_root\output\RelWithDebInfo`
- `APP_ARGS`
  Recommended: `-n -m -l -dddd`
- `APP_LOG_DIR`
  Recommended: the same directory as `APP_WORKDIR` unless you use a dedicated klogg log directory.
- `APP_DUMP_DIR`
  Recommended: the same directory as `APP_WORKDIR` unless dumps are written elsewhere.
- `MAIN_WINDOW_TITLE_REGEX`
  Recommended: `klogg`
- `APP_STATE_DUMP_ARG`
  Required: `--dump-state-json`
- `QT_AUTOMATION_ENV_VAR`
  Required: `KLOGG_AUTOMATION`
- `KLOGG_SAMPLE_LOG`
  Recommended: `C:\src\klogg\test_data\ansi_colors_example.txt`
- `KLOGG_SMOKE_REQUIRE_COMPUTER_USE`
  Use `1` for the full validation matrix.

Do not commit user-local MCP registration. Keep Codex MCP server registration in the user profile or user-local project config.

## Commands

Recommended full run from `codex-win-gui-mcp`:

```powershell
.\scripts\run-klogg-validation.ps1 -KloggRoot C:\src\klogg -Config RelWithDebInfo
```

This script:

- sets klogg-specific env values;
- runs the fast unit/regression checks;
- runs the live semantic/fallback/computer-use validation;
- prints the final JSON result.

Recommended prep from the `klogg` repo:

```powershell
.\scripts\codex\build-windows.ps1 -Config RelWithDebInfo
```

## Acceptance Criteria

The live validation is successful only if all of the following pass in one run:

- `launch_app/create_session/wait_window_stable` bind to a live klogg window;
- `dump_qt_state` returns `windowInfo`, `actions`, and `kloggState`;
- `klogg_open_log` opens the configured sample log and `klogg_get_state` reports it as active;
- `klogg_search` sets the configured search text and returns a positive match count;
- `klogg_toggle_follow` can set follow mode both on and off deterministically;
- `klogg_get_visible_range` returns both start and end bounds;
- at least one real `click_qt_object` fallback interaction succeeds against a visible instrumented control;
- the computer-use scenario returns a non-empty human-readable summary;
- `create_artifact_bundle` succeeds for the semantic phase and the computer-use phase.

## Artifact Locations

Each session writes to:

- `artifacts/sessions/<session_id>/trace.jsonl`
- `artifacts/sessions/<session_id>/screenshots/`
- `artifacts/sessions/<session_id>/bundle-*/bundle-manifest.json`

Each bundle is expected to contain:

- `trace.jsonl`
- `last-screenshot.png`
- `qt-state.json` when Qt state is available
- `uia-tree.json` when UIA capture succeeds
- `process-tree.json` when a session PID is available
- copied logs under `logs/`
- copied dumps under `dumps/`
- `event-logs.txt` when Windows event log collection succeeds

## Failure Triage

Use the bundle contents to classify the failure before changing code:

- App bug:
  semantic commands succeed but visible UI state, logs, or dumps show broken klogg behavior.
- Adapter bug:
  Qt dump is present but normalized state, action invocation, or fallback lookup is inconsistent with the raw dump.
- Session or viewport bug:
  clicks or screenshots use the wrong coordinates, window binding is unstable, or the trace shows stale HWND/PID state.
- Environment bug:
  missing env vars, missing Qt deployment, absent sample log, missing OpenAI key, or empty log/dump directories.
