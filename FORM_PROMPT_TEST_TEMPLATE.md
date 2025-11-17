````markdown
# =====================================================================
# 🚀 PHASE16 REAL PAPER 테스트 – Windsurf용 마스터 프롬프트 템플릿
# =====================================================================

아래 내용 전체를 **Windsurf에 그대로 붙여넣어서** 실행하라.  
단, 이 프롬프트는 **“실행 전 완전 초기화 → REAL PAPER 실행 → 실시간 모니터링 → 문제 발생 시 디버깅 → 리포트/커밋”** 흐름을 **한 번에** 처리하기 위한 템플릿이다.

- 기본 대상 프로젝트: `future_alarm_bot`
- 기본 모드: `REAL PAPER (wall_clock 모드)`
- 기본 전략 예시: `scalping`, `BTCUSDT`, `3m`
- 기본 테스트 시간 예시: `12h` (필요 시 duration 부분만 변경해서 재사용)

---

## 0. 전제 조건 및 금지사항

### 0-1. 반드시 지켜야 할 것

1. **`run_paper.py` 는 “한 번만” 실행**  
   - 이미 PAPER가 실행 중인데 새로 또 켜면 안 된다.
2. **모니터링/디버깅 단계에서는 `run_paper.py` 를 절대 다시 실행하지 않는다.**
3. 모든 모니터링/로그 분석은 **“이번 실행의 시작 시각 이후 로그만”** 기준으로 처리한다.
4. 초기화 단계에서만:
   - Python 프로세스 강제 종료
   - Redis FLUSHALL
   - Scorecard 디렉토리 백업 후 재생성
   - `application.log` 롤링

### 0-2. 이 템플릿에서 사용되는 파일/폴더

- 가상환경: `trading_bot_env`
- Redis 컨테이너: `trading_redis`
- Postgres 컨테이너: `trading_db_postgres`
- 로그 파일: `logs/application.log`
- Scorecard 루트: `scorecards/paper_phase16`
- REAL PAPER 설정 예시:
  - `configs/scalping/real_paper_12h_v3.yml`
- PHASE16 문서:
  - `docs/PHASE16/PHASE16_REAL_PAPER_12H_REPORT.md`

---

## 1. 전체 목표

1. 기존 실행/데이터/가드 상태를 **완전히 초기화**하고,
2. **테스트 전용 REAL PAPER 설정 YAML**을 생성한 뒤,
3. **새 CMD 창에서 REAL PAPER를 비동기 실행**하고,
4. **정해진 체크포인트(M5, M10, M30, 1h, 2h, 4h, …, 12h)를 기준으로 실시간 모니터링**하며,
5. **Guard/ERROR/Traceback 발생 시 즉시 디버깅 모드로 전환**하고,
6. **Scorecard/리포트 문서를 업데이트**하며,
7. 마지막으로 **Git 커밋까지 완료**하는 것.

---

## 2. STEP 0 – 완전 초기화 (CLEAN RESET)

`future_alarm_bot` 루트에서 아래 순서대로 처리하라.

### 2-1. `future_alarm_bot` 관련 Python 프로세스 전부 종료

```powershell
Get-Process python -ErrorAction SilentlyContinue | Where-Object {
    $_.Path -like "*future_alarm_bot*"
} | Stop-Process -Force -ErrorAction SilentlyContinue
````

* 설명: 이전에 실행 중이던 PAPER/백테스트/기타 엔진이 남아있지 않도록 **모두 강제 종료**한다.

---

### 2-2. Redis 완전 초기화 (쿨다운/포트폴리오/가드 상태 포함)

```powershell
docker exec trading_redis redis-cli FLUSHALL
docker exec trading_redis redis-cli DBSIZE
```

* `DBSIZE`가 `0` 인지 확인해야 한다.
* 이 단계에서 **쿨다운, 포트폴리오, 가드 상태, 이전 PAPER 관련 키**가 모두 초기화된다.

---

### 2-3. Scorecard 디렉토리 백업 후 새로 생성

```powershell
$ts = Get-Date -Format "yyyyMMdd_HHmmss"
if (Test-Path "scorecards\paper_phase16") {
    Move-Item "scorecards\paper_phase16" "scorecards\paper_phase16_backup_$ts"
}
New-Item -ItemType Directory -Path "scorecards\paper_phase16" | Out-Null
```

* 기존 실행 기록은 `backup` 폴더에 보존하고,
* 이번 REAL PAPER 실행만 담을 새로운 디렉토리를 만든다.

---

### 2-4. `logs/application.log` 롤링 및 초기화

```powershell
$ts = Get-Date -Format "yyyyMMdd_HHmmss"
if (Test-Path "logs\application.log") {
    Move-Item "logs\application.log" "logs\application_$ts.log"
}
New-Item -ItemType File -Path "logs\application.log" | Out-Null
```

* 이전 실행의 로그와 이번 실행의 로그를 **명확히 분리**하기 위함.
* 이후 모니터링/디버깅은 `logs/application.log`의 **이번 실행 구간**만 사용한다.

---

### 2-5. 가상환경 및 Docker 상태 점검

```powershell
& .\trading_bot_env\Scripts\Activate.ps1
python --version

