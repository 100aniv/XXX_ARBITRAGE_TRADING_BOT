param(
    [Parameter(Mandatory=$true)]
    [ValidateSet("fast","regression","full")]
    [string]$mode
)

# watchdog.ps1: watchexec 호환 파일 변경 감지 자동 재실행
# 용도: 개발 중 파일 저장 시 자동으로 just <mode> 재실행
# 사용: .\scripts\watchdog.ps1 fast|regression|full
# 근거: SSOT Core Regression (44 tests, D92 정의)

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

# PowerShell FileSystemWatcher: watchexec 호환 구현
$watcher = New-Object System.IO.FileSystemWatcher
$watcher.Path = (Get-Location).Path
$watcher.IncludeSubdirectories = $true
$watcher.EnableRaisingEvents = $true

$lastRun = [DateTime]::MinValue
$debounceMs = 1000

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
            Write-Host "[watchdog] Running: just $mode" -ForegroundColor Green
            Invoke-Expression "just $mode"
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
