# LEGACY (P-08) -- not part of the release pipeline and not the README-named assets.
#
# This script predates package.yml. It wipes the whole dist\ folder, builds a differently named
# archive (CQ-HECS-v<version>-Windows-x64.zip) from a mixed bin\Release tree and writes
# checksums.txt. None of that is published. The release assets are produced by
# .github/workflows/package.yml: cqhecs-<v>-py3-none-any.whl, cqhecs-<v>.tar.gz,
# cqhecs-<v>-windows-x64.zip (scripts/build_exe.ps1), cq-hecs-cpu-<v>-windows-x64.zip and
# cq-hecs-vulkan-<v>-windows-x64.zip (scripts/package_native.ps1), the CycloneDX SBOMs
# and SHA256SUMS (scripts/make_manifest.py). See docs/PACKAGING.md.
#
# It refuses to run unless -Legacy is passed, because running it deletes dist\.
param([switch]$Legacy)
if (-not $Legacy) {
    Write-Error "scripts/package_release.ps1 is LEGACY and deletes dist\. Use scripts/package_native.ps1 and scripts/build_exe.ps1 (see docs/PACKAGING.md), or pass -Legacy to run it anyway."
    exit 2
}

# Packaging Script for CQ-HECS (version derived from scripts/version.py)
$ErrorActionPreference = "Stop"

$version = (python scripts/version.py).Trim()
if ($LASTEXITCODE -ne 0 -or -not $version) {
    throw "Could not read the canonical version from scripts/version.py"
}

$dist = "dist\CQ-HECS-v$version-Windows-x64"
$zip = "dist\CQ-HECS-v$version-Windows-x64.zip"
$native = "build\bin\Release"

Write-Host "Creating clean distribution directories..." -ForegroundColor Cyan
if (Test-Path "dist") {
    Remove-Item -Recurse -Force "dist"
}

New-Item -ItemType Directory -Force -Path "$dist\bin" | Out-Null
New-Item -ItemType Directory -Force -Path "$dist\include" | Out-Null
New-Item -ItemType Directory -Force -Path "$dist\benchmarks\qasm" | Out-Null
New-Item -ItemType Directory -Force -Path "$dist\benchmarks\sat" | Out-Null
New-Item -ItemType Directory -Force -Path "$dist\docs" | Out-Null

Write-Host "Copying binaries and shared library..." -ForegroundColor Cyan
Copy-Item "$native\cq_hecs.exe" "$dist\bin\"
Copy-Item "$native\cq_hecs.dll" "$dist\bin\"
Copy-Item "$native\cq_hecs.lib" "$dist\bin\"
Copy-Item "include\cq_hecs_api.h" "$dist\include\"

Write-Host "Copying canonical benchmarks..." -ForegroundColor Cyan
Copy-Item "benchmarks\qasm\ghz_300.qasm" "$dist\benchmarks\qasm\"
Copy-Item "benchmarks\qasm\qft_300.qasm" "$dist\benchmarks\qasm\"
Copy-Item "benchmarks\sat\uf50_hard.cnf" "$dist\benchmarks\sat\"
Copy-Item "benchmarks\sat\pigeonhole_6_5.cnf" "$dist\benchmarks\sat\"

Write-Host "Copying documentation and metadata..." -ForegroundColor Cyan
Copy-Item "README.md" "$dist\docs\"
Copy-Item "docs\USAGE_GUIDE.md" "$dist\docs\"
Copy-Item "docs\API_REFERENCE.md" "$dist\docs\"
Copy-Item "docs\EMBEDDING_GUIDE.md" "$dist\docs\"
Copy-Item "docs\BENCHMARKS.md" "$dist\docs\"
Copy-Item "docs\ARCHITECTURE.md" "$dist\docs\"
Copy-Item "LICENSE" "$dist\"
Copy-Item "CHANGELOG.md" "$dist\"

Write-Host "Compressing distribution zip archive..." -ForegroundColor Cyan
Compress-Archive -Path "$dist\*" -DestinationPath $zip -Force

Write-Host "Generating SHA-256 checksums..." -ForegroundColor Cyan
$sha256 = (Get-FileHash $zip -Algorithm SHA256).Hash.ToLower()
"$sha256  CQ-HECS-v$version-Windows-x64.zip" | Out-File -Encoding ascii "dist\checksums.txt"

Write-Host "Release packaging complete for v$version:" -ForegroundColor Green
Get-ChildItem -Recurse "dist"
Get-Content "dist\checksums.txt"
