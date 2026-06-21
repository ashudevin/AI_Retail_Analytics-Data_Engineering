#Requires -Version 5.1
$ErrorActionPreference = "Stop"

$ProjectRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
Set-Location $ProjectRoot

$VenvPython = & "$PSScriptRoot\ensure_venv.ps1" -InstallRequirements | Select-Object -Last 1
Write-Host "Virtual environment ready: $VenvPython"
Write-Host "Activate with: .\.venv\Scripts\Activate.ps1"
Write-Host "Run ingestion with: .\scripts\ingest.ps1"
Write-Host "Run silver transform with: .\scripts\silver.ps1"
Write-Host "Run gold transform with: .\scripts\gold.ps1"
Write-Host "Run AI insights with: .\scripts\ai_insights.ps1"
Write-Host "Run export dashboard JSON with: .\scripts\export_json.ps1"
Write-Host "Start Docker platform with: .\scripts\docker-up.ps1 -Build"
