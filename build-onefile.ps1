# PyInstaller one-file build (slower startup; single .exe to distribute)
# Run: .\build-onefile.ps1
#
# Bundle lists (hiddenimports, static datas, collect-all) are read from
# full-spectrum-development.spec via scripts\print_onefile_from_spec.py — keep in sync with the spec.

Set-Location $PSScriptRoot

Write-Host "Installing dependencies..."
python -m pip install -r requirements.txt -q
python -m pip install -r requirements-build.txt -q

if ($env:INTEGRAL_CI_BUILD -eq "1") {
    if (-not (Test-Path "assets\icon.ico")) {
        Write-Error "CI build requires committed assets\icon.ico (do not run build_icon.py in CI)."
        exit 1
    }
    Write-Host "CI build: using committed assets\icon.ico (skipping build_icon.py)."
} else {
    Write-Host "Building app icon..."
    python scripts\build_icon.py
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
}

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

if ($env:INTEGRAL_CI_BUILD -eq "1") {
    $markerDir = Join-Path $PSScriptRoot "build"
    New-Item -ItemType Directory -Force -Path $markerDir | Out-Null
    $markerPath = Join-Path $markerDir "ci_test_build.marker"
    if (-not (Test-Path $markerPath)) {
        Set-Content -Path $markerPath -Value "ci" -NoNewline
    }
    $dataArgs += @("--add-data", "$markerPath;build")
    Write-Host "CI test build: bundling ci_test_build.marker (data -> Integral-test)"
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
if ($env:INTEGRAL_CI_BUILD -eq "1") {
    Write-Host "CI build: default data folder is %APPDATA%\Integral-test\ (not production Integral)."
} else {
    Write-Host "Double-click that file to run. Data saves to:"
    Write-Host "  %APPDATA%\Integral\data.json"
}
