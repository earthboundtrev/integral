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
Write-Host "Smoke: using isolated INTEGRAL_DATA_DIR (temp)."
Write-Host "Smoke: launching exe for $Seconds seconds..."

$proc = Start-Process -FilePath $ExePath -PassThru -WorkingDirectory (Split-Path -Parent $ExePath)
try {
    Start-Sleep -Seconds $Seconds
    if ($proc.HasExited) {
        Write-Error "Integral.exe exited early (exit code $($proc.ExitCode)) after $Seconds s smoke window."
        exit 1
    }

    if (-not (Test-Path -LiteralPath $smokeDir)) {
        Write-Error "Smoke data folder is missing after launch."
        exit 1
    }
    $dataJson = Join-Path $smokeDir "data.json"
    if (-not (Test-Path -LiteralPath $dataJson)) {
        Write-Error "Smoke data folder has no data.json (app did not persist test data at startup)."
        exit 1
    }
    $names = @(Get-ChildItem -LiteralPath $smokeDir -File | ForEach-Object { $_.Name })
    Write-Host "Smoke OK: $($names.Count) file(s) in test data dir ($($names -join ', '))."
    Write-Host "Smoke OK: process still running after $Seconds seconds."
}
finally {
    if ($proc -and -not $proc.HasExited) {
        Stop-Process -Id $proc.Id -Force -ErrorAction SilentlyContinue
    }
    if (Test-Path -LiteralPath $smokeDir) {
        Remove-Item -LiteralPath $smokeDir -Recurse -Force -ErrorAction SilentlyContinue
        Write-Host "Smoke: removed test data dir."
    }
}
