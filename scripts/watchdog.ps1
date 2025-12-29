# WATCHDOG: Sequential Gate Execution (doctor → fast → regression)
# Purpose: Run all gates in order with evidence collection
# SSOT: .windsurfrule [WATCHDOG] section
# Evidence: logs/evidence/<run_id>/ (auto-generated)

param(
    [switch]$SkipDoctor = $false,
    [switch]$SkipFast = $false,
    [switch]$SkipRegression = $false
)

$ErrorActionPreference = "Stop"
$StartTime = Get-Date

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "WATCHDOG: Sequential Gate Execution" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Start Time: $StartTime" -ForegroundColor Gray
Write-Host ""

$gates = @()
$failedGates = @()
$passedGates = @()

# Helper function to run a gate
function Run-Gate {
    param(
        [string]$GateName,
        [scriptblock]$Command,
        [switch]$Skip
    )
    
    if ($Skip) {
        Write-Host "⊘ Skipping $GateName (--Skip$GateName)" -ForegroundColor Yellow
        return $null
    }
    
    Write-Host ""
    Write-Host "========================================" -ForegroundColor Green
    Write-Host "Gate: $GateName" -ForegroundColor Green
    Write-Host "========================================" -ForegroundColor Green
    Write-Host ""
    
    $gateStartTime = Get-Date
    
    try {
        # Run the gate command
        & $Command
        
        $exitCode = $LASTEXITCODE
        $gateEndTime = Get-Date
        $duration = ($gateEndTime - $gateStartTime).TotalSeconds
        
        if ($exitCode -eq 0) {
            Write-Host ""
            Write-Host "✅ $GateName PASSED ($([Math]::Round($duration, 2))s)" -ForegroundColor Green
            $passedGates += $GateName
            return $true
        } else {
            Write-Host ""
            Write-Host "❌ $GateName FAILED (exit code: $exitCode)" -ForegroundColor Red
            $failedGates += $GateName
            return $false
        }
    }
    catch {
        Write-Host ""
        Write-Host "❌ $GateName ERROR: $_" -ForegroundColor Red
        $failedGates += $GateName
        return $false
    }
}

# Run gates in sequence
Write-Host "Running gates in sequence: doctor → fast → regression" -ForegroundColor Cyan
Write-Host ""

# Initialize Evidence Packer (d200-3)
Write-Host ""
Write-Host "Initializing Evidence Packer (d200-3)..." -ForegroundColor Cyan
$evidenceOutput = & ".\abt_bot_env\Scripts\python.exe" -c "from tools.evidence_pack import EvidencePacker; p = EvidencePacker('d200-3', 'watchdog'); p.start(); print(f'Evidence: {p.run_id}')" 2>&1
Write-Host $evidenceOutput -ForegroundColor Gray

# Gate 1: Doctor
$doctorResult = Run-Gate -GateName "doctor" `
    -Command { & ".\abt_bot_env\Scripts\python.exe" -m pytest tests/ --collect-only -q } `
    -Skip:$SkipDoctor

if ($doctorResult -eq $false -and -not $SkipDoctor) {
    Write-Host ""
    Write-Host "❌ WATCHDOG STOPPED: doctor gate failed" -ForegroundColor Red
    Write-Host "Fix the errors and re-run watchdog" -ForegroundColor Yellow
    exit 1
}

# Gate 2: Fast
$fastResult = Run-Gate -GateName "fast" `
    -Command { & ".\abt_bot_env\Scripts\python.exe" -m pytest -m "not optional_ml and not optional_live and not live_api and not fx_api" -x --tb=short -v } `
    -Skip:$SkipFast

if ($fastResult -eq $false -and -not $SkipFast) {
    Write-Host ""
    Write-Host "❌ WATCHDOG STOPPED: fast gate failed" -ForegroundColor Red
    Write-Host "Fix the errors and re-run watchdog" -ForegroundColor Yellow
    exit 1
}

# Gate 3: Regression
$regressionResult = Run-Gate -GateName "regression" `
    -Command { & ".\abt_bot_env\Scripts\python.exe" -m pytest -m "not live_api and not fx_api" --tb=short -v } `
    -Skip:$SkipRegression

if ($regressionResult -eq $false -and -not $SkipRegression) {
    Write-Host ""
    Write-Host "❌ WATCHDOG STOPPED: regression gate failed" -ForegroundColor Red
    Write-Host "Fix the errors and re-run watchdog" -ForegroundColor Yellow
    exit 1
}

# Summary
Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "WATCHDOG SUMMARY" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan

$endTime = Get-Date
$totalDuration = ($endTime - $StartTime).TotalSeconds

Write-Host "Passed: $($passedGates.Count)" -ForegroundColor Green
foreach ($gate in $passedGates) {
    Write-Host "  ✅ $gate" -ForegroundColor Green
}

if ($failedGates.Count -gt 0) {
    Write-Host "Failed: $($failedGates.Count)" -ForegroundColor Red
    foreach ($gate in $failedGates) {
        Write-Host "  ❌ $gate" -ForegroundColor Red
    }
}

Write-Host "Total Duration: $([Math]::Round($totalDuration, 2))s" -ForegroundColor Gray
Write-Host "End Time: $endTime" -ForegroundColor Gray

# Check for evidence
Write-Host ""
Write-Host "Evidence Check:" -ForegroundColor Cyan
$evidencePath = "logs/evidence"
if (Test-Path $evidencePath) {
    $latestEvidence = Get-ChildItem $evidencePath -Directory | Sort-Object LastWriteTime -Descending | Select-Object -First 1
    if ($latestEvidence) {
        Write-Host "  📁 Latest evidence: $($latestEvidence.Name)" -ForegroundColor Green
        $files = Get-ChildItem $latestEvidence.FullName -File
        foreach ($file in $files) {
            Write-Host "    - $($file.Name)" -ForegroundColor Gray
        }
    }
} else {
    Write-Host "  ⚠️ No evidence directory found" -ForegroundColor Yellow
}

Write-Host ""

# Exit with appropriate code
if ($failedGates.Count -eq 0) {
    Write-Host "✅ WATCHDOG PASSED" -ForegroundColor Green
    exit 0
} else {
    Write-Host "❌ WATCHDOG FAILED" -ForegroundColor Red
    exit 1
}
