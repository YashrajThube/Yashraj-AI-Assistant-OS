<#
Activate the project's virtual environment and run the FastAPI backend locally.
This script assumes the repository layout is the project root containing `.venv` and `backend/`.
Do NOT modify credentials.json, token.json, or .env in this script.
#>

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Definition
$venvActivate = Join-Path $scriptDir "..\.venv\Scripts\Activate.ps1"
if (Test-Path $venvActivate) {
    . $venvActivate
} else {
    Write-Error ".venv Activate.ps1 not found at $venvActivate. Activate your venv manually.";
    exit 1
}

# Switch to backend folder and run uvicorn
Set-Location -Path (Join-Path $scriptDir "..\backend")

$env:API_HOST = '127.0.0.1'
$env:API_PORT = '5000'

Write-Host "Starting backend on http://$($env:API_HOST):$($env:API_PORT)"
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 5000
