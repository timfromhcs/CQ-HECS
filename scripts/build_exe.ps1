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
& $Exe --format json run name:bell --shots 64 | Out-Null
if ($LASTEXITCODE -ne 0) { throw "standalone binary failed its circuit smoke test" }

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
  Stop-Process -Id $Studio.Id -Force -ErrorAction SilentlyContinue
}

$Version = (& $Python scripts\version.py).Trim()
$Zip = ".\dist\cqhecs-$Version-windows-x64.zip"
if (Test-Path $Zip) { Remove-Item $Zip }
Compress-Archive -Path ".\dist\cq-hecs" -DestinationPath $Zip
Write-Host "Built $Exe"
Write-Host "Release asset: $Zip"
Write-Host ("SHA-256: " + (Get-FileHash $Zip -Algorithm SHA256).Hash.ToLower())
