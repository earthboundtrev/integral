# Smoke-test a built Integral.exe on Windows CI (GUI session required).
param(
    [Parameter(Mandatory = $true)][string]$ExePath,
    [int]$Seconds = 20
)

$ErrorActionPreference = "Stop"
if (-not (Test-Path -LiteralPath $ExePath)) {
    Write-Error "Missing exe: $ExePath"
    exit 1
}

$smokeDir = Join-Path $env:TEMP "integral-ci-smoke-$PID"
New-Item -ItemType Directory -Force -Path $smokeDir | Out-Null
$env:INTEGRAL_DATA_DIR = $smokeDir
Write-Host "Smoke: INTEGRAL_DATA_DIR=$smokeDir"
Write-Host "Smoke: launching $ExePath for $Seconds seconds..."

$proc = Start-Process -FilePath $ExePath -PassThru -WorkingDirectory (Split-Path -Parent $ExePath)
try {
    Start-Sleep -Seconds $Seconds
    if ($proc.HasExited) {
        Write-Error "Integral.exe exited early (exit code $($proc.ExitCode)) after $Seconds s smoke window."
        exit 1
    }
    Write-Host "Smoke OK: process still running after $Seconds seconds."
}
finally {
    if (-not $proc.HasExited) {
        Stop-Process -Id $proc.Id -Force -ErrorAction SilentlyContinue
    }
}
