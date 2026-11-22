# Build the Windows application folder (PyInstaller ONEDIR, not a single-file app).
#
#   powershell -ExecutionPolicy Bypass -File scripts/build_exe.ps1
#   powershell -ExecutionPolicy Bypass -File scripts/build_exe.ps1 -OutDir C:\tmp\cqhecs-out -WorkDir C:\tmp\cqhecs-work
#
# Output: <OutDir>\cq-hecs\cq-hecs.exe plus _internal\, and the deterministic archive
# <OutDir>\cqhecs-<version>-windows-x64.zip. The zip is a folder of files: it must be
# extracted before use. One-file mode is intentionally not used: a 518 MB one-file build
# failed to extract bcrypt at runtime on the reference Windows machine.
#
# The smoke test runs scripts/package_smoke.py against a COPY of the folder in a temporary
# directory outside the repository, with PYTHONPATH removed. It is not a clean-machine test.

param(
  # Interpreter that has the runtime dependencies and PyInstaller installed. Use a CLEAN
  # virtual environment (numpy, qiskit, optional qiskit-aer, pyinstaller): a general
  # environment drags unrelated packages into the bundle.
  [string]$Python = "python",
  # Where the app folder and archive go. Default keeps the historical dist\ location.
  [string]$OutDir = "",
  # PyInstaller work and spec directories (own names so parallel builds cannot collide).
  [string]$WorkDir = "",
  [switch]$SkipSmoke
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

if (-not $OutDir) { $OutDir = Join-Path $Root "dist" }
if (-not $WorkDir) { $WorkDir = Join-Path $Root "build\pyinstaller" }
New-Item -ItemType Directory -Force -Path $OutDir, $WorkDir | Out-Null
$OutDir = (Resolve-Path $OutDir).Path
$WorkDir = (Resolve-Path $WorkDir).Path

# qiskit-aer is optional (only `cq-hecs verify` uses it): bundle it only if present.
$AerArgs = @()
& $Python -c "import qiskit_aer" 2>$null
if ($LASTEXITCODE -eq 0) {
  $AerArgs = @("--collect-submodules", "qiskit_aer", "--collect-data", "qiskit_aer")
} else {
  Write-Host "qiskit_aer not installed: building without it (cq-hecs verify will report it missing)"
}

& $Python -m PyInstaller `
  --noconfirm `
  --paths $Root `
  --clean `
  --onedir `
  --name cq-hecs `
  --distpath $OutDir `
  --workpath $WorkDir `
  --specpath $WorkDir `
  --add-data "$Root\cqhecs\studio\static;cqhecs\studio\static" `
  --add-data "$Root\cqhecs\studio\data;cqhecs\studio\data" `
  --collect-submodules qiskit `
  --collect-data qiskit `
  @AerArgs `
  "$Root\cqhecs\cli.py"

if ($LASTEXITCODE -ne 0) { throw "PyInstaller failed with exit code $LASTEXITCODE" }

$AppDir = Join-Path $OutDir "cq-hecs"
$Exe = Join-Path $AppDir "cq-hecs.exe"
if (-not (Test-Path $Exe)) { throw "expected $Exe was not produced" }

# Licence notices for everything that was bundled (PyInstaller does not copy them).
$SitePackages = (& $Python -c "import sysconfig;print(sysconfig.get_paths()['purelib'])").Trim()
$PyiCopying = Get-ChildItem -Path $SitePackages -Filter "COPYING.txt" -Recurse -ErrorAction SilentlyContinue |
  Where-Object { $_.FullName -like "*pyinstaller-*dist-info*" } | Select-Object -First 1
$NoticeArgs = @("--app-dir", $AppDir, "--metadata-root", $SitePackages,
  "--pyz-toc", (Join-Path $WorkDir "cq-hecs\PYZ-00.toc"), "--licence-file", "$Root\LICENSE")
if ($PyiCopying) { $NoticeArgs += @("--extra-file", ("PyInstaller bootloader=" + $PyiCopying.FullName)) }
& $Python "$Root\scripts\package_notices.py" @NoticeArgs
if ($LASTEXITCODE -ne 0) { throw "writing licence notices failed" }

if (-not $SkipSmoke) {
  # Copy the folder out of the build tree and smoke the copy from a temp directory.
  $Stage = Join-Path ([System.IO.Path]::GetTempPath()) ("cqhecs-onedir-" + [guid]::NewGuid().ToString("N"))
  New-Item -ItemType Directory -Path $Stage | Out-Null
  try {
    Copy-Item -Recurse $AppDir (Join-Path $Stage "cq-hecs")
    $Version = (& $Python "$Root\scripts\version.py").Trim()
    & $Python "$Root\scripts\package_smoke.py" --cmd (Join-Path $Stage "cq-hecs\cq-hecs.exe") `
      --label onedir --expect-version $Version --out (Join-Path $OutDir "smoke-onedir.json")
    if ($LASTEXITCODE -ne 0) { throw "standalone folder failed its smoke test (see smoke-onedir.json)" }
  } finally {
    Remove-Item -Recurse -Force $Stage -ErrorAction SilentlyContinue
  }
}

$Version = (& $Python "$Root\scripts\version.py").Trim()
$Zip = Join-Path $OutDir "cqhecs-$Version-windows-x64.zip"
if (Test-Path $Zip) { Remove-Item $Zip }
# Deterministic archive: sorted entries, fixed timestamp, forward-slash names.
& $Python "$Root\scripts\package_archive.py" --src $AppDir --out $Zip --root-name cq-hecs
if ($LASTEXITCODE -ne 0) { throw "archiving $AppDir failed" }
Write-Host "Built $Exe (onedir application folder; extract the zip before use)"
Write-Host "Archive: $Zip"
Write-Host ("SHA-256: " + (Get-FileHash $Zip -Algorithm SHA256).Hash.ToLower())
