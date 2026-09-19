<#
.SYNOPSIS
    Agent ICE health check.

.DESCRIPTION
    Runs the Python healthcheck and, if a backend process is running,
    queries the /health endpoint directly.
#>

[CmdletBinding()]
param(
    [string]$BaseUrl = 'http://127.0.0.1:8000',
    [switch]$Json
)

$ErrorActionPreference = 'Continue'
Set-StrictMode -Version Latest

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectRoot = Resolve-Path (Join-Path $ScriptDir '..\..')
Set-Location $ProjectRoot

$Activate = Join-Path $ProjectRoot '.venv\Scripts\Activate.ps1'
if (Test-Path $Activate) { & $Activate }

$env:PYTHONPATH = $ProjectRoot

$pyArgs = @((Join-Path $ProjectRoot 'scripts\healthcheck.py'), '--base-url', $BaseUrl)
if ($Json) { $pyArgs += '--json' }

& python @pyArgs
$exitCode = $LASTEXITCODE

Write-Host ""
if ($exitCode -eq 0) {
    Write-Host "Overall: HEALTHY" -ForegroundColor Green
} elseif ($exitCode -eq 1) {
    Write-Host "Overall: BACKEND UNREACHABLE" -ForegroundColor Red
} elseif ($exitCode -eq 2) {
    Write-Host "Overall: DATABASE UNHEALTHY" -ForegroundColor Red
} elseif ($exitCode -eq 3) {
    Write-Host "Overall: DEGRADED (Ollama unavailable - high-risk actions will fail closed)" -ForegroundColor Yellow
}

exit $exitCode