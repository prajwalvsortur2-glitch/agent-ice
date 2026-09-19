<#
.SYNOPSIS
    Bootstrap Agent ICE on Windows 11.

.DESCRIPTION
    Creates a Python virtual environment, installs backend dependencies,
    installs frontend dependencies, copies .env.example to .env (if absent),
    seeds the database, and pulls the Ollama model if Ollama is present.

    Safe to re-run. Existing .env and existing .venv are preserved.

.NOTES
    Requires PowerShell 5.1+ (Windows 11 default) or PowerShell 7+.
#>

[CmdletBinding()]
param(
    [switch]$SkipFrontend,
    [switch]$SkipOllama,
    [switch]$Force
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

# --- Locate project root -----------------------------------------------------
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectRoot = Resolve-Path (Join-Path $ScriptDir '..\..')
Set-Location $ProjectRoot

Write-Host ""
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "  Agent ICE - Windows 11 Setup" -ForegroundColor Cyan
Write-Host "  Project root: $ProjectRoot" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host ""

function Test-Command {
    param([string]$Name)
    return [bool](Get-Command $Name -ErrorAction SilentlyContinue)
}

# --- 1. Python ---------------------------------------------------------------
if (-not (Test-Command 'python')) {
    Write-Error "python is not on PATH. Install Python 3.11+ from https://www.python.org/downloads/windows/ and re-run."
}
$pyVersion = (& python --version 2>&1).ToString()
Write-Host "[1/6] Python found: $pyVersion" -ForegroundColor Green

# --- 2. Virtual environment --------------------------------------------------
$VenvPath = Join-Path $ProjectRoot '.venv'
if ($Force -and (Test-Path $VenvPath)) {
    Write-Host "[2/6] Removing existing .venv (Force)" -ForegroundColor Yellow
    Remove-Item -Recurse -Force $VenvPath
}
if (-not (Test-Path $VenvPath)) {
    Write-Host "[2/6] Creating virtual environment .venv" -ForegroundColor Green
    & python -m venv .venv
} else {
    Write-Host "[2/6] Reusing existing .venv" -ForegroundColor Green
}

$Activate = Join-Path $VenvPath 'Scripts\Activate.ps1'
if (-not (Test-Path $Activate)) {
    Write-Error "Virtual environment activation script not found: $Activate"
}
& $Activate
Write-Host "      Activated: $Activate" -ForegroundColor DarkGray

# --- 3. Backend dependencies -------------------------------------------------
Write-Host "[3/6] Installing backend dependencies" -ForegroundColor Green
& python -m pip install --upgrade pip | Out-Null
& pip install -r (Join-Path $ProjectRoot 'requirements.txt')

# --- 4. .env -----------------------------------------------------------------
$EnvExample = Join-Path $ProjectRoot '.env.example'
$EnvFile = Join-Path $ProjectRoot '.env'
if (-not (Test-Path $EnvFile)) {
    if (-not (Test-Path $EnvExample)) {
        Write-Error ".env.example not found at $EnvExample"
    }
    Copy-Item $EnvExample $EnvFile
    Write-Host "[4/6] Created .env from .env.example" -ForegroundColor Green

    # Generate a strong random RECEIPT_SECRET and substitute it into .env.
    $secret = & python -c "import secrets; print(secrets.token_urlsafe(48))"
    $contents = Get-Content $EnvFile -Raw
    $contents = $contents -replace 'RECEIPT_SECRET=.*', "RECEIPT_SECRET=$secret"
    Set-Content -Path $EnvFile -Value $contents -NoNewline
    Write-Host "      Generated a random RECEIPT_SECRET" -ForegroundColor DarkGray
} else {
    Write-Host "[4/6] Reusing existing .env" -ForegroundColor Green
}

# --- 5. Seed database --------------------------------------------------------
Write-Host "[5/6] Seeding database" -ForegroundColor Green
$env:PYTHONPATH = $ProjectRoot
& python (Join-Path $ProjectRoot 'scripts\seed_data.py') --wipe

# --- 6. Frontend + Ollama ----------------------------------------------------
if (-not $SkipFrontend) {
    if (Test-Command 'npm') {
        Write-Host "[6/6a] Installing frontend dependencies" -ForegroundColor Green
        Push-Location (Join-Path $ProjectRoot 'frontend')
        try {
            & npm install
        } finally {
            Pop-Location
        }
    } else {
        Write-Host "[6/6a] npm not found - skipping frontend install" -ForegroundColor Yellow
        Write-Host "       Install Node.js 20+ from https://nodejs.org/ and re-run with -SkipOllama" -ForegroundColor Yellow
    }
} else {
    Write-Host "[6/6a] Frontend install skipped (-SkipFrontend)" -ForegroundColor DarkGray
}

if (-not $SkipOllama) {
    if (Test-Command 'ollama') {
        Write-Host "[6/6b] Checking Ollama model qwen2.5:7b" -ForegroundColor Green
        $models = (& ollama list) 2>$null
        if ($models -match 'qwen2\.5:7b') {
            Write-Host "       qwen2.5:7b already installed" -ForegroundColor DarkGray
        } else {
            Write-Host "       Pulling qwen2.5:7b (this may take several minutes)..." -ForegroundColor Yellow
            & ollama pull qwen2.5:7b
        }
    } else {
        Write-Host "[6/6b] ollama not found - skipping model pull" -ForegroundColor Yellow
        Write-Host "       Install Ollama from https://ollama.com/download and run: ollama pull qwen2.5:7b" -ForegroundColor Yellow
    }
} else {
    Write-Host "[6/6b] Ollama setup skipped (-SkipOllama)" -ForegroundColor DarkGray
}

Write-Host ""
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "  Setup complete." -ForegroundColor Green
Write-Host "  Next: .\scripts\windows\start.ps1" -ForegroundColor Green
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host ""