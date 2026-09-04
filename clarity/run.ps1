# Clarity — start the engine and the UI.
#   .\run.ps1          serve the built UI from the API on :8000
#   .\run.ps1 -Dev     run the Vite dev server on :5173 alongside the API
param([switch]$Dev)

$root = $PSScriptRoot
$npmCommand = Get-Command npm.cmd -ErrorAction SilentlyContinue
$npmPath = if ($npmCommand) { $npmCommand.Source } else { 'C:\Program Files\nodejs\npm.cmd' }
if (-not (Test-Path $npmPath)) {
    throw "Node.js/npm is not available. Install Node.js, reopen PowerShell, and run this script again."
}
$nodeDirectory = Split-Path $npmPath
if ($env:Path -notlike "*$nodeDirectory*") {
    $env:Path = "$nodeDirectory;$env:Path"
}

if ($Dev) {
    Start-Process powershell -ArgumentList "-NoExit","-Command","Set-Location '$root\backend'; python -m clarity.api" -WindowStyle Hidden
    Set-Location "$root\frontend"
    if (-not (Test-Path node_modules)) { & $npmPath install }
    & $npmPath run dev
} else {
    Set-Location "$root\frontend"
    if (-not (Test-Path node_modules)) { & $npmPath install }
    & $npmPath run build
    Set-Location "$root\backend"
    Write-Host "Clarity on http://127.0.0.1:8000"
    python -m clarity.api
}
