$ErrorActionPreference = "Stop"

# Add uv and pnpm installation directories to PATH
$env:PATH += ";$env:USERPROFILE\.local\bin;$env:APPDATA\npm"

function Test-CommandExists {
  param([string]$CommandName)

  return $null -ne (Get-Command $CommandName -ErrorAction SilentlyContinue)
}

if (-not (Test-CommandExists "uv")) {
  Write-Error "Missing required command: uv. Ensure uv is installed or available on PATH."
}

if (-not (Test-CommandExists "pnpm")) {
  Write-Error "Missing required command: pnpm. Ensure pnpm is installed or available on PATH."
}

$repoRoot = Split-Path -Parent $MyInvocation.MyCommand.Path

# Start Backend and Frontend in separate PowerShell windows
Start-Process powershell -ArgumentList "-NoExit", "-Command", "`$env:PATH += ';$env:USERPROFILE\.local\bin;$env:APPDATA\npm'; Set-Location '$repoRoot\backend'; uv run python src/agent.py dev"
Start-Process powershell -ArgumentList "-NoExit", "-Command", "`$env:PATH += ';$env:USERPROFILE\.local\bin;$env:APPDATA\npm'; Set-Location '$repoRoot\frontend'; pnpm dev"

Write-Host "Successfully launched Backend and Frontend in separate PowerShell windows!" -ForegroundColor Green
Write-Host "Open http://localhost:3000 in your browser when both terminals are ready." -ForegroundColor Cyan
