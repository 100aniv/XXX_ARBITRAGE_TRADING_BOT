param(
    [Parameter(Mandatory=$true)]
    [ValidateSet("fast","regression","full")]
    [string]$mode
)

# watchdog.ps1: PowerShell FileSystemWatcher 기반 파일 변경 감지 자동 재실행
# 용도: 개발 중 파일 저장 시 자동으로 pytest 재실행
# 사용: .\scripts\watchdog.ps1 fast|regression|full
# 주의: watch 모드에서는 테스트 실행만 (설치/대화형 명령 금지)

$exts = @("py", "md", "toml", "yml", "yaml", "json")
$ignore = @(
    ".git",
    ".venv", "venv",
    "__pycache__",
    ".pytest_cache",
    "logs",
    "dist", "build",
    "node_modules",
    ".mypy_cache",
    ".ruff_cache",
    ".tmp.driveupload"
)

Write-Host "[watchdog] mode=$mode exts=$($exts -join ',')" -ForegroundColor Cyan
Write-Host "[watchdog] ignore=$($ignore -join ', ')" -ForegroundColor Gray
Write-Host "[watchdog] Press Ctrl+C to stop" -ForegroundColor Yellow

# pytest 명령 구성
$testCmd = switch ($mode) {
    "fast" { "python -m pytest -m `"not optional_ml and not optional_live`" -q" }
    "regression" { "python -m pytest -m `"not optional_ml and not optional_live`" -q" }
    "full" { "python -m pytest -q" }
}

Write-Host "[watchdog] Command: $testCmd" -ForegroundColor Gray

# FileSystemWatcher 구성
$watcher = New-Object System.IO.FileSystemWatcher
$watcher.Path = (Get-Location).Path
$watcher.IncludeSubdirectories = $true
$watcher.EnableRaisingEvents = $true

# 마지막 실행 시간 추적 (폭주 방지)
$lastRun = [DateTime]::MinValue
$debounceMs = 1000

# 파일 변경 이벤트 처리
$action = {
    $file = $Event.SourceEventArgs.FullPath
    $fileName = Split-Path -Leaf $file
    $fileExt = [System.IO.Path]::GetExtension($file).TrimStart('.')
    
    # ignore 패턴 확인
    $shouldIgnore = $false
    foreach ($pattern in $ignore) {
        if ($file -match [regex]::Escape($pattern)) {
            $shouldIgnore = $true
            break
        }
    }
    
    # 확장자 확인
    $hasValidExt = $fileExt -in $exts
    
    # 실행 조건: ignore 아님 + 유효한 확장자 + debounce 시간 경과
    if (-not $shouldIgnore -and $hasValidExt) {
        $now = [DateTime]::Now
        if (($now - $script:lastRun).TotalMilliseconds -gt $debounceMs) {
            $script:lastRun = $now
            Write-Host "[watchdog] Change detected: $fileName" -ForegroundColor Yellow
            Write-Host "[watchdog] Running: $script:testCmd" -ForegroundColor Green
            Invoke-Expression $script:testCmd
        }
    }
}

# 이벤트 등록
$null = Register-ObjectEvent -InputObject $watcher -EventName "Changed" -Action $action
$null = Register-ObjectEvent -InputObject $watcher -EventName "Created" -Action $action

Write-Host "[watchdog] Watching for changes..." -ForegroundColor Green

# Ctrl+C까지 대기
try {
    while ($true) { Start-Sleep -Seconds 1 }
} finally {
    $watcher.EnableRaisingEvents = $false
    $watcher.Dispose()
    Write-Host "[watchdog] Stopped" -ForegroundColor Yellow
}
