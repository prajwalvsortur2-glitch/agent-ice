<#
.SYNOPSIS
    Reset Agent ICE to a clean, seeded state.

.DESCRIPTION
    Drops and recreates the database schema, clears tool state, and
    reseeds the demo session. Fixture files under data/fixtures/ are
    never touched.
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

& python (Join-Path $ProjectRoot 'scripts\reset.py')
exit $LASTEXITCODE