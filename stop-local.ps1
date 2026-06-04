$ErrorActionPreference = "SilentlyContinue"

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$pidFile = Join-Path $root ".local\uvicorn.pid"

if (Test-Path $pidFile) {
    $pidValue = Get-Content $pidFile | Select-Object -First 1
    Stop-Process -Id ([int]$pidValue) -Force
    Remove-Item $pidFile
}

$connections = Get-NetTCPConnection -LocalPort 8000
foreach ($connection in $connections) {
    Stop-Process -Id $connection.OwningProcess -Force
}
Write-Host "SSQ V6.0 stopped."
