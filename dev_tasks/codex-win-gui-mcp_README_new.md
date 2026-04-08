# codex-win-gui-mcp

Windows GUI automation MCP for Codex, with a local Computer Use loop and a practical path toward reliable GUI debugging for desktop applications such as Qt apps.

## What this repo gives you

This repo gives you a working baseline for Codex-driven GUI automation on Windows:

- a FastMCP server that exposes window, mouse, keyboard, screenshot, log, and UIA tools;
- a `DesktopHarness` that performs the actual desktop operations;
- a local OpenAI Computer Use loop for screenshot-driven interaction;
- PowerShell scripts you can wire into Codex app Local environments.

## Current architecture

- `server.py` — MCP tool definitions only
- `win_gui_core.py` — Windows desktop harness
- `openai_loop.py` — local Computer Use loop
- `scripts/` — run/reset/log collection helpers
- `user_config.toml.example` — sample Codex config
- `LOCAL_ENVIRONMENT_SETUP.md` — sample Local environment setup
- `AGENTS.md` — repository guidance for Codex

## Quick start

### 1) Install prerequisites

```powershell
winget install Codex -s msstore
winget install --id Git.Git
winget install --id Python.Python.3.11
```

Optional:

```powershell
winget install --id Microsoft.DotNet.SDK.10
```

Optional if you want WebDriver-style Windows UI tests:

- install Windows Application Driver (WinAppDriver)
- run `scripts\start-winappdriver.ps1`

### 2) Create and populate the virtual environment

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

### 3) Set environment variables

You can either:

- set them in your shell from `.env.example`, or
- put them into your Codex MCP config under `[mcp_servers.win_gui.env]`

Required in practice:

- `APP_EXE`
- `APP_WORKDIR`
- `APP_LOG_DIR`
- `MAIN_WINDOW_TITLE_REGEX`

Recommended:

- `APP_STATE_DIR`
- `APP_ARGS`
- `OPENAI_API_KEY`
- `OPENAI_COMPUTER_MODEL`

### 4) Wire the MCP server into Codex

Merge `user_config.toml.example` into `%USERPROFILE%\.codex\config.toml` or a project-scoped `.codex\config.toml`.

Recommended example:

```toml
model = "gpt-5.4"
model_provider = "openai"
approval_policy = "on-request"
sandbox_mode = "workspace-write"

[windows]
sandbox = "elevated"
sandbox_private_desktop = false

[mcp_servers.win_gui]
command = 'C:\dev\codex-win-gui-mcp\.venv\Scripts\python.exe'
args = ['C:\dev\codex-win-gui-mcp\server.py']
cwd = 'C:\dev\codex-win-gui-mcp'
startup_timeout_sec = 20
tool_timeout_sec = 120
enabled = true
required = false
enabled_tools = [
  'launch_app',
  'close_app',
  'restart_app',
  'list_windows',
  'wait_main_window',
  'focus_window',
  'move_window',
  'capture_screenshot',
  'click_xy',
  'double_click_xy',
  'drag_mouse',
  'move_mouse',
  'scroll',
  'type_text',
  'send_hotkey',
  'find_element',
  'click_element',
  'get_uia_tree',
  'tail_log',
  'collect_recent_logs',
]

[mcp_servers.win_gui.env]
APP_EXE = 'C:\work\MyApp\bin\Debug\MyApp.exe'
APP_WORKDIR = 'C:\work\MyApp'
APP_LOG_DIR = 'C:\work\MyApp\logs'
APP_STATE_DIR = 'C:\Users\<you>\AppData\Local\MyApp'
MAIN_WINDOW_TITLE_REGEX = 'MyApp'
```

## Local environments in Codex app

Create Local environment setup/actions from `LOCAL_ENVIRONMENT_SETUP.md`.

Recommended project actions:

- Build Debug
- Run App
- Reset State
- Collect Logs
- Reproduce via Computer Use

## How to use this MCP effectively

Use this order of operations:

