# Build a double-clickable Windows app (recommended — faster startup than one-file)
# Run: .\build.ps1

Set-Location $PSScriptRoot

Write-Host "Installing dependencies..."
python -m pip install -r requirements.txt -q
python -m pip install -r requirements-build.txt -q

Write-Host "Building app icon..."
python scripts\build_icon.py
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host "Building executable..."
python -m PyInstaller --noconfirm --clean full-spectrum-development.spec

if ($LASTEXITCODE -ne 0) {
    Write-Error "Build failed."
    exit 1
}

Write-Host ""
Write-Host "Done. Your app is here:"
Write-Host "  dist\Integral\Integral.exe"
Write-Host ""
Write-Host "Zip the whole Integral folder for GitHub Releases."
Write-Host "User data saves to: %APPDATA%\Integral\data.json"
