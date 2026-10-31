# Build the standalone Windows executable (onedir).
#
#   powershell -ExecutionPolicy Bypass -File scripts/build_exe.ps1
#
# Output: dist/cq-hecs/cq-hecs.exe plus _internal/. Zip the folder for a
# release asset. One-file mode is intentionally not used: a 518 MB one-file
# build failed to extract bcrypt at runtime on the reference Windows machine.

param(
  # Interpreter that has the runtime dependencies and PyInstaller installed.
  [string]$Python = "python"
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

& $Python -m PyInstaller `
  --noconfirm `
  --clean `
  --onedir `
  --name cq-hecs `
  --add-data "cqhecs\studio\static;cqhecs\studio\static" `
  --add-data "cqhecs\studio\data;cqhecs\studio\data" `
  --collect-submodules qiskit `
  --collect-data qiskit `
  --collect-submodules qiskit_aer `
  --collect-data qiskit_aer `
  "cqhecs\cli.py"

if ($LASTEXITCODE -ne 0) { throw "PyInstaller failed with exit code $LASTEXITCODE" }

$Exe = ".\dist\cq-hecs\cq-hecs.exe"
& $Exe version
if ($LASTEXITCODE -ne 0) { throw "standalone binary failed its version smoke test" }
& $Exe sat solve "benchmarks\sat\pigeonhole_6_5.cnf" | Out-Host
if ($LASTEXITCODE -ne 0) { throw "standalone binary failed its SAT smoke test" }
& $Exe sat solve "benchmarks\sat\pigeonhole_6_5.cnf" --engine omniwave | Out-Host
if ($LASTEXITCODE -ne 0) { throw "standalone binary failed its OMNIWAVE smoke test" }
& $Exe --format json run name:bell --shots 64 | Out-Null
if ($LASTEXITCODE -ne 0) { throw "standalone binary failed its circuit smoke test" }
& $Exe --format json run name:bell --device iqm_garnet --shots 64 | Out-Null
if ($LASTEXITCODE -ne 0) { throw "standalone binary failed its device-profile smoke test" }

# The Studio must start from outside the repository on the packaged snapshot.
$Port = 8765
$Studio = Start-Process -FilePath (Resolve-Path $Exe) -ArgumentList "studio", "--no-browser", "--port", $Port `
  -WorkingDirectory $env:TEMP -PassThru -WindowStyle Hidden
try {
  $ok = $false
  for ($i = 0; $i -lt 60 -and -not $ok; $i++) {
    Start-Sleep -Seconds 1
    try {
      $health = Invoke-RestMethod "http://127.0.0.1:$Port/api/health" -TimeoutSec 5
      $ok = [bool]$health.ok
    } catch { }
  }
  if (-not $ok) { throw "standalone binary failed its Studio smoke test" }
} finally {
  # The PyInstaller bootloader runs the app in a child process; end the whole
  # tree, or the child keeps cq-hecs.exe locked and the zip step fails.
  cmd.exe /c "taskkill /PID $($Studio.Id) /T /F >nul 2>&1"
  $Studio.WaitForExit(30000) | Out-Null
  Start-Sleep -Seconds 2
}

$Version = (& $Python scripts\version.py).Trim()
$Zip = ".\dist\cqhecs-$Version-windows-x64.zip"
if (Test-Path $Zip) { Remove-Item $Zip }
# Python's zipfile writes portable forward-slash entry names; Windows
# PowerShell 5.1 Compress-Archive writes backslashes.
& $Python -c "import shutil; shutil.make_archive(r'$($Zip -replace '\.zip$','')', 'zip', 'dist', 'cq-hecs')"
if ($LASTEXITCODE -ne 0) { throw "zipping dist\cq-hecs failed" }
Write-Host "Built $Exe"
Write-Host "Release asset: $Zip"
Write-Host ("SHA-256: " + (Get-FileHash $Zip -Algorithm SHA256).Hash.ToLower())
