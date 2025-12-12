# D92-5-2: 10분 스모크 테스트 실행 가이드

**Date:** 2025-12-13 01:16 KST

## 실행 명령어

```powershell
# Python 캐시 정리 (중요!)
Get-ChildItem -Path "C:\Users\bback\Desktop\부업\9) 코인 자동매매\arbitrage-lite" -Recurse -Filter "__pycache__" -Directory | Remove-Item -Recurse -Force

# 환경 변수 설정 및 실행
$env:ARBITRAGE_ENV="paper"
python scripts/run_d92_1_topn_longrun.py --top-n 10 --duration-minutes 10 --mode advisory --stage-id d92-5
```

## AC (Acceptance Criteria)

### AC-1: TP/SL 트리거 ≥ 1회
- Exit reason 분포에서 `take_profit` 또는 `stop_loss` ≥ 1회 확인

### AC-2: Exit reason TIME_LIMIT < 100%
- `time_limit` 비율이 100%가 아니어야 함

### AC-3: logs/d92-5/{run_id}/ 구조 생성
- KPI summary 파일 위치: `logs/d92-5/{run_id}/{run_id}_kpi_summary.json`

### AC-4: PnL 통화 SSOT 필드 존재
- `total_pnl_krw`: KRW 단위 PnL
- `total_pnl_usd`: USD 단위 PnL
- `fx_rate`: 환율
- `currency_note`: 통화 설명

### AC-5: 테스트 100% PASS
- `pytest tests/test_d92_5_pnl_currency.py -v` → 4/4 PASS

## 결과 분석

실행 완료 후 다음 명령어로 결과 확인:

```powershell
# KPI summary 조회
$kpi = Get-Content (Get-ChildItem -Path "logs\d92-5" -Recurse -Filter "*_kpi_summary.json" | Sort-Object LastWriteTime -Descending | Select-Object -First 1).FullName | ConvertFrom-Json

# Exit reason 분포
$kpi.exit_reasons

# PnL 통화 필드
$kpi.total_pnl_krw
$kpi.total_pnl_usd
$kpi.fx_rate
$kpi.currency_note
```

## Known Issues

**Python 캐시 문제:**
- `stage_id` 파라미터가 Python 캐시로 인해 런타임에 반영되지 않을 수 있음
- **해결:** 위 명령어에 포함된 캐시 정리 단계 필수 실행

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
