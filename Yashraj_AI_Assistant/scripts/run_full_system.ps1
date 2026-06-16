<#
Start backend and frontend in separate PowerShell windows.
This script launches two PowerShell processes that run `run_backend.ps1` and `run_frontend.ps1`.
#>

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Definition
$backendScript = Join-Path $scriptDir "run_backend.ps1"
$frontendScript = Join-Path $scriptDir "run_frontend.ps1"

if (-Not (Test-Path $backendScript)) { Write-Error "$backendScript not found"; exit 1 }
if (-Not (Test-Path $frontendScript)) { Write-Error "$frontendScript not found"; exit 1 }

Start-Process -FilePath "powershell" -ArgumentList "-NoProfile -NoExit -ExecutionPolicy Bypass -File `"$backendScript`""
Start-Process -FilePath "powershell" -ArgumentList "-NoProfile -NoExit -ExecutionPolicy Bypass -File `"$frontendScript`""

Write-Host "Launched backend and frontend in separate PowerShell windows."
