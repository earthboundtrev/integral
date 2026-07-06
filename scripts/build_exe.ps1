$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot\..

Write-Host "Building Integral.exe ..."
python -m PyInstaller --noconfirm --clean full-spectrum-development.spec

if (Test-Path "dist\Integral\Integral.exe") {
    Write-Host "OK: dist\Integral\Integral.exe"
} elseif (Test-Path "dist\Integral.exe") {
    Write-Host "OK: dist\Integral.exe"
} else {
    Write-Error "Build failed - Integral.exe not found"
    exit 1
}
