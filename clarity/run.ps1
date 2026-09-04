# Clarity — start the engine and the UI.
#   .\run.ps1          serve the built UI from the API on :8000
#   .\run.ps1 -Dev     run the Vite dev server on :5173 alongside the API
param([switch]$Dev)

$root = $PSScriptRoot

if ($Dev) {
    Start-Process powershell -ArgumentList "-NoExit","-Command","Set-Location '$root\backend'; python -m clarity.api"
    Set-Location "$root\frontend"
    if (-not (Test-Path node_modules)) { npm install }
    npm run dev
} else {
    Set-Location "$root\frontend"
    if (-not (Test-Path node_modules)) { npm install }
    npm run build
    Set-Location "$root\backend"
    Write-Host "Clarity on http://127.0.0.1:8000"
    python -m clarity.api
}
