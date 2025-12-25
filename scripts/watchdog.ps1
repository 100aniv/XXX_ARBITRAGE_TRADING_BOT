param(
    [Parameter(Mandatory=$true)]
    [ValidateSet("fast","regression","full")]
    [string]$mode
)

# watchdog.ps1: watchexec 기반 파일 변경 감지 자동 재실행 (또는 PowerShell FileSystemWatcher 폴백)
# 용도: 개발 중 파일 저장 시 자동으로 just <mode> 재실행
# 사용: .\scripts\watchdog.ps1 fast|regression|full
# 주의: watch 모드에서는 테스트 실행만 (설치/대화형 명령 금지)

$exts = "py,md,toml,yml,yaml,json"
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

Write-Host "[watchdog] mode=$mode exts=$exts" -ForegroundColor Cyan
Write-Host "[watchdog] ignore=$($ignore -join ', ')" -ForegroundColor Gray

# watchexec 명령 구성
$ignoreArgs = @()
foreach ($pattern in $ignore) {
    $ignoreArgs += @("--ignore", $pattern)
}

# watchexec 사용 시도
$watchexecPath = (Get-Command watchexec -ErrorAction SilentlyContinue).Source
if ($watchexecPath) {
    Write-Host "[watchdog] Using watchexec: $watchexecPath" -ForegroundColor Green
    Write-Host "[watchdog] Press Ctrl+C to stop" -ForegroundColor Yellow
    
    $watchexecArgs = @(
        "--watch", ".",
        "--exts", $exts,
        "--restart"
    ) + $ignoreArgs + @("--", "just", $mode)
    
    & watchexec @watchexecArgs
} else {
    Write-Host "[watchdog] watchexec not found, using PowerShell FileSystemWatcher fallback" -ForegroundColor Yellow
    Write-Host "[watchdog] Press Ctrl+C to stop" -ForegroundColor Yellow
    
    # Fallback: PowerShell FileSystemWatcher
    $watcher = New-Object System.IO.FileSystemWatcher
    $watcher.Path = (Get-Location).Path
    $watcher.IncludeSubdirectories = $true
    $watcher.EnableRaisingEvents = $true
    
    $lastRun = [DateTime]::MinValue
    $debounceMs = 1000
    $extsArray = $exts -split ","
    
    $action = {
        $file = $Event.SourceEventArgs.FullPath
        $fileName = Split-Path -Leaf $file
        $fileExt = [System.IO.Path]::GetExtension($file).TrimStart('.')
        
        $shouldIgnore = $false
        foreach ($pattern in $ignore) {
            if ($file -match [regex]::Escape($pattern)) {
                $shouldIgnore = $true
                break
            }
        }
        
        $hasValidExt = $fileExt -in $extsArray
        
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
    
    $null = Register-ObjectEvent -InputObject $watcher -EventName "Changed" -Action $action
    $null = Register-ObjectEvent -InputObject $watcher -EventName "Created" -Action $action
    
    Write-Host "[watchdog] Watching for changes..." -ForegroundColor Green
    
    try {
        while ($true) { Start-Sleep -Seconds 1 }
    } finally {
        $watcher.EnableRaisingEvents = $false
        $watcher.Dispose()
        Write-Host "[watchdog] Stopped" -ForegroundColor Yellow
    }
}
