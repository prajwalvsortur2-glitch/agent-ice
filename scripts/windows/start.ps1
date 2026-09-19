<#
.SYNOPSIS
    Start Agent ICE backend (and optionally the frontend dev server).

.DESCRIPTION
    Activates .venv, starts uvicorn on the configured host/port, and
    optionally starts the frontend Vite dev server in a second window.

    The backend runs in the current PowerShell window so its logs are
    visible. Use -Background to detach it instead.
#>

[CmdletBinding()]
param(
    [switch]$WithFrontend,
    [switch]$Background,
    [string]$BindHost = '127.0.0.1',
    [int]$Port = 8000
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectRoot = Resolve-Path (Join-Path $ScriptDir '..\..')
Set-Location $ProjectRoot

$Activate = Join-Path $ProjectRoot '.venv\Scripts\Activate.ps1'
if (-not (Test-Path $Activate)) {
    Write-Error "Virtual environment not found. Run .\scripts\windows\setup.ps1 first."
}
& $Activate

$env:PYTHONPATH = $ProjectRoot

Write-Host ""
Write-Host "Starting Agent ICE backend on http://${BindHost}:${Port}" -ForegroundColor Cyan
Write-Host "  Docs:   http://${BindHost}:${Port}/docs"
Write-Host "  Health: http://${BindHost}:${Port}/health"
Write-Host ""

$uvicornArgs = @(
    '-m', 'uvicorn', 'app.main:app',
    '--host', $BindHost,
    '--port', "$Port"
)

if ($Background) {
    $logFile = Join-Path $ProjectRoot 'logs\backend.log'
    $logDir = Split-Path -Parent $logFile
    if (-not (Test-Path $logDir)) { New-Item -ItemType Directory -Path $logDir | Out-Null }

    Write-Host "Starting backend in background (log: $logFile)" -ForegroundColor Green
    $proc = Start-Process -FilePath 'python' -ArgumentList $uvicornArgs `
        -RedirectStandardOutput $logFile `
        -RedirectStandardError "$logFile.err" `
        -PassThru -WindowStyle Hidden

    $pidFile = Join-Path $ProjectRoot 'logs\backend.pid'
    Set-Content -Path $pidFile -Value $proc.Id
    Write-Host "Backend PID: $($proc.Id)" -ForegroundColor DarkGray
} else {
    Write-Host "Press Ctrl+C to stop the backend." -ForegroundColor Yellow
    & python @uvicornArgs
}

if ($WithFrontend) {
    if (-not (Get-Command 'npm' -ErrorAction SilentlyContinue)) {
        Write-Warning "npm not found; skipping frontend."
        return
    }
    $frontendDir = Join-Path $ProjectRoot 'frontend'
    if (-not (Test-Path (Join-Path $frontendDir 'node_modules'))) {
        Write-Warning "frontend/node_modules missing. Run .\scripts\windows\setup.ps1 first."
        return
    }
    Write-Host "Starting frontend dev server in a new window..." -ForegroundColor Cyan
    Start-Process -FilePath 'powershell' -ArgumentList @(
        '-NoExit', '-Command',
        "Set-Location '$frontendDir'; npm run dev"
    )
}