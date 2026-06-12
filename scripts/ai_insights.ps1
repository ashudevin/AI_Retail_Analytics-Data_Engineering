#Requires -Version 5.1
$ErrorActionPreference = "Stop"

$ProjectRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
Set-Location $ProjectRoot

$VenvPython = & "$PSScriptRoot\ensure_venv.ps1" | Select-Object -Last 1
& $VenvPython -m src.ai.run_ai_insights @args
exit $LASTEXITCODE
