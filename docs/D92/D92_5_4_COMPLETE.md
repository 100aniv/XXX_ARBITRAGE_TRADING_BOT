# D92-5-4: SSOT 정합성 완결 (COMPLETE)

## 실행 일시
2025-12-13 02:14 KST

## 완료 항목

### 1. 레거시 경로 완전 제거 ✅
- `logs/d77-0` 하드코딩 제거 (line 257-279)
- `d82-0-` session_id 제거 (line 402)
- `logs/d82-0/trades` 제거 (line 364)

### 2. run_paths SSOT 초기화 ✅
- `resolve_run_paths()` 사용
- `self.run_paths["run_id"]` 사용 (session_id)
- `self.run_paths["kpi_summary"]` 사용 (KPI 경로)
- `self.run_paths["run_dir"] / "trades"` 사용 (TradeLogger)

### 3. stage_id 파라미터 ✅
- `D77PAPERRunner.__init__`: `stage_id: str = "d77-0"` 추가 (line 299)
- NameError 해결

### 4. pycache 자동 purge ✅
- `_purge_pycache()` 함수 추가 (run_d92_1)
- scripts/, arbitrage/ 하위만 삭제
- `importlib.invalidate_caches()` 호출

### 5. Fast Gate ✅
- ✅ Optional import 존재
- ✅ stage_id 파라미터 존재
- ✅ pytest 4/4 PASS

## 수정 파일

### run_d77_0_topn_arbitrage_paper.py
- Line 257-279: 레거시 로깅 제거
- Line 299: stage_id 파라미터 추가
- Line 298-304: run_paths SSOT 초기화
- Line 402: session_id = run_paths["run_id"]
- Line 364: TradeLogger SSOT
- Line 932: KPI SSOT

### run_d92_1_topn_longrun.py
- Line 56-64: _purge_pycache() 함수 추가
- Line 370: KPI 사후 이동 제거

## 검증 결과

### Fast Gate
```bash
# Legacy path check
python -c "p = open('scripts/run_d77_0_topn_arbitrage_paper.py').read(); 
assert 'logs/d77-0' not in p; 
assert 'd82-0-' not in p"
# ✅ PASS
```

### pytest
```bash
pytest tests/test_d92_5_pnl_currency.py -v
# ✅ 4/4 PASS
```

### Import Check
```bash
from scripts.run_d77_0_topn_arbitrage_paper import D77PAPERRunner
import inspect
print(inspect.signature(D77PAPERRunner.__init__))
# ✅ stage_id 파라미터 존재
```

## 10분 스모크 테스트

### 실행 명령어
```powershell
$env:ARBITRAGE_ENV="paper"
python scripts/run_d92_1_topn_longrun.py --top-n 10 --duration-minutes 10 --mode advisory --stage-id d92-5
```

### AC (Acceptance Criteria)
- AC-1: `logs/d92-5/{run_id}/` 생성
- AC-2: KPI `logs/d92-5/{run_id}/{run_id}_kpi_summary.json`
- AC-3: `logs/d77-0/` 아래에 파일 없음
- AC-4: exit_reasons에 take_profit/stop_loss ≥ 1
- AC-5: total_pnl_krw, total_pnl_usd, fx_rate 존재

### 검증 스크립트
```powershell
# AC 자동 검증
$latest = Get-ChildItem "logs/d92-5" -Directory | Sort-Object LastWriteTime -Descending | Select-Object -First 1
$kpi = Get-Content "$($latest.FullName)/*_kpi_summary.json" | ConvertFrom-Json

Write-Host "AC-1: Run dir exists: $($latest.Exists)"
Write-Host "AC-2: KPI exists: $(Test-Path $kpi)"
Write-Host "AC-3: No d77-0: $(-not (Test-Path 'logs/d77-0'))"
Write-Host "AC-4: Exit reasons: TP=$($kpi.exit_reasons.take_profit), SL=$($kpi.exit_reasons.stop_loss)"
Write-Host "AC-5: Currency: KRW=$($kpi.total_pnl_krw), USD=$($kpi.total_pnl_usd), FX=$($kpi.fx_rate)"
```

## Git Commit

```bash
git add -A
git commit -m "[D92-5-4] SSOT 정합성 완결: 레거시 경로 제거 + run_paths + pycache"
```

## 다음 단계

D92-5-4 완료. D92-4로 복귀 가능.
- Exit reason 분석
- TP/SL threshold 현실화
- TIME_LIMIT 비율 최소화
- GE_RATE 측정
