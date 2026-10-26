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
$hiddenJson = python -c "import json; from pathlib import Path; from tests.pyinstaller_import_audit import parse_hiddenimports_from_spec; print(json.dumps(sorted(parse_hiddenimports_from_spec(Path('full-spectrum-development.spec')))))"
if ($LASTEXITCODE -ne 0) {
    Write-Error "Failed to read hiddenimports from full-spectrum-development.spec"
    exit 1
}
$hiddenList = @($hiddenJson | ConvertFrom-Json)
if ($hiddenList.Count -eq 0) {
    Write-Error "No hiddenimports found in full-spectrum-development.spec"
    exit 1
}
$hiddenImportArgs = @()
foreach ($name in $hiddenList) {
    $hiddenImportArgs += @("--hidden-import", $name)
}

python -m PyInstaller `
    --noconfirm `
    --clean `
    --onefile `
    --windowed `
    --name Integral `
    @iconArg `
    --add-data "programs;programs" `
    --add-data "assets;assets" `
    @hiddenImportArgs `
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
