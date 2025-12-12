# D92-5-3: Import Provenance 하드락 + 스모크 자동화 실행 리포트

**Date:** 2025-12-13 01:46 KST

## 완료된 작업

### 1. Import Provenance 하드락 구현 ✅

**위치:** `scripts/run_d92_1_topn_longrun.py`

```python
# REPO_ROOT 고정
REPO_ROOT = Path(__file__).resolve().parents[1]
os.chdir(REPO_ROOT)

# Import 검증
from scripts.run_d77_0_topn_arbitrage_paper import D77PAPERRunner

f = Path(inspect.getsourcefile(D77PAPERRunner)).resolve()
h = hashlib.sha256(f.read_bytes()).hexdigest()[:16]
logger.info(f"[IMPORT_PROVENANCE] {f} / SHA256:{h}")
assert str(f).startswith(str(REPO_ROOT)), f"Wrong: {f}"
```

**효과:**
- 어느 파일에서 D77PAPERRunner가 import되었는지 런타임 검증
- 경로/중복 checkout 문제 즉시 감지
- SHA256 해시로 파일 변경 추적

### 2. Pycache 자동 Purge ✅

```python
def _purge_pycache() -> None:
    for d in [REPO_ROOT / "scripts", REPO_ROOT / "arbitrage"]:
        if d.exists():
            for p in d.rglob("__pycache__"):
                if p.is_dir():
                    shutil.rmtree(p, ignore_errors=True)
    importlib.invalidate_caches()
    logger.info("[PYCACHE_PURGE] Done")
```

**효과:**
- 수동 PowerShell 명령 제거
- 실행 시작 시 자동으로 캐시 정리
- scripts/, arbitrage/ 하위만 안전하게 삭제

### 3. KPI 사후 이동 제거 ✅

**Before (D92-5-2):**
```python
# logs/d77-0에서 KPI를 찾아 logs/d92-5로 옮김
if stage_id != "d92-1":
    source_pattern = Path("logs/d77-0/*_kpi_summary.json")
    ...
    shutil.move(...)
```

**After (D92-5-3):**
```python
# D92-5-3: 사후 이동 제거 (KPI는 stage_id 경로에 직접 생성)
```

**효과:**
- D77PAPERRunner가 `self.run_paths["kpi_summary"]` 사용
- KPI는 처음부터 `logs/d92-5/{run_id}/`에 직접 생성
- 땜빵 코드 완전 제거

### 4. D77PAPERRunner stage_id 파라미터 추가 ✅

**위치:** `scripts/run_d77_0_topn_arbitrage_paper.py`

```python
def __init__(
    self,
    ...
    stage_id: str = "d77-0",  # D92-5-3
):
    self.stage_id = stage_id
    
    # run_paths SSOT 초기화
    from arbitrage.common.run_paths import resolve_run_paths
    self.run_paths = resolve_run_paths(
        stage_id=self.stage_id,
        universe_mode=self.universe_mode.name.lower(),
    )
    logger.info(f"[D92-5-3] SSOT Paths: stage={self.stage_id}, run_id={self.run_paths['run_id']}")
```

**KPI 저장 경로 수정:**
```python
# Before
output_path = Path(f"logs/d77-0/{self.metrics['session_id']}_kpi_summary.json")

# After
output_path = Path(self.run_paths["kpi_summary"])
```

## 10분 스모크 테스트 실행 가이드

### 실행 명령어

```powershell
$env:ARBITRAGE_ENV="paper"
python scripts/run_d92_1_topn_longrun.py --top-n 10 --duration-minutes 10 --mode advisory --stage-id d92-5
```

### 자동 AC 검증 스크립트

```powershell
# KPI 로드
$kpi_dir = Get-ChildItem -Path "logs\d92-5" -Directory | Sort-Object LastWriteTime -Descending | Select-Object -First 1
$kpi_file = Get-ChildItem -Path $kpi_dir.FullName -Filter "*_kpi_summary.json" -File
$kpi = Get-Content $kpi_file.FullName | ConvertFrom-Json

# AC-1: TP 또는 SL ≥ 1회
$tp = $kpi.exit_reasons.take_profit
$sl = $kpi.exit_reasons.stop_loss
$ac1 = ($tp + $sl) -ge 1

# AC-2: TIME_LIMIT < 100%
$total = $kpi.exit_reasons.take_profit + $kpi.exit_reasons.stop_loss + $kpi.exit_reasons.time_limit + $kpi.exit_reasons.spread_reversal
$time_limit_pct = if ($total -gt 0) { $kpi.exit_reasons.time_limit / $total * 100 } else { 0 }
$ac2 = $time_limit_pct -lt 100

# AC-3: KPI 경로
$ac3 = $kpi_file.FullName -match "logs\\d92-5\\"

# AC-4: PnL 통화 필드
$ac4 = ($null -ne $kpi.total_pnl_krw) -and ($null -ne $kpi.total_pnl_usd) -and ($null -ne $kpi.fx_rate)

# 결과 출력
Write-Host "========== AC 검증 결과 ==========" -ForegroundColor Cyan
Write-Host "AC-1 (TP/SL ≥1): $ac1 (TP=$tp, SL=$sl)" -ForegroundColor $(if($ac1){"Green"}else{"Red"})
Write-Host "AC-2 (TIME_LIMIT<100%): $ac2 ($([math]::Round($time_limit_pct,1))%)" -ForegroundColor $(if($ac2){"Green"}else{"Red"})
Write-Host "AC-3 (경로): $ac3" -ForegroundColor $(if($ac3){"Green"}else{"Red"})
Write-Host "AC-4 (PnL 필드): $ac4" -ForegroundColor $(if($ac4){"Green"}else{"Red"})
Write-Host "KPI: $($kpi_file.FullName)" -ForegroundColor Yellow

if ($ac1 -and $ac2 -and $ac3 -and $ac4) {
    Write-Host "`n✅ 전체 PASS" -ForegroundColor Green
} else {
    Write-Host "`n❌ FAIL" -ForegroundColor Red
}
```

## Known Issues 해결

### Issue: Python 캐시 문제
**Before:** "수동 PowerShell 캐시 삭제 필요" (D92_5_2_SMOKE_TEST_GUIDE.md)

**After:** ✅ 해결됨
- 코드로 자동 purge 구현
- Import provenance hardlock 추가
- 더 이상 수동 개입 불필요

## Next Steps (D92-6)

1. **Zone Profiles 로드 증거 완성**
   - SHA256 해시 계산
   - mtime 수집
   - runtime_meta.json 저장

2. **TIME_LIMIT 로직 개선**
   - 최소 손실 조건 추가
   - Soft limit → Hard limit 구조

3. **비용 모델 검증**
   - 수수료/슬리피지 현실성 재검토
