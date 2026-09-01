# Packaging Script for CQ-HECS v4.5.0 Release
$ErrorActionPreference = "Stop"

$dist = "dist\CQ-HECS-v4.5.0-Windows-x64"
$zip = "dist\CQ-HECS-v4.5.0-Windows-x64.zip"

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
Copy-Item "bin\Release\cq_hecs.exe" "$dist\bin\"
Copy-Item "bin\Release\cq_hecs.dll" "$dist\bin\"
Copy-Item "bin\Release\cq_hecs.lib" "$dist\bin\"
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
"$sha256  CQ-HECS-v4.5.0-Windows-x64.zip" | Out-File -Encoding ascii "dist\checksums.txt"

Write-Host "Release packaging complete:" -ForegroundColor Green
Get-ChildItem -Recurse "dist"
Get-Content "dist\checksums.txt"
