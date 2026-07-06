$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot\..

Write-Host "Building PersonalDevelopmentTracker.exe ..."
python -m PyInstaller build\personal_dev_tracker.spec --noconfirm

if (Test-Path "dist\PersonalDevelopmentTracker.exe") {
    Write-Host "OK: dist\PersonalDevelopmentTracker.exe"
} else {
    Write-Error "Build failed - EXE not found"
    exit 1
}
