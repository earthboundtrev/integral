# Validate a v* release tag against APP_VERSION in paths.py and origin/main reachability.
# Run only on tag push builds. Tag and ref values come from the workflow env (never inline ${{ }} here).
param()

$ErrorActionPreference = "Stop"

$tag = $env:INTEGRAL_TAG_NAME
if (-not $tag) {
    Write-Error "INTEGRAL_TAG_NAME is not set."
    exit 1
}

$strictPattern = '^v\d+(?:\.\d+)*(?:-[A-Za-z0-9.]+)?$'
if ($tag -notmatch $strictPattern) {
    Write-Error "Tag '$tag' does not match the required pattern (v + dotted version + optional -suffix)."
    exit 1
}

$pathsText = Get-Content -Path paths.py -Raw -Encoding UTF8
if ($pathsText -notmatch 'APP_VERSION\s*=\s*"([^"]+)"') {
    Write-Error "Could not parse APP_VERSION from paths.py."
    exit 1
}
$appVersion = $Matches[1]

$tagVersion = $tag.Substring(1)
if ($tagVersion -ne $appVersion) {
    Write-Error "Release tag/version mismatch: tag '$tag' (version '$tagVersion') does not match paths.py APP_VERSION '$appVersion'. Install, build, and release are skipped."
    exit 1
}

Write-Host "Release tag OK: $tag matches APP_VERSION $appVersion"

git fetch origin main --prune
$reachable = $true
git merge-base --is-ancestor HEAD origin/main
if ($LASTEXITCODE -ne 0) {
    $reachable = $false
}
if (-not $reachable) {
    Write-Error "Tagged commit is not reachable from origin/main; release build aborted."
    exit 1
}

Write-Host "Tagged commit is reachable from origin/main."

$prerelease = "false"
if ($appVersion -match '-') {
    $prerelease = "true"
}

"integral_version=$appVersion" >> $env:GITHUB_OUTPUT
"integral_prerelease=$prerelease" >> $env:GITHUB_OUTPUT
"integral_asset_exe=Integral-v$appVersion.exe" >> $env:GITHUB_OUTPUT
"integral_asset_sha=Integral-v$appVersion.exe.sha256" >> $env:GITHUB_OUTPUT
