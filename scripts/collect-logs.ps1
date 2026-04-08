$ErrorActionPreference = 'Stop'

if (-not $env:APP_LOG_DIR) {
    throw 'APP_LOG_DIR is not set.'
}

if (-not (Test-Path $env:APP_LOG_DIR)) {
    throw "APP_LOG_DIR does not exist: $env:APP_LOG_DIR"
}

$timestamp = Get-Date -Format 'yyyyMMdd-HHmmss'
$outDir = Join-Path (Join-Path (Get-Location) 'artifacts') "logs-$timestamp"
New-Item -ItemType Directory -Path $outDir -Force | Out-Null

Get-ChildItem -LiteralPath $env:APP_LOG_DIR -File -Recurse |
    ForEach-Object {
        $relative = Resolve-Path -LiteralPath $_.FullName | ForEach-Object {
            $_.Path.Substring((Resolve-Path -LiteralPath $env:APP_LOG_DIR).Path.Length).TrimStart('\')
        }
        $destination = Join-Path $outDir $relative
        $destinationDir = Split-Path -Parent $destination
        New-Item -ItemType Directory -Path $destinationDir -Force | Out-Null
        Copy-Item -LiteralPath $_.FullName -Destination $destination -Force
    }

Write-Host "Logs copied to $outDir"
