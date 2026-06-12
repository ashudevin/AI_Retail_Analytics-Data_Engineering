#Requires -Version 5.1
param(
    [switch]$InstallRequirements
)

$ErrorActionPreference = "Stop"

$ProjectRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
$VenvPath = Join-Path $ProjectRoot ".venv"
$VenvPython = Join-Path $VenvPath "Scripts\python.exe"

if (-not (Test-Path $VenvPython)) {
    Write-Host "Creating virtual environment at $VenvPath ..."
    & python -m venv $VenvPath
    if ($LASTEXITCODE -ne 0) {
        throw "Failed to create virtual environment. Is Python installed?"
    }
}

if ($InstallRequirements) {
    $Requirements = Join-Path $ProjectRoot "requirements.txt"
    Write-Host "Installing dependencies from requirements.txt ..."
    & $VenvPython -m pip install --upgrade pip
    if ($LASTEXITCODE -ne 0) {
        throw "Failed to upgrade pip."
    }
    & $VenvPython -m pip install -r $Requirements
    if ($LASTEXITCODE -ne 0) {
        throw "Failed to install requirements."
    }
}

Write-Output $VenvPython
