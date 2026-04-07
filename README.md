# Codex Windows GUI starter kit

This starter kit gives you a **practical baseline** for GUI debugging on Windows:

- an MCP server that exposes window, mouse, keyboard, screenshot, log, and UIA tools;
- a `win_gui_core.py` harness that performs the actual desktop work;
- an `openai_loop.py` script that runs a local Computer Use loop against one window or the whole desktop;
- PowerShell scripts you can wire into Codex app Local environments.

## 1. Install prerequisites

```powershell
winget install Codex -s msstore
winget install --id Git.Git
winget install --id Python.Python.3.14
winget install --id Microsoft.DotNet.SDK.10
```

If you need a different Python or .NET version, change the package ids.

Optional if you want WebDriver-style Windows UI tests:

- install Windows Application Driver (WinAppDriver);
- then run `scripts\start-winappdriver.ps1`.

## 2. Create and populate the virtual environment

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

## 3. Set environment variables

Either:

- copy `.env.example` into your shell/session and fill it in; or
- put the app-specific variables into your Codex MCP config.

Required in practice:

- `APP_EXE`
- `APP_WORKDIR`
- `APP_LOG_DIR`
- `MAIN_WINDOW_TITLE_REGEX`

Recommended:

- `APP_STATE_DIR`
- `OPENAI_API_KEY`
- `OPENAI_COMPUTER_MODEL`

## 4. Wire the MCP server into Codex

Merge `user_config.toml.example` into **`%USERPROFILE%\.codex\config.toml`** or into a project-scoped **`.codex\config.toml`**.

Then adjust these values:

- the Python interpreter path in `[mcp_servers.win_gui]`;
- the `server.py` path;
- the app-specific environment variables.

## 5. Start the MCP server by opening Codex

Once Codex sees the `win_gui` MCP server, it can call tools such as:

- `launch_app`
- `wait_main_window`
- `get_uia_tree`
- `click_element`
- `click_xy`
- `drag_mouse`
- `capture_screenshot`
- `tail_log`
- `collect_recent_logs`

## 6. Create Local environment actions in the Codex app

See `LOCAL_ENVIRONMENT_SETUP.md`.

The recommended project actions are:

- Build Debug
- Run App
- Reset State
- Collect Logs
- Reproduce via Computer Use

## 7. Run a direct Computer Use loop

This is useful even outside Codex MCP, for quick prototyping.

```powershell
.\.venv\Scripts\python.exe .\openai_loop.py --window-title "MyApp" "Open the Settings window, switch to Advanced, and tell me whether the Save button becomes disabled."
```

Use `--full-screen` if your workflow spans multiple windows or menus.

## 8. How to drive the app reliably

Use this order of operations:

1. Prefer `get_uia_tree` and `click_element`.
2. If the control is custom-drawn or missing from accessibility, use `capture_screenshot` and `click_xy`/`drag_mouse`.
3. After every meaningful step, inspect the latest log via `tail_log`.
4. When you can, reset the app state before each repro.

## 9. Notes

- `sandbox_private_desktop = false` is intentional here, because many desktop debugging scenarios need the default interactive desktop rather than a private sandbox desktop.
- If your app uses custom tabs, canvases, OpenGL, DirectX, or owner-drawn widgets, expect to use screenshot-driven clicks and drags more often.
- `pyautogui` fail-safe is enabled. Moving the mouse to the top-left corner can interrupt execution.

## 10. First things to customize

Usually you only need to edit:

- `APP_EXE`
- `APP_WORKDIR`
- `APP_LOG_DIR`
- `APP_STATE_DIR`
- `MAIN_WINDOW_TITLE_REGEX`
- the build command in `LOCAL_ENVIRONMENT_SETUP.md`

After that, you can start asking Codex for workflows like:

- "Launch the app, dump the UIA tree, and find the Settings tab."
- "Reproduce the bug, then collect the latest logs and summarize the failure."
- "Try element-based interaction first, then fall back to screenshot-based drag for the tab strip."
