# codex-win-gui-mcp review, LLD, and README proposal

## 1. What is already good

- Thin FastMCP layer in `server.py` and nearly all platform logic isolated in `win_gui_core.py`.
- Clean split between:
  - MCP tools (`server.py`)
  - desktop harness (`win_gui_core.py`)
  - local Computer Use loop (`openai_loop.py`)
  - operational scripts (`scripts/*.ps1`)
- The current tool surface is already enough for a basic "launch -> wait -> inspect UIA -> click/drag -> collect logs" workflow.

## 2. Biggest concrete issues to fix first

### P0 — coordinate-space bug in `openai_loop.py`
When `--full-screen` is **not** used, the screenshot is captured for one target window, but actions are executed directly in desktop coordinates through `pyautogui`.

That means the model sees coordinates in **window image space**, while the harness clicks in **screen space**. This will misclick unless the window happens to be at `(0, 0)`.

### P0 — missing viewport metadata
`capture_screenshot()` should return the full viewport metadata used to produce the image:
- `left`
- `top`
- `width`
- `height`
- `hwnd`
- `pid`
- `coord_space`
- `scale_x`
- `scale_y`
- `capture_mode`

Without this, the model loop cannot safely translate image-space coordinates back to the real desktop.

### P0 — no session object
The current design repeatedly resolves windows by title regex. For stable GUI automation, introduce a session object that pins:
- PID
- HWND
- title regex
- viewport
- last screenshot
- target monitor / DPI info

### P1 — no assertions / waits / state oracles
The current repo has actions, but not enough validation. Add:
- `wait_for_element`
- `wait_for_window_text`
- `wait_for_process_idle`
- `assert_element`
- `assert_window_title`
- `assert_status_text`
- `assert_log_contains`

### P1 — limited artifact collection
Add a single artifact bundle operation that can collect:
- step screenshots
- latest logs
- app state dump
- crash dumps / minidumps (if available)
- machine-readable session trace JSONL

### P1 — README/config drift
There are a few mismatches that should be fixed immediately:
- README installs Python 3.14 but creates a 3.11 venv.
- `user_config.toml.example` still points at `codex-win-gui-starter` paths instead of this repo.
- `run-app.ps1` supports `APP_ARGS`, but README does not document it.

## 3. Recommended architecture after cleanup

### Layer A — MCP API surface
Keep `server.py` thin.
Only tool definitions and argument docs should live here.

### Layer B — core harness package
Split `win_gui_core.py` into smaller modules:

- `core/session.py`
  - `TargetSession`
  - `Viewport`
  - `SessionTraceEvent`
- `core/windows.py`
  - list/focus/move/restore window
  - monitor enumeration
  - DPI / geometry helpers
- `core/screenshots.py`
  - capture full screen / window / region
  - viewport metadata
  - artifact storage pathing
- `core/input.py`
  - click / double click / drag / hotkeys / text / scroll
  - coordinate translation helpers
- `core/uia.py`
  - resolve window
  - resolve element
  - serialize UIA tree
  - wait/assert helpers
- `core/logs.py`
  - tail newest log
  - collect logs
  - preserve relative paths
- `core/artifacts.py`
  - create session bundle
  - manifest JSON
- `core/errors.py`
  - typed errors for focus failure / element not found / coordinate translation failure

### Layer C — Computer Use loop
Move the loop into `loops/computer_use.py`.
It should:
- keep a persistent target session
- capture viewport metadata on each screenshot
- translate action coordinates from image space to screen space
- record every model action and execution result
- optionally keep a rolling screenshot history

### Layer D — adapters
Add app-specific adapters, starting with Qt and klogg:

- `adapters/qt_adapter.py`
  - objectName-oriented operations
  - menu/action helpers
  - status bar helpers
  - optional Qt state dump integration
- `adapters/klogg_adapter.py`
  - launch sample file
  - read active tab metadata
  - read search state
  - dump current file / line / selection state

## 4. Detailed LLD

## 4.1 Session model

```python
@dataclass
class Viewport:
    mode: Literal["full_screen", "window", "region"]
    left: int
    top: int
    width: int
    height: int
    hwnd: int | None
    pid: int | None
    title: str | None
    monitor_index: int | None
    scale_x: float = 1.0
    scale_y: float = 1.0
    captured_at: float = 0.0

@dataclass
class TargetSession:
    session_id: str
    title_regex: str | None
    pid: int | None
    hwnd: int | None
    viewport: Viewport | None
    last_screenshot_path: str | None
    last_model_response_id: str | None
```

## 4.2 Screenshot contract

Every screenshot call should return:

```json
{
  "ok": true,
  "path": "...png",
  "image_base64": "...",
  "viewport": {
    "mode": "window",
    "left": 120,
    "top": 80,
    "width": 1440,
    "height": 900,
    "hwnd": 197324,
    "pid": 15088,
    "title": "klogg - sample.log"
  }
}
```

## 4.3 Coordinate translation

