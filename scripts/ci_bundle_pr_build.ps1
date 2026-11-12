# Write dist/BUILD.txt + Run-Test.cmd and emit artifact bundle name (GITHUB_OUTPUT).
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

$repoRoot = Split-Path -Parent $PSScriptRoot
$pathsFile = Join-Path $repoRoot "paths.py"
$pathsText = Get-Content -LiteralPath $pathsFile -Raw
if ($pathsText -notmatch 'APP_VERSION\s*=\s*"([^"]+)"') {
    Write-Error "Could not parse APP_VERSION from paths.py"
    exit 1
}
$appVersion = $Matches[1]

$built = (Get-Date).ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ss'Z'")
$lines = [System.Collections.Generic.List[string]]::new()
$lines.Add("app_version: $appVersion")
$lines.Add("commit: $env:GITHUB_SHA")
if ($env:INTEGRAL_PR_HEAD_SHA) {
    $lines.Add("pr_head_commit: $env:INTEGRAL_PR_HEAD_SHA")
}
$lines.Add("built_utc: $built")
$lines.Add("data_folder_default: %APPDATA%\Integral-test")
$lines.Add("run_test_cmd: sets INTEGRAL_DATA_DIR=%TEMP%\Integral-RunTest")

$dist = Join-Path $repoRoot "dist"
New-Item -ItemType Directory -Force -Path $dist | Out-Null
$lines | Set-Content -Path (Join-Path $dist "BUILD.txt") -Encoding utf8
Copy-Item -Path (Join-Path $PSScriptRoot "Run-Test.cmd") -Destination (Join-Path $dist "Run-Test.cmd")

$pr = $env:INTEGRAL_PR_NUMBER
if (-not $pr) { $pr = "manual" }
if ($env:INTEGRAL_PR_HEAD_SHA) {
    $short = $env:INTEGRAL_PR_HEAD_SHA.Substring(0, 8)
} else {
    $short = $env:GITHUB_SHA.Substring(0, 8)
}
$name = "integral-pr${pr}-${short}"
if ($env:GITHUB_OUTPUT) {
    "name=$name" | Out-File -FilePath $env:GITHUB_OUTPUT -Append -Encoding utf8
}
Write-Host "Artifact bundle: $name (app_version $appVersion)"