1. **Prefer semantic interaction first**
   - `get_uia_tree`
   - `find_element`
   - `click_element`

2. **Use coordinates only as a fallback**
   - `capture_screenshot`
   - `click_xy`
   - `drag_mouse`

3. **After each meaningful step, verify state**
   - `tail_log`
   - UIA tree refresh
   - window title / status bar / visible controls

4. **Reset app state before each repro**
   - `scripts\reset-state.ps1`

5. **Collect artifacts immediately after failure**
   - screenshots
   - latest logs
   - state dump / dumps if available

## Coordinate systems: very important

This is the most common source of flaky GUI automation.

### Full-screen screenshots
If your screenshot covers the full desktop, model coordinates can be treated as screen coordinates.

### Window screenshots
If your screenshot only covers one target window, model coordinates are relative to the window image, not the screen.

That means your harness must translate:

```text
screen_x = window_left + image_x
screen_y = window_top  + image_y
```

If your harness crops to a window but executes clicks as raw desktop coordinates, it will misclick whenever the window is not anchored at the top-left corner.

## How to instrument target apps for best results

This MCP becomes much more reliable if the target application exposes stable semantic identifiers.

### For Qt apps
Add:

- `objectName` for important widgets and `QAction`s
- `accessibleName` for icon-only controls
- `accessibleDescription` where the meaning is ambiguous
- an automation mode such as `KLOGG_AUTOMATION=1`
- an optional `--dump-state-json` or debug socket for internal state

### For custom-drawn widgets
If a control is custom rendered, screenshot-only automation will always be more fragile. Add either:

- accessibility support for that widget, or
- a debug-only state/introspection endpoint

## klogg / Qt recommendations

For klogg-like Qt apps, expose at least:

- active file path
- active tab title
- search text
- match count
- cursor line / column
- visible line range
- follow/tail mode
- current encoding / parser mode

These state oracles make the agent far closer to a human tester because it can verify outcomes instead of only clicking and guessing.

## Recommended Codex prompts

- `Launch the app, inspect the UI tree, and find the Settings tab before clicking anything.`
- `Reproduce the bug, then tail the latest log and summarize the failure.`
- `Use click_element first; if the target is not visible in UIA, fall back to screenshot-driven clicks.`
- `Reset state, launch the app with APP_ARGS, reproduce the issue, and collect artifacts.`

## Known limitations

- Custom-drawn controls may not appear well in UIA.
- Screenshot-driven automation is sensitive to DPI, scaling, and window placement.
- Focus-stealing and minimized windows can break input replay.
- If you disable private desktop mode for compatibility, treat the environment as more exposed.

## Safe operating guidelines

Because this MCP can click and type on a real Windows desktop:

- prefer an isolated VM or disposable Windows user profile;
- keep Codex approvals enabled for destructive or high-impact tasks;
- avoid running against your daily-driver desktop session when testing unstable automation;
- keep an explicit allowlist of apps and actions the agent is supposed to use.

## Developer recommendations for this repo

### Code organization
This starter repo is already clean, but the next step is to split `win_gui_core.py` into:

- `session.py`
- `windows.py`
- `screenshots.py`
- `input.py`
- `uia.py`
- `logs.py`
- `artifacts.py`

### Features to add next
Highest-value additions:

- viewport metadata on screenshots
- coordinate translation for window-cropped screenshots
- session object pinned to PID/HWND
- wait/assert tools
- artifact bundles
- better Qt / app-specific adapters

### Tests to add
At minimum:

- coordinate translation tests
- action normalization tests
- log path resolution tests
- Windows smoke tests for launch / wait / screenshot / click flows

## Troubleshooting

### PowerShell execution policy
If PowerShell blocks local scripts, try a less restrictive execution policy after checking your security requirements.

### Wrong click positions
Check:

- whether you captured a full-screen or window-only screenshot
- current DPI / display scaling
- whether the target window moved between screenshots

### Window not found
Check:

- `MAIN_WINDOW_TITLE_REGEX`
- whether the window is minimized
- whether multiple windows share similar titles

