# Rename dist/Integral.exe and write Integral-v{version}.exe.sha256 for release upload.
param(
    [Parameter(Mandatory = $true)][string]$AppVersion
)

$ErrorActionPreference = "Stop"
$src = "dist/Integral.exe"
if (-not (Test-Path -LiteralPath $src)) {
    Write-Error "Missing $src"
    exit 1
}

$destName = "Integral-v$AppVersion.exe"
$dest = Join-Path "dist" $destName
Copy-Item -LiteralPath $src -Destination $dest -Force

$hash = (Get-FileHash -LiteralPath $dest -Algorithm SHA256).Hash.ToLowerInvariant()
$shaPath = "$dest.sha256"
"$hash  $destName" | Set-Content -Path $shaPath -Encoding ascii -NoNewline

Write-Host "Release package: $destName"
Write-Host "SHA-256: $hash"
