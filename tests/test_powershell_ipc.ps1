# PowerShell IPC & JSON Pipeline Verification Test Script
# Validates PowerShell 5.1 and 7.x object deserialization via ConvertFrom-Json

$ErrorActionPreference = "Stop"
$exe = ".\bin\Release\cq_hecs.exe"

if (-not (Test-Path $exe)) {
    Write-Error "Binary not found at $exe"
    exit 1
}

Write-Host "=================================================================" -ForegroundColor Cyan
Write-Host " CQ-HECS v4.5: PowerShell IPC & JSON Streaming Test Suite" -ForegroundColor Cyan
Write-Host "=================================================================" -ForegroundColor Cyan

$allPassed = $true

# Test 1: Self-test JSON
Write-Host "[Test 1/5] Testing embedded self-test JSON pipeline..." -NoNewline
try {
    $out = & $exe test --json | ConvertFrom-Json
    if ($out.status -eq "SUCCESS" -and $out.total_tests -eq 7 -and $out.passed -eq 7) {
        Write-Host " [PASS]" -ForegroundColor Green
    } else {
        Write-Host " [FAIL]" -ForegroundColor Red
        $allPassed = $false
    }
} catch {
    Write-Host " [EXCEPTION: $_]" -ForegroundColor Red
    $allPassed = $false
}

# Test 2: QASM Stdin Pipeline
Write-Host "[Test 2/5] Testing QASM stdin pipeline with ConvertFrom-Json..." -NoNewline
try {
    $out = Get-Content benchmarks\qasm\ghz_300.qasm | & $exe qasm - --json | ConvertFrom-Json
    if ($out.status -eq "SUCCESS" -and $out.qubit_count -eq 300 -and $out.gate_count -eq 600 -and $out.vram_satisfied) {
        Write-Host " [PASS]" -ForegroundColor Green
    } else {
        Write-Host " [FAIL]" -ForegroundColor Red
        $allPassed = $false
    }
} catch {
    Write-Host " [EXCEPTION: $_]" -ForegroundColor Red
    $allPassed = $false
}

# Test 3: SAT UNSAT Pipeline & Exit Code 10
Write-Host "[Test 3/5] Testing SAT UNSAT pipeline and Exit Code 10..." -NoNewline
try {
    $out = Get-Content benchmarks\sat\pigeonhole_6_5.cnf | & $exe sat - --json | ConvertFrom-Json
    $exitCode = $LASTEXITCODE
    if ($out.status -eq "UNSAT" -and $out.verified -and $exitCode -eq 10) {
        Write-Host " [PASS (ExitCode: $exitCode)]" -ForegroundColor Green
    } else {
        Write-Host " [FAIL (Status: $($out.status), ExitCode: $exitCode)]" -ForegroundColor Red
        $allPassed = $false
    }
} catch {
    Write-Host " [EXCEPTION: $_]" -ForegroundColor Red
    $allPassed = $false
}

# Test 4: ARX Benchmarking Pipeline
Write-Host "[Test 4/5] Testing ARX cryptanalysis JSON pipeline..." -NoNewline
try {
    $out = & $exe arx blake2b --rounds 1000 --json | ConvertFrom-Json
    if ($out.status -eq "SUCCESS" -and $out.inverse_verified -and $out.carry_shadow_exact) {
        Write-Host " [PASS]" -ForegroundColor Green
    } else {
        Write-Host " [FAIL]" -ForegroundColor Red
        $allPassed = $false
    }
} catch {
    Write-Host " [EXCEPTION: $_]" -ForegroundColor Red
    $allPassed = $false
}

# Test 5: Stress Test Pipeline
Write-Host "[Test 5/5] Testing 10,000-cycle stress JSON pipeline..." -NoNewline
try {
    $out = & $exe stress --cycles 10000 --json | ConvertFrom-Json
    if ($out.status -eq "SUCCESS" -and $out.vram_satisfied -and (-not $out.memory_leaks_detected)) {
        Write-Host " [PASS]" -ForegroundColor Green
    } else {
        Write-Host " [FAIL]" -ForegroundColor Red
        $allPassed = $false
    }
} catch {
    Write-Host " [EXCEPTION: $_]" -ForegroundColor Red
    $allPassed = $false
}

Write-Host "=================================================================" -ForegroundColor Cyan
if ($allPassed) {
    Write-Host " ALL POWERSHELL IPC TESTS PASSED (EXIT CODE 0)" -ForegroundColor Green
    exit 0
} else {
    Write-Host " POWERSHELL IPC TESTS ENCOUNTERED FAILURES" -ForegroundColor Red
    exit 1
}
