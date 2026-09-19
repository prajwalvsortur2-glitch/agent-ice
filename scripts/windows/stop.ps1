<#
.SYNOPSIS
    Stop the Agent ICE backend started by start.ps1 -Background.
#>

[CmdletBinding()]
param()

$ErrorActionPreference = 'Continue'
Set-StrictMode -Version Latest

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectRoot = Resolve-Path (Join-Path $ScriptDir '..\..')
$pidFile = Join-Path $ProjectRoot 'logs\backend.pid'

if (-not (Test-Path $pidFile)) {
    Write-Host "No backend.pid found - nothing to stop." -ForegroundColor Yellow
    return
}

$backendPid = Get-Content $pidFile -Raw
$backendPid = $backendPid.Trim()

if (-not $backendPid) {
    Write-Host "backend.pid is empty - removing." -ForegroundColor Yellow
    Remove-Item $pidFile -Force
    return
}

try {
    $proc = Get-Process -Id ([int]$backendPid) -ErrorAction Stop
    Write-Host "Stopping Agent ICE backend PID $backendPid..." -ForegroundColor Cyan
    Stop-Process -Id $proc.Id -Force
    Write-Host "Stopped." -ForegroundColor Green
} catch {
    Write-Host "Process $backendPid is not running." -ForegroundColor Yellow
}

Remove-Item $pidFile -Force