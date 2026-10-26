# PyInstaller one-file build (slower startup; single .exe to distribute)
# Run: .\build-onefile.ps1
#
# Bundle lists (hiddenimports, static datas, collect-all) are read from
# full-spectrum-development.spec via scripts\print_onefile_from_spec.py — keep in sync with the spec.

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

function Get-SpecBundleLines {
    param([Parameter(Mandatory = $true)][string]$Command)
    $output = & python scripts\print_onefile_from_spec.py $Command 2>&1
    if ($LASTEXITCODE -ne 0) {
        Write-Error "Failed to read '$Command' from full-spectrum-development.spec (see scripts\print_onefile_from_spec.py)."
        exit 1
    }
    return @($output | ForEach-Object { "$_".Trim() } | Where-Object { $_ })
}

Write-Host "Building single-file executable..."
$hiddenList = Get-SpecBundleLines hiddenimports
if ($hiddenList.Count -eq 0) {
    Write-Error "No hiddenimports found in full-spectrum-development.spec"
    exit 1
}
$hiddenImportArgs = @()
foreach ($name in $hiddenList) {
    $hiddenImportArgs += @("--hidden-import", $name)
}

$dataLines = Get-SpecBundleLines add-data
if ($dataLines.Count -eq 0) {
    Write-Error "No static datas found in full-spectrum-development.spec"
    exit 1
}
$dataArgs = @()
foreach ($line in $dataLines) {
    $pair = $line -split '\|', 2
    if ($pair.Count -ne 2) {
        Write-Error "Invalid add-data line from spec: $line"
        exit 1
    }
    $dataArgs += @("--add-data", "$($pair[0]);$($pair[1])")
}

$collectList = Get-SpecBundleLines collect-all
$collectArgs = @()
foreach ($package in $collectList) {
    $collectArgs += @("--collect-all", $package)
}

python -m PyInstaller `
    --noconfirm `
    --clean `
    --onefile `
    --windowed `
    --name Integral `
    @iconArg `
    @dataArgs `
    @hiddenImportArgs `
    @collectArgs `
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
