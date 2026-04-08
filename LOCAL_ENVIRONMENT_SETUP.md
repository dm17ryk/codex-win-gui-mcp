# Codex app local-environment checklist

Create these actions in the Codex app **Settings -> Local environments** for your project.

## Suggested setup script (Windows)

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

If your app needs a build step, append it, for example:

```powershell
dotnet restore .\MyApp.sln
dotnet build .\MyApp.sln -c Debug
```

## Suggested project actions (Windows)

### Build Debug
```powershell
dotnet build .\MyApp.sln -c Debug
```

### Run App
```powershell
.\scripts\run-app.ps1
```

### Reset State
```powershell
.\scripts\reset-state.ps1
```

### Collect Logs
```powershell
.\scripts\collect-logs.ps1
```

### Reproduce via Computer Use
```powershell
.\.venv\Scripts\python.exe .\openai_loop.py --window-title "MyApp" "Open Settings, switch to Advanced, and report any visible error dialog."
```

## Recommended Codex prompts

- `Launch the app, create a session, wait for the window to stabilize, and inspect the UI tree before clicking anything.`
- `Reproduce the bug, assert the expected UI state, then create an artifact bundle and summarize the failure.`
- `Use click_element first; if the target isn't in UIA, capture a screenshot and use viewport-relative click_point or drag_path.`
