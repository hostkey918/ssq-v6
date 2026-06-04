$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$backend = Join-Path $root "backend"
$python = Join-Path $root ".venv\Scripts\python.exe"
$logDir = Join-Path $root ".local"
$outLog = Join-Path $logDir "uvicorn.out.log"
$errLog = Join-Path $logDir "uvicorn.err.log"
$pidFile = Join-Path $logDir "uvicorn.pid"

if (!(Test-Path $python)) {
    python -m venv (Join-Path $root ".venv")
    & $python -m pip install -r (Join-Path $backend "requirements.txt")
}

if (!(Test-Path (Join-Path $backend "static\index.html"))) {
    Push-Location (Join-Path $root "frontend")
    npm.cmd install
    npm.cmd run build
    Pop-Location
}

New-Item -ItemType Directory -Force -Path $logDir | Out-Null

$existing = Get-NetTCPConnection -LocalPort 8000 -ErrorAction SilentlyContinue
if ($existing) {
    Write-Host "Port 8000 is already in use. Open http://localhost:8000 or run .\stop-local.ps1 first."
    exit 0
}

$command = "`$env:DATABASE_URL='sqlite:///$($root.Replace('\', '/'))/ssq.db'; `$env:SCHEDULER_ENABLED='false'; & '$python' -m uvicorn app.main:app --host 127.0.0.1 --port 8000"
$process = Start-Process powershell `
    -ArgumentList "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", $command `
    -WorkingDirectory $backend `
    -WindowStyle Hidden `
    -RedirectStandardOutput $outLog `
    -RedirectStandardError $errLog `
    -PassThru

Start-Sleep -Seconds 2
$listener = Get-NetTCPConnection -LocalPort 8000 -ErrorAction SilentlyContinue | Select-Object -First 1
if ($listener) {
    $listener.OwningProcess | Set-Content $pidFile
} else {
    $process.Id | Set-Content $pidFile
}
Write-Host "SSQ V6.0 started: http://localhost:8000"
Write-Host "Logs: $outLog / $errLog"