Add one function and use it everywhere:

```python
def viewport_to_screen(x: int, y: int, viewport: Viewport) -> tuple[int, int]:
    return (
        int(viewport.left + x * viewport.scale_x),
        int(viewport.top + y * viewport.scale_y),
    )
```

The Computer Use loop must never click raw model coordinates unless the screenshot came from the full desktop with origin `(0, 0)`.

## 4.4 MCP tool additions

### Reliability / state
- `create_session(title_regex: str | None = None, pid: int | None = None) -> dict`
- `get_session() -> dict`
- `refresh_session() -> dict`
- `wait_window_stable(timeout_sec: float = 5.0) -> dict`
- `restore_window(hwnd: int) -> dict`
- `enumerate_monitors() -> dict`

### UIA / assertions
- `wait_for_element(...) -> dict`
- `wait_for_element_gone(...) -> dict`
- `assert_element(...) -> dict`
- `right_click_element(...) -> dict`
- `double_click_element(...) -> dict`
- `drag_element_to_point(...) -> dict`
- `drag_element_to_element(...) -> dict`

### Screenshots / artifacts
- `capture_region(x, y, width, height, absolute=True, hwnd=None) -> dict`
- `create_artifact_bundle(reason: str | None = None) -> dict`
- `list_artifacts() -> dict`

### Logs / diagnostics
- `collect_event_logs(minutes: int = 60) -> dict`
- `collect_dumps(output_dir: str | None = None) -> dict`
- `get_process_tree(pid: int | None = None) -> dict`
- `wait_process_idle(pid: int | None = None, cpu_threshold: float = 2.0) -> dict`

## 4.5 Test plan

Create `tests/` and add pure unit tests for:
- coordinate remapping for window screenshots
- path normalization for drag actions
- key normalization
- newest-log resolution
- log collection preserving file names and relative structure
- session persistence

Add smoke tests guarded behind Windows markers for:
- launch / close app
- wait_main_window
- capture_screenshot with viewport metadata
- click_xy window-relative translation

## 4.6 Logging / trace format

Write one JSONL event per step:

```json
{"ts": 1712500000.123, "type": "screenshot", "path": "...png", "viewport": {...}}
{"ts": 1712500001.456, "type": "model_actions", "actions": [...]}
{"ts": 1712500001.789, "type": "action_result", "ok": true, "action": {...}}
{"ts": 1712500002.100, "type": "tail_log", "path": "...log"}
```

This trace becomes the backbone for debugging the debugger.

## 5. Qt / klogg-specific recommendations

The MCP can get much closer to human-grade GUI testing if the target Qt app exposes stable semantic handles.

### Add to the Qt app
- `objectName` for every important widget and `QAction`
- `accessibleName` for icon-only or ambiguous controls
- `accessibleDescription` where the action meaning is not obvious
- deterministic automation mode, e.g. `KLOGG_AUTOMATION=1`
- optional `--dump-state-json` CLI or a local debug socket for introspection

### For custom widgets
If a widget is heavily custom-drawn, add accessibility support or a debug-only state endpoint.
This is much more reliable than forcing the agent to infer everything from pixels.

### Good klogg-specific state oracles
- active file path
- active tab title
- cursor line / column
- visible line range
- current search string
- match count
- follow/tail mode
- scratch pad state
- current encoding / parser mode

## 6. What the README should explain explicitly

The current README is good as a starter, but for real adoption it should also document:

1. **How the coordinate system works**
   - full-screen screenshot => screen coordinates
   - window screenshot => window-relative coordinates that must be translated

2. **The preferred action order**
   - object/UIA first
   - coordinate fallback second
   - logs and assertions after each meaningful step

3. **How to instrument the target app**
   - objectName / accessibleName / automation mode / state dump

4. **What to put in project-scoped `.codex/config.toml`**
   - `cwd`
   - `enabled_tools`
   - app env variables

5. **How to run safely**
   - isolated VM / disposable Windows user / approval policy

6. **Known limitations**
   - custom-drawn controls
   - multi-monitor / DPI issues
   - focus stealing
   - screenshot-space vs screen-space transforms

## 7. Recommended README rewrite

A drop-in rewrite is provided separately in `codex-win-gui-mcp_README_patch.diff`.

## 8. Suggested implementation order

### Milestone 1 — correctness
- fix viewport coordinate mapping
- return viewport metadata from screenshots
- add session object
- fix README/config mismatches

### Milestone 2 — observability
- session trace JSONL
- artifact bundles
- wait/assert tools
- preserve relative paths in log collection

### Milestone 3 — Windows robustness
- monitor enumeration
- restore/minimize/maximize support
- better focus handling
- idle/stability waits

### Milestone 4 — Qt / klogg depth
- Qt adapter
- klogg adapter
- target app instrumentation docs
- app-specific state dump

### Milestone 5 — tests and CI
- unit tests
- Windows smoke tests
- lint / format / compile checks

