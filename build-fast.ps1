# Fast iterative build — keeps PyInstaller cache (no --clean). Use for dev; use build.ps1 for releases.
# Run: .\build-fast.ps1

Set-Location $PSScriptRoot

if (-not (Test-Path "assets\icon.ico")) {
    Write-Host "Building app icon..."
    python scripts\build_icon.py
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
}

Write-Host "Fast build (incremental, no pip, no --clean)..."
python -m PyInstaller --noconfirm full-spectrum-development.spec

if ($LASTEXITCODE -ne 0) {
    Write-Error "Build failed."
    exit 1
}

Write-Host ""
Write-Host "Done. Your app is here:"
Write-Host "  dist\Integral\Integral.exe"
Write-Host ""
Write-Host "For a clean release build, run: .\build.ps1"
