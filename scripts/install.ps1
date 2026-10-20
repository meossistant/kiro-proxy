# PowerShell automated installer for kiro-proxy on Windows
$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoDir = Resolve-Path "$scriptDir\.."

Write-Host "=== Installing kiro-proxy for Windows ===" -ForegroundColor Cyan
Write-Host "Repository path: $repoDir"

# 1. Check or install uv
if (!(Get-Command "uv" -ErrorAction SilentlyContinue)) {
    Write-Host ">> 'uv' not found. Installing uv via Astral installer..." -ForegroundColor Yellow
    powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
    $env:Path = [System.Environment]::GetEnvironmentVariable("Path","User") + ";" + [System.Environment]::GetEnvironmentVariable("Path","Machine")
}

Write-Host ">> Using uv: $(uv --version)" -ForegroundColor Green

# 2. Check kiro-cli
if (!(Get-Command "kiro-cli" -ErrorAction SilentlyContinue)) {
    Write-Host ">> [WARNING] 'kiro-cli' not found in PATH." -ForegroundColor Yellow
    Write-Host "   Please install Kiro CLI from https://kiro.dev/downloads/ or check your installation path."
} else {
    Write-Host ">> kiro-cli found: $(kiro-cli --version 2>&1 | Select-Object -First 1)" -ForegroundColor Green
    $whoami = kiro-cli whoami 2>&1 | Out-String
    if ($whoami -match "Logged in") {
        Write-Host ">> kiro-cli authentication: OK" -ForegroundColor Green
    } else {
        Write-Host ">> [NOTICE] kiro-cli is not logged in. Run 'kiro-cli login --use-device-flow' to authenticate." -ForegroundColor Yellow
    }
}

# 3. Sync dependencies
Write-Host ">> Syncing dependencies with uv..." -ForegroundColor Cyan
Set-Location $repoDir
uv sync

# 4. Create global command wrapper in ~/.local/bin/kiro-proxy.cmd
$binDir = "$env:USERPROFILE\.local\bin"
if (!(Test-Path $binDir)) {
    New-Item -ItemType Directory -Path $binDir -Force | Out-Null
}

$cmdPath = "$binDir\kiro-proxy.cmd"
$cmdContent = "@echo off`r`ncd /d `"$repoDir`"`r`nuv run kiro-proxy %*"
Set-Content -Path $cmdPath -Value $cmdContent -Encoding ASCII
Write-Host ">> Created global launcher at: $cmdPath" -ForegroundColor Green

# 5. Add binDir to User PATH if not present
$userPath = [Environment]::GetEnvironmentVariable("Path", "User")
if ($userPath -notlike "*$binDir*") {
    [Environment]::SetEnvironmentVariable("Path", "$userPath;$binDir", "User")
    $env:Path += ";$binDir"
    Write-Host ">> Added $binDir to User PATH." -ForegroundColor Green
}

Write-Host "`n=== Installation complete! ===" -ForegroundColor Cyan
Write-Host "You can now run 'kiro-proxy' from any Command Prompt or PowerShell window."
Write-Host "Start proxy: kiro-proxy"
Write-Host "Health check: curl http://localhost:8000/health"
