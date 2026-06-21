#Requires -Version 5.1
<#
.SYNOPSIS
    Start the full AI-Powered Retail Analytics Docker platform (Phase 7).

.EXAMPLE
    .\scripts\docker-up.ps1
    .\scripts\docker-up.ps1 -Build
    .\scripts\docker-up.ps1 -Down
#>
param(
    [switch]$Build,
    [switch]$Down,
    [switch]$Logs
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
Set-Location $ProjectRoot

if (-not (Test-Path ".env")) {
    Write-Host "WARNING: .env not found. Copy .env.example to .env and set GEMINI_API_KEY."
    if (Test-Path ".env.example") {
        Copy-Item ".env.example" ".env"
        Write-Host "Created .env from .env.example — edit GEMINI_API_KEY before running AI tasks."
    }
}

if ($Down) {
    docker compose down
    exit $LASTEXITCODE
}

if ($Logs) {
    docker compose logs -f
    exit $LASTEXITCODE
}

$composeArgs = @("compose", "up", "-d")
if ($Build) { $composeArgs += "--build" }

Write-Host ""
Write-Host "============================================================"
Write-Host " AI-Powered Retail Analytics — Docker Platform"
Write-Host "============================================================"
Write-Host " Dashboard : http://localhost:3000"
Write-Host " Airflow UI: http://localhost:8080  (airflow / airflow)"
Write-Host "============================================================"
Write-Host ""

docker @composeArgs
exit $LASTEXITCODE
