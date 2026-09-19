<#
.SYNOPSIS
    Run the deterministic Agent ICE demo.

.DESCRIPTION
    Executes the three-scenario demo against the local backend. The demo
    is safe to run repeatedly; it resets state first.
#>

[CmdletBinding()]
param()

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
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "  Agent ICE - Attack Demonstration" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host ""

& python (Join-Path $ProjectRoot 'scripts\run_demo.py')
$exitCode = $LASTEXITCODE

Write-Host ""
if ($exitCode -eq 0) {
    Write-Host "Demo completed successfully." -ForegroundColor Green
} else {
    Write-Host "Demo exited with code $exitCode" -ForegroundColor Red
}
exit $exitCode