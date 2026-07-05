# PyInstaller one-file build (slower startup; single .exe to distribute)
# Run: .\build-onefile.ps1

Set-Location $PSScriptRoot

Write-Host "Installing dependencies..."
python -m pip install -r requirements.txt -q
python -m pip install -r requirements-build.txt -q

Write-Host "Building app icon..."
python scripts\build_icon.py
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

$iconArg = @()
if (Test-Path "assets\icon.ico") {
    $iconArg = @("--icon", "assets\icon.ico")
}

Write-Host "Building single-file executable..."
python -m PyInstaller `
    --noconfirm `
    --clean `
    --onefile `
    --windowed `
    --name Integral `
    @iconArg `
    --add-data "programs;programs" `
    --add-data "assets;assets" `
    --hidden-import activity_grid `
    --hidden-import paths `
    --hidden-import theme `
    --hidden-import graphs `
    --hidden-import fitness_graphs `
    --hidden-import fitness.engine `
    --hidden-import fitness.ui `
    --hidden-import insights.engine `
    --hidden-import insights.playbooks `
    --collect-all matplotlib `
    personal_dev_tracker.py

if ($LASTEXITCODE -ne 0) {
    Write-Error "Build failed."
    exit 1
}

Write-Host ""
Write-Host "Done. Your app is here:"
Write-Host "  dist\Integral.exe"
Write-Host ""
Write-Host "Double-click that file to run. Data saves to:"
Write-Host "  %APPDATA%\Integral\data.json"
