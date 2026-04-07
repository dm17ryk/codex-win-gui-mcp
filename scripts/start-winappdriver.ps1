$ErrorActionPreference = 'Stop'

$defaultPath = 'C:\Program Files (x86)\Windows Application Driver\WinAppDriver.exe'
$pathToExe = if ($env:WINAPPDRIVER_EXE) { $env:WINAPPDRIVER_EXE } else { $defaultPath }

if (-not (Test-Path $pathToExe)) {
    throw "WinAppDriver.exe not found: $pathToExe"
}

Start-Process -FilePath $pathToExe | Out-Null
Write-Host 'WinAppDriver started.'