docker ps --filter "name=trading_redis" --filter "name=trading_db_postgres" --format "table {{.Names}}\t{{.Status}}"
```

* Python 3.x 버전 출력 확인.
* `trading_redis`, `trading_db_postgres` 컨테이너가 **Up** / **(healthy)** 인지 확인.
* 이상이 있으면 **여기서 먼저 해결**하고 진행해야 한다.

---

## 3. STEP 1 – REAL PAPER 전용 설정 YAML 생성 (예: 12h v3)

아래는 **예시**이며, 필요 시 duration/리스크 설정을 변경하여 재사용한다.
(1차: Drawdown Guard, 2차: Exposure Guard 조기 종료 경험을 반영한 버전 예시)

```powershell
@"
paper:
  duration_hours: 12           # 필요시 1, 6, 24 등으로 변경 가능
  duration_mode: wall_clock    # REAL PAPER는 반드시 wall_clock

risk:
  max_drawdown_pct: 25.0       # 1차 테스트(17.55% DD) 기준 완만히 완화
  max_positions: 2             # Exposure Guard를 피하기 위해 동시 포지션 수 제한

portfolio:
  symbol_cooldown_seconds: 120 # 동일 심볼 재진입 쿨다운 강화

logging:
  level: INFO
"@ | Out-File "configs/scalping/real_paper_12h_v3.yml" -Encoding utf8
```

* 이 파일은 **튜닝/테스트 결과에 따라 v4, v5 … 형태로 복제/변형**해 쓸 수 있다.
* 핵심은:

  * `duration_mode: wall_clock`
  * `max_drawdown_pct`, `max_positions`, `symbol_cooldown_seconds` 로 **가드와 리스크를 설계**한다는 점.

---

## 4. STEP 2 – REAL PAPER 실행 (새 CMD 창, 비동기)

> ⚠️ 이 단계 이후부터는 **절대 `run_paper.py` 를 중복 실행하지 말 것.**
> Windsurf PowerShell 세션은 오직 **모니터링/디버깅/리포트** 전용으로 사용한다.

```powershell
& .\trading_bot_env\Scripts\Activate.ps1

$start  = Get-Date
$startStr = $start.ToString("yyyy-MM-dd HH:mm:ss")
$startStr | Out-File "test_paper_start_time.txt" -Encoding utf8

Start-Process -FilePath "cmd.exe" -ArgumentList "/k python scripts/run_paper.py --strategy scalping --symbol BTCUSDT --timeframe 3m --duration-hours 12 --duration-mode wall_clock --config configs/scalping/real_paper_12h_v3.yml"

