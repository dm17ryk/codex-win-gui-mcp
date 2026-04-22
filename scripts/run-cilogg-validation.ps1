param(
    [string]$CILoggRoot = "",
    [string]$Config = "RelWithDebInfo",
    [string]$SampleLog = "",
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

if ([string]::IsNullOrWhiteSpace($SampleLog)) {
    $SampleLog = Join-Path $CILoggRoot "test_data\ansi_colors_example.txt"
}
if (-not (Test-Path $SampleLog)) {
    throw "Sample log not found: $SampleLog"
}

$env:APP_EXE = $appExe
$env:APP_WORKDIR = $appDir
$env:APP_LOG_DIR = $appDir
$env:APP_DUMP_DIR = $appDir
$env:MAIN_WINDOW_TITLE_REGEX = "(?i)cilogg"
$env:APP_STATE_DUMP_ARG = "--dump-state-json"
$env:QT_AUTOMATION_ENV_VAR = "CILOGG_AUTOMATION"
$env:CILOGG_SAMPLE_LOG = $SampleLog
$env:WIN_GUI_CILOGG_SMOKE = "1"

if (-not $SkipUnitTests) {
    & $python -m unittest tests.test_artifacts tests.test_adapters tests.test_service tests.test_cilogg_validation
    if ($LASTEXITCODE -ne 0) {
        exit $LASTEXITCODE
    }
}

& $python .\cilogg_validation.py
exit $LASTEXITCODE
