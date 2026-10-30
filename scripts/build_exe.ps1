# Build the standalone Windows executable (onedir).
#
#   powershell -ExecutionPolicy Bypass -File scripts/build_exe.ps1
#
# Output: dist/cq-hecs/cq-hecs.exe plus _internal/. Zip the folder for a
# release asset. One-file mode is intentionally not used: a 518 MB one-file
# build failed to extract bcrypt at runtime on the reference Windows machine.

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

python -m PyInstaller `
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

Write-Host "Built $Exe"
Write-Host "Zip dist\cq-hecs\ for the release asset."