"🔵 REAL PAPER 시작(KST): $startStr" | Write-Host
```

* PAPER 엔진은 **새 CMD 창에서만** 돌아간다.
* `test_paper_start_time.txt` 는 이후 모니터링 시 **시작 기준 시각**으로 사용된다.

---

## 5. STEP 3 – 모니터링 함수 정의 (시작 시각 이후 로그 기준)

> 이 함수는 **이번 실행의 시작 시각 이후 로그만** 기준으로 통계를 집계한다.

```powershell
function Write-MonitorSnapshot {
  param([string]$label)

  $startText = Get-Content "test_paper_start_time.txt" -Raw
  $startTime = Get-Date $startText.Trim()
  $now = Get-Date
  $elapsed = $now - $startTime

  # Redis 상태
  $db = docker exec trading_redis redis-cli DBSIZE

  # 시작 이후 로그만 필터링
  $logs = Get-Content logs\application.log | Where-Object {
    $_.Length -ge 19 -and
    ($tsStr = $_.Substring(0,19);
     [datetime]::TryParse($tsStr, [ref]([datetime]::MinValue))) -and
    ([datetime]$tsStr -ge $startTime)
  }

  $entryCount  = ($logs | Select-String "ENTRY OPEN" | Measure-Object).Count
  $closedCount = ($logs | Select-String "TP1:|SL:" | Measure-Object).Count

  $errors = $logs | Select-String "ERROR|Traceback|Guard" | Select-Object -Last 20

  Write-Host ""
  Write-Host "=== [$label] 체크포인트 ==="
  Write-Host "현재 시각: $($now.ToString("yyyy-MM-dd HH:mm:ss"))"
  Write-Host ("경과 시간: {0:hh\:mm\:ss}" -f $elapsed)
  Write-Host "Redis DBSIZE: $db"
  Write-Host "ENTRY OPEN (이 실행 기준): $entryCount"
  Write-Host "CLOSED (TP/SL, 이 실행 기준): $closedCount"
  Write-Host "최근 ERROR/Traceback/Guard (최대 20줄):"
  $errors | ForEach-Object { Write-Host $_ }

  # 모니터링 로그 파일에도 기록
  $lines = @()
  $lines += "=== [$label] 체크포인트 ==="
  $lines += "현재 시각: $($now.ToString("yyyy-MM-dd HH:mm:ss"))"
  $lines += ("경과 시간: {0:hh\:mm\:ss}" -f $elapsed)
  $lines += "Redis DBSIZE: $db"
  $lines += "ENTRY OPEN: $entryCount"
  $lines += "CLOSED: $closedCount"
  $lines += "최근 ERROR/Traceback/Guard:"
  $lines += ($errors | ForEach-Object { $_.ToString() })

  $lines | Out-File "logs\paper_monitoring_snapshots.log" -Append -Encoding utf8
}
```

* 이 함수만 반복 호출하면,
  **실시간 스냅샷 + 장기 기록 둘 다 확보**된다.

---

## 6. STEP 4 – 체크포인트별 모니터링 시나리오

> 아래 시간은 예시이며, 실제 테스트 시간에 맞게 조정해 사용할 수 있다.

### 6-1. 체크포인트 타임라인 예시

* `M5`   : 시작 후 5분
* `M10`  : 시작 후 10분
* `M30`  : 시작 후 30분
* `M1h`  : 시작 후 1시간
* `M2h`  : 시작 후 2시간
* `M4h`  : 시작 후 4시간
* `M6h`  : 시작 후 6시간
* `M8h`  : 시작 후 8시간
* `M10h` : 시작 후 10시간
* `M12h` : 시작 후 12시간 (최종)

### 6-2. 초기 구간 모니터링 예시 (M5~M1h)

```powershell
# M5
Start-Sleep -Seconds 300
Write-MonitorSnapshot -label "M5"

# M10
Start-Sleep -Seconds 300
Write-MonitorSnapshot -label "M10"

# M30
Start-Sleep -Seconds 1200
Write-MonitorSnapshot -label "M30"

# M1h
Start-Sleep -Seconds 1800
Write-MonitorSnapshot -label "M1h"
```

### 6-3. 장기 구간 모니터링 예시 (M2h~M12h)

```powershell
# M2h
Start-Sleep -Seconds 3600
Write-MonitorSnapshot -label "M2h"

# M4h
Start-Sleep -Seconds 7200
Write-MonitorSnapshot -label "M4h"

# M6h
Start-Sleep -Seconds 7200
Write-MonitorSnapshot -label "M6h"

# M8h
Start-Sleep -Seconds 7200
Write-MonitorSnapshot -label "M8h"

# M10h
Start-Sleep -Seconds 7200
Write-MonitorSnapshot -label "M10h"

# M12h (최종)
Start-Sleep -Seconds 7200
Write-MonitorSnapshot -label "M12h"
```

> 이 구간에서는 **절대 `run_paper.py` 를 새로 실행하지 말고**,
> 오직 `Write-MonitorSnapshot` 만 호출해야 한다.

---

## 7. STEP 5 – 조기 종료 감지 및 디버깅

### 7-1. PAPER 엔진 프로세스 종료 여부 확인

```powershell
Get-Process python -ErrorAction SilentlyContinue | Where-Object {
    $_.Path -like "*future_alarm_bot*"
}
```

* 출력이 없으면 → PAPER 엔진이 종료된 상태 → **디버깅 모드 진입**.

---

### 7-2. Guard / ERROR / Traceback 상세 로그 추출

```powershell
$startText = Get-Content "test_paper_start_time.txt" -Raw
$startTime = Get-Date $startText.Trim()

