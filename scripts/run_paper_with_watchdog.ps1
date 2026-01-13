# D205-2 REOPEN: Watchdog 강제 실행 래퍼
# 
# Purpose: longrun(3h+) 실행 시 watchdog 모니터링 강제
# - 프로세스 crash/timeout 감지
# - 자동 로그 저장
# - 사용자 떠넘김 0 (완전 자동화)
#
# Usage:
#   .\scripts\run_paper_with_watchdog.ps1 -Durations "20,60,180" -Phases "smoke,baseline,longrun" -Profile "ssot"
#   .\scripts\run_paper_with_watchdog.ps1 -Durations "1,2,3" -Phases "smoke_q,baseline_q,longrun_q" -Profile "quick"

param(
    [Parameter(Mandatory=$true)]
    [string]$Durations,
    
    [Parameter(Mandatory=$true)]
    [string]$Phases,
    
    [Parameter(Mandatory=$false)]
    [ValidateSet("ssot", "acceptance", "quick")]
    [string]$Profile = "ssot",
    
    [Parameter(Mandatory=$false)]
    [ValidateSet("strict", "optional", "off")]
    [string]$DbMode = "strict",
    
    [Parameter(Mandatory=$false)]
    [int]$TimeoutSeconds = 0,  # 0 = no timeout
    
    [Parameter(Mandatory=$false)]
    [string]$EvidenceRoot = "logs/evidence"
)

# ============================================================================
# Functions
# ============================================================================

function Write-Log {
    param([string]$Message, [string]$Level = "INFO")
    $timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    $color = switch ($Level) {
        "ERROR" { "Red" }
        "WARN"  { "Yellow" }
        "SUCCESS" { "Green" }
        default { "White" }
    }
    Write-Host "[$timestamp] [$Level] $Message" -ForegroundColor $color
}

function Test-LongrunRequirement {
    param([string]$Phases, [string]$Durations)
    
    $phaseList = $Phases -split ","
    $durationList = $Durations -split "," | ForEach-Object { [int]$_ }
    
    for ($i = 0; $i -lt $phaseList.Count; $i++) {
        $phase = $phaseList[$i].Trim()
        $duration = $durationList[$i]
        
        # longrun 라벨 + duration >= 180 → watchdog 필수
        if ($phase -like "*longrun*" -and $duration -ge 180) {
            return $true
        }
    }
    
    return $false
}

# ============================================================================
# Main
# ============================================================================

Write-Log "========================================" "INFO"
Write-Log "D205-2 REOPEN: Watchdog Wrapper START" "INFO"
Write-Log "========================================" "INFO"
Write-Log "Durations: $Durations" "INFO"
Write-Log "Phases: $Phases" "INFO"
Write-Log "Profile: $Profile" "INFO"
Write-Log "DB Mode: $DbMode" "INFO"

# longrun 요구사항 체크
$requireWatchdog = Test-LongrunRequirement -Phases $Phases -Durations $Durations

if ($requireWatchdog) {
    Write-Log "✅ Watchdog required (longrun >= 180m detected)" "SUCCESS"
} else {
    Write-Log "⚠️  Watchdog optional (no longrun >= 180m)" "WARN"
}

# Python 가상환경 활성화
$pythonExe = ".\abt_bot_env\Scripts\python.exe"
if (-not (Test-Path $pythonExe)) {
    Write-Log "❌ Python executable not found: $pythonExe" "ERROR"
    exit 1
}

# D205-18-1: REAL data 강제 체크 (baseline/longrun 포함 시)
$phaseList = $Phases -split ","
$useRealData = $false
foreach ($phase in $phaseList) {
    $phaseTrimmed = $phase.Trim()
    if ($phaseTrimmed -in @("smoke", "baseline", "longrun")) {
        $useRealData = $true
        Write-Log "✅ REAL data enforced for phase '$phaseTrimmed' (D205-18-1)" "SUCCESS"
        break
    }
}

# paper_chain 실행 명령어 구성
$cmd = "$pythonExe -m arbitrage.v2.harness.paper_chain --durations $Durations --phases $Phases --profile $Profile --db-mode $DbMode"
Write-Log "Command: $cmd" "INFO"
Write-Log "REAL data mode: $useRealData" "INFO"

# 프로세스 시작
Write-Log "Starting paper_chain process..." "INFO"
$startTime = Get-Date

try {
    # D205-18-1: ArgumentList는 paper_chain 내부에서 --use-real-data 처리
    # (paper_chain.py가 phase별로 자동 추가)
    $process = Start-Process -FilePath $pythonExe `
        -ArgumentList "-m", "arbitrage.v2.harness.paper_chain", `
                      "--durations", $Durations, `
                      "--phases", $Phases, `
                      "--profile", $Profile, `
                      "--db-mode", $DbMode `
        -NoNewWindow `
        -PassThru `
        -RedirectStandardOutput "logs/watchdog_stdout.log" `
        -RedirectStandardError "logs/watchdog_stderr.log"
    
    Write-Log "Process started: PID=$($process.Id)" "SUCCESS"
    
    # Watchdog 모니터링 루프
    $checkInterval = 10  # 10초마다 체크
    $elapsedSeconds = 0
    
    while (-not $process.HasExited) {
        Start-Sleep -Seconds $checkInterval
        $elapsedSeconds += $checkInterval
        
        $elapsedMinutes = [math]::Floor($elapsedSeconds / 60)
        Write-Log "⏱️  Running... Elapsed: ${elapsedMinutes}m" "INFO"
        
        # Timeout 체크
        if ($TimeoutSeconds -gt 0 -and $elapsedSeconds -ge $TimeoutSeconds) {
            Write-Log "❌ TIMEOUT: $TimeoutSeconds seconds exceeded" "ERROR"
            $process.Kill()
            exit 1
        }
        
        # CPU/Memory 체크 (optional)
        try {
            $proc = Get-Process -Id $process.Id -ErrorAction SilentlyContinue
            if ($proc) {
                $cpu = [math]::Round($proc.CPU, 2)
                $memMB = [math]::Round($proc.WorkingSet64 / 1MB, 2)
                Write-Log "📊 CPU: ${cpu}s, Memory: ${memMB}MB" "INFO"
            }
        } catch {
            # Ignore errors (process may have exited)
        }
    }
    
    # 종료 확인
    $exitCode = $process.ExitCode
    $endTime = Get-Date
    $totalDuration = ($endTime - $startTime).TotalSeconds
    
    Write-Log "Process finished: Exit Code=$exitCode, Duration=${totalDuration}s" "INFO"
    
    if ($exitCode -eq 0) {
        Write-Log "✅ SUCCESS: paper_chain completed successfully" "SUCCESS"
    } else {
        Write-Log "❌ FAIL: paper_chain failed with exit code $exitCode" "ERROR"
        Write-Log "Check logs: logs/watchdog_stderr.log" "ERROR"
    }
    
    exit $exitCode
    
} catch {
    Write-Log "❌ Exception: $_" "ERROR"
    exit 1
}
