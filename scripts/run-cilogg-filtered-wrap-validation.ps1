param(
    [string]$CILoggRoot = "",
    [string]$Config = "RelWithDebInfo",
    [string]$ReproLog = "",
    [switch]$SkipUnitTests
)

$ErrorActionPreference = "Stop"

function Get-RepoRoot {
    return (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
}

$repoRoot = Get-RepoRoot
if ([string]::IsNullOrWhiteSpace($CILoggRoot)) {
    $CILoggRoot = (Resolve-Path (Join-Path $repoRoot "..\klogg")).Path
}

$python = Join-Path $repoRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $python)) {
    throw "Python virtual environment not found: $python"
}

$appDir = Join-Path $CILoggRoot "build_root\output\$Config"
$appExe = Join-Path $appDir "cilogg.exe"
if (-not (Test-Path $appExe)) {
    throw "cilogg.exe not found: $appExe"
}

if ([string]::IsNullOrWhiteSpace($ReproLog)) {
    $ReproLog = "D:\Essence_SC\kloggs\com1_115200_2026-03-24_13-31-15.log"
}
if (-not (Test-Path $ReproLog)) {
    throw "Filtered-wrap repro log not found: $ReproLog"
}

$env:APP_EXE = $appExe
$env:APP_WORKDIR = $appDir
$env:APP_LOG_DIR = $appDir
$env:APP_DUMP_DIR = $appDir
$env:MAIN_WINDOW_TITLE_REGEX = "(?i)cilogg"
$env:APP_STATE_DUMP_ARG = "--dump-state-json"
$env:QT_AUTOMATION_ENV_VAR = "CILOGG_AUTOMATION"
$env:CILOGG_FILTERED_WRAP_LOG = $ReproLog
$env:WIN_GUI_CILOGG_FILTERED_WRAP_SMOKE = "1"

if (-not $SkipUnitTests) {
    Push-Location $repoRoot
    try {
        & $python -m unittest tests.test_adapters tests.test_cilogg_validation
        if ($LASTEXITCODE -ne 0) {
            exit $LASTEXITCODE
        }

        & $python .\cilogg_filtered_wrap_validation.py
        exit $LASTEXITCODE
    }
    finally {
        Pop-Location
    }
}

Push-Location $repoRoot
try {
    & $python .\cilogg_filtered_wrap_validation.py
    exit $LASTEXITCODE
}
finally {
    Pop-Location
}
