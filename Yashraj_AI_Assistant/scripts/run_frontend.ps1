<#
Run the frontend in development mode (Vite). This will run `npm install` then `npm run dev`.
This script assumes Node.js is installed and available on the PATH.
#>

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Definition
Set-Location -Path (Join-Path $scriptDir "..\frontend")

if (-Not (Test-Path "package.json")) {
    Write-Error "package.json not found in frontend folder. Ensure you're in project root."; exit 1
}

Write-Host "Installing frontend dependencies (if needed)..."
npm install

Write-Host "Starting frontend dev server..."
npm run dev
