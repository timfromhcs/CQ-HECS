# Isolated Sandbox Smoke Test Script
# Verifies zero runtime file/DLL dependency from a standalone temporary folder

$ErrorActionPreference = "Stop"

$sandbox = Join-Path $env:TEMP "cq_hecs_smoke_test"
$zip = (Resolve-Path "dist\CQ-HECS-v4.5.0-Windows-x64.zip").Path

Write-Host "=================================================================" -ForegroundColor Cyan
Write-Host " CQ-HECS v4.5.0: Isolated Sandbox Smoke Test" -ForegroundColor Cyan
Write-Host " Sandbox Location: $sandbox" -ForegroundColor Cyan
Write-Host "=================================================================" -ForegroundColor Cyan

# Step 1: Clean and create sandbox
if (Test-Path $sandbox) {
    Remove-Item -Recurse -Force $sandbox
}
New-Item -ItemType Directory -Force -Path $sandbox | Out-Null

# Step 2: Extract zip archive
Write-Host "[1/5] Extracting release zip archive into sandbox..." -ForegroundColor Cyan
Expand-Archive -Path $zip -DestinationPath $sandbox -Force

# Step 3: Run standalone verification commands from the sandbox
Push-Location $sandbox
try {
    $exe = ".\bin\cq_hecs.exe"

    # Command 1: --version
    Write-Host "[2/5] Testing --version flag..." -NoNewline
    $verOut = & $exe --version
    if ($LASTEXITCODE -eq 0 -and $verOut -match "v4.5.0") {
        Write-Host " [PASS: $verOut]" -ForegroundColor Green
    } else {
        throw "Failed --version: $verOut"
    }

    # Command 2: qasm benchmarks\qasm\ghz_300.qasm --json
    Write-Host "[3/5] Testing 300-qubit OpenQASM simulation in sandbox..." -NoNewline
    $qasmOut = & $exe qasm benchmarks\qasm\ghz_300.qasm --json | ConvertFrom-Json
    if ($LASTEXITCODE -eq 0 -and $qasmOut.status -eq "SUCCESS" -and $qasmOut.qubit_count -eq 300) {
        Write-Host " [PASS: $($qasmOut.gate_count) gates, $($qasmOut.active_vram_mb) MB VRAM]" -ForegroundColor Green
    } else {
        throw "Failed QASM execution: $qasmOut"
    }

    # Command 3: sat benchmarks\sat\pigeonhole_6_5.cnf --json (Exit code 10!)
    Write-Host "[4/5] Testing DIMACS SAT UNSAT refutation in sandbox..." -NoNewline
    $satOut = & $exe sat benchmarks\sat\pigeonhole_6_5.cnf --json | ConvertFrom-Json
    $satCode = $LASTEXITCODE
    if ($satCode -eq 10 -and $satOut.status -eq "UNSAT" -and $satOut.verified) {
        Write-Host " [PASS: UNSAT certified, Exit Code 10]" -ForegroundColor Green
    } else {
        throw "Failed SAT execution: code=$satCode status=$($satOut.status)"
    }

    # Command 4: arx blake2b --rounds 100 --json
    Write-Host "[5/5] Testing ARX BLAKE2b inversion in sandbox..." -NoNewline
    $arxOut = & $exe arx blake2b --rounds 100 --json | ConvertFrom-Json
    if ($LASTEXITCODE -eq 0 -and $arxOut.status -eq "SUCCESS" -and $arxOut.inverse_verified) {
        Write-Host " [PASS: Inverse verified, Carry shadow exact]" -ForegroundColor Green
    } else {
        throw "Failed ARX execution: $arxOut"
    }

    Write-Host "=================================================================" -ForegroundColor Cyan
    Write-Host " ALL SANDBOX SMOKE TESTS PASSED CLEANLY (EXIT CODE 0)" -ForegroundColor Green
    Write-Host "=================================================================" -ForegroundColor Cyan
} finally {
    Pop-Location
    # Step 4: Cleanup sandbox
    Write-Host "Cleaning up temporary sandbox directory..." -ForegroundColor Cyan
    Remove-Item -Recurse -Force $sandbox
}
