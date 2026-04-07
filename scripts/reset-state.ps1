$ErrorActionPreference = 'Stop'

if (-not $env:APP_STATE_DIR) {
    Write-Warning 'APP_STATE_DIR is not set. Nothing to reset.'
    exit 0
}

$targets = @(
    (Join-Path $env:APP_STATE_DIR 'Cache'),
    (Join-Path $env:APP_STATE_DIR 'Temp'),
    (Join-Path $env:APP_STATE_DIR 'Session')
)

foreach ($path in $targets) {
    if (Test-Path $path) {
        Write-Host "Removing $path"
        Remove-Item -LiteralPath $path -Recurse -Force -ErrorAction SilentlyContinue
    }
}

if ($env:APP_LOG_DIR -and (Test-Path $env:APP_LOG_DIR)) {
    Get-ChildItem -LiteralPath $env:APP_LOG_DIR -File -ErrorAction SilentlyContinue |
        Remove-Item -Force -ErrorAction SilentlyContinue
}

Write-Host 'State reset completed.'
