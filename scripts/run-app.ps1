param(
    [string[]]$ArgsList
)

$ErrorActionPreference = 'Stop'

if (-not $env:APP_EXE) {
    throw 'APP_EXE is not set.'
}

$workingDir = if ($env:APP_WORKDIR) { $env:APP_WORKDIR } else { Split-Path -Parent $env:APP_EXE }
$argsToUse = @()
if ($env:APP_ARGS) {
    $argsToUse += $env:APP_ARGS -split ' '
}
if ($ArgsList) {
    $argsToUse += $ArgsList
}

Write-Host "Launching $env:APP_EXE"
Start-Process -FilePath $env:APP_EXE -WorkingDirectory $workingDir -ArgumentList $argsToUse | Out-Null
