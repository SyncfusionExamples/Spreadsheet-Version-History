$ErrorActionPreference = "Stop"

$ProjectRoot = $PSScriptRoot
$ApplicationPath = Join-Path $ProjectRoot "app.py"
$HostPath = Join-Path `
    $ProjectRoot `
    "collaboration-host\CollaborationHost.exe"

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Starting Spreadsheet Version History" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan

if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
    throw "Python was not found in PATH."
}

if (-not (Test-Path $ApplicationPath)) {
    throw "app.py was not found."
}

if (-not (Test-Path $HostPath)) {
    throw "CollaborationHost.exe was not found."
}

Set-Location $ProjectRoot
python $ApplicationPath

if ($LASTEXITCODE -ne 0) {
    throw "The backend exited with code $LASTEXITCODE."
}