$logs = Get-Content logs\application.log | Where-Object {
  $_.Length -ge 19 -and
  ($tsStr = $_.Substring(0,19);
   [datetime]::TryParse($tsStr, [ref]([datetime]::MinValue))) -and
  ([datetime]$tsStr -ge $startTime)
}

$guardErrors = $logs | Select-String "Drawdown Guard|Exposure Guard|Extreme Loss Guard|Slippage Guard|Flash-Guard|ERROR|Traceback"

$guardErrors | Select-Object -Last 200 | Out-File "logs\paper_guard_error_snippet.log" -Encoding utf8
```

이 파일을 기준으로:

* 어떤 Guard가 최초로 트리거되었는지,
* 손실률 / 노출도 / 슬리피지 수준,
* 종료 시각과 실제 경과 시간,

등을 **정확히 분석**해서 리포트에 넣어야 한다.

---

## 8. STEP 6 – Scorecard & PHASE16 리포트 업데이트

### 8-1. 최신 run_id 디렉토리 조회

```powershell
$latest = Get-ChildItem "scorecards\paper_phase16" -Directory |
          Sort-Object LastWriteTime -Descending |
          Select-Object -First 1
$latest.Name
```

* 이 값이 `run_id` 가 된다. (예: `20251117_212039_phase16` 등)

---

### 8-2. PHASE16 리포트 생성/업데이트

```powershell
python scripts/generate_phase16_report.py --run-id $latest.Name
```

* 이 명령이 `scorecard.csv` / `scorecard.md` 를 사용해 **기본 분석 리포트**를 만든다.
* 이후 아래 문서를 수동으로/자동으로 업데이트해야 한다:

  * `docs/PHASE16/PHASE16_REAL_PAPER_XXH_REPORT.md`

    * `XXH` 는 실제 duration에 맞게 (1H, 12H, 72H 등) 이름 유지.

리포트에 포함해야 할 내용 예시:

* 실행 모드: REAL PAPER (wall_clock)
* duration: 예) 12h
* 설정 파일: `configs/scalping/real_paper_12h_v3.yml`
* 실행 결과:

  * 실제 실행 시간 (현실 시계 기준)
  * Entry/Closed 개수
  * Winrate, PF, Max DD 등
* Guard 발생 여부:

  * 발생 시: 어떤 Guard, 어떤 수치에서, 언제 종료되었는지
* 최종 판정: PASS / FAIL
* 다음 단계/개선안:

  * Drawdown/Exposure/쿨다운/포지션 수 등 조정 방향

---

## 9. STEP 7 – Git 커밋

```powershell
git add -A
git commit -m "PHASE16: REAL PAPER Xh 실행 + 모니터링 + 리포트 업데이트 (결과: PASS/FAIL, 사유: XXX Guard 등)"
```

* 커밋 메시지에는 최소한:

  * `duration` (예: 12h)
  * `결과(PASS/FAIL)`
  * `주요 원인 (예: Drawdown Guard, Exposure Guard 등)`
    를 포함한다.

---

## 10. Windsurf가 마지막에 출력해야 하는 요약 문장 예시

```text
OK, 다음 작업을 모두 완료했습니다.

1) 기존 프로세스/Redis/Scorecard/logs 완전 초기화
2) REAL PAPER 전용 설정 YAML 생성
3) 새 CMD 창에서 REAL PAPER 실행 (wall_clock 모드)
4) M5~M12h 체크포인트 모니터링 스냅샷 기록
5) 조기 종료 시 Guard/ERROR/Traceback 로그 수집 및 분석
6) 최신 run_id 기준 PHASE16 REAL PAPER 리포트 업데이트
7) Git 커밋 완료

이제 사용자가 Scorecard/리포트/모니터링 로그를 확인하고
다음 튜닝/재실행 여부를 판단할 수 있는 상태입니다.
```

---

> 이 전체 파일을 `docs/PHASE16/PHASE16_REAL_PAPER_PROMPT_TEMPLATE.md` 같은 이름으로 저장해 두면,
> 앞으로는 그냥 **이 템플릿을 복붙해서 duration/설정 파일 이름만 바꾸고 재활용**하면 된다.

```
```
