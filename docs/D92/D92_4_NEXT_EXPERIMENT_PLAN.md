# D92-4 다음 실험 플랜 (Next Experiment Plan)

**작성일:** 2025-12-12 18:50 KST  
**목적:** Threshold 재조정 후 60분 재검증 (팩트 기반 실험 설계)  
**상태:** 📋 READY TO EXECUTE

---

## 🎯 실험 목적

**현재 문제:**
- Threshold 6.0 bps > p95 (4.82 bps) → 진입률 너무 낮음 (1.04%)
- 60분에 11 RT만 발생 → 통계적 유의성 부족
- 모든 Exit가 TIME_LIMIT → TP/SL 미작동

**목표:**
- Threshold를 p95 근처로 하향 조정하여 진입률 증가 (5-10% 목표)
- TP/SL 트리거 비율 측정 (현재 0% 개선)
- PnL 정산 로직 검증 (Quantity 과대 여부 확인)

---

## 🧪 실험 설계

### Phase 1: Threshold 후보 테스트 (3개 후보)

| Threshold | 근거 | 예상 ge_rate | 예상 RT/60m |
|-----------|------|--------------|-------------|
| **5.0 bps** | p95 (4.82) + 안전 마진 0.18 | 3-5% | 30-50 |
| **4.8 bps** | p95 직접 적용 | 5-7% | 50-70 |
| **4.5 bps** | p90 (4.52) 근처 | 8-10% | 80-100 |

**실행 순서:**
1. 5.0 bps: 10m smoke → 60m base
2. 4.8 bps: 10m smoke → 60m base (5.0 결과에 따라 결정)
3. 4.5 bps: 10m smoke만 (너무 공격적이면 60m 스킵)

---

### Phase 2: TP/SL Threshold 점검 (병행)

**현재 상태 (추정):**
- TP threshold: 미설정 또는 매우 높음 (>10 bps?)
- SL threshold: 미설정 또는 매우 깊음 (<-50 bps?)
- TIME_LIMIT: 3분 (기본값)

**점검 사항:**
```yaml
# configs/paper/topn_arb_baseline.yaml 확인
exit_strategy:
  take_profit_bps: ???  # 현재 값 확인
  stop_loss_bps: ???    # 현재 값 확인
  time_limit_seconds: 180  # 3분 확인
```

**조정 후보 (실험 후 결정):**
- TP: 2.0-3.0 bps (entry spread의 30-50%)
- SL: -3.0 bps (entry spread와 동일)
- TIME_LIMIT: 그대로 180s

---

### Phase 3: Quantity 검증 (코드 확인)

**의문점:**
- 평균 손실 -$3,654.5/RT → 73 BTC/RT 추정 (비현실적)
- Paper mode에서 과도한 수량 설정 가능성

**확인 사항:**
```python
# configs/paper/topn_arb_baseline.yaml
trading:
  quantity_per_trade: ???  # BTC 기준 수량
  notional_per_trade: ???  # USD 기준 명목가
  # 어느 것이 사용되는지 확인
```

**권장 값 (Paper mode):**
- Quantity: 0.01 BTC/trade (~$1,000 notional)
- 또는 Notional: $1,000-$5,000/trade

---

## 📋 실행 체크리스트

### Pre-Execution (각 실행 전 필수)

#### 1. 환경 준비
```powershell
# venv 활성화
.\abt_bot_env\Scripts\Activate.ps1

# Docker 확인
docker ps | Select-String "redis|postgres"

# Redis 초기화
docker exec -it arbitrage-redis redis-cli FLUSHALL

# DB 상태 확인 (필요 시 초기화)
# (scripts/prepare_d92_1_env.py 활용)

# Python 프로세스 정리
Get-Process python | Where-Object {$_.MainWindowTitle -notlike "*launcher*"} | Stop-Process -Force
```

#### 2. Config 업데이트
```powershell
# config/arbitrage/zone_profiles_v2.yaml 수정
# BTC의 zone_boundaries[0][1] 값 변경
#   - 5.0 bps 실험: 2.0 ~ 5.0
#   - 4.8 bps 실험: 2.0 ~ 4.8
#   - 4.5 bps 실험: 2.0 ~ 4.5
```

#### 3. Log 경로 준비
```powershell
# logs/d92-4/ 디렉토리 생성
New-Item -Path "logs/d92-4" -ItemType Directory -Force
```

---

### Execution (10m smoke)

```powershell
# 예시: 5.0 bps threshold
python scripts/run_d92_1_topn_longrun.py `
  --top-n 10 `
  --duration-minutes 10 `
  --dry-run false `
  2>&1 | Tee-Object -FilePath "logs/d92-4/d92_4_smoke_10m_t5.0.log"
```

**모니터링 (실행 중):**
- Iteration 수 (400개 예상, 10분 / 1.5s)
- Entry count (5% × 400 = 20개 목표)
- Spread checks (BTC만 ~ 100-120개)

**중단 조건:**
- Entry 0건 (2분 경과 시)
- Crash/Exception
- CPU > 90% 지속

**PASS 기준:**
- Entry ≥ 1
- Exit ≥ 1
- No crash
- Duration 10분 ± 5초

---

### Execution (60m base)

```powershell
# 예시: 5.0 bps threshold (smoke PASS 후)
python scripts/run_d92_1_topn_longrun.py `
  --top-n 10 `
  --duration-minutes 60 `
  --dry-run false `
  2>&1 | Tee-Object -FilePath "logs/d92-4/d92_4_60m_t5.0.log"
```

**모니터링 (실행 중, 10분마다 체크):**
- Entry count 진행률
- RT count (TP/SL/TIME_LIMIT 비율)
- PnL 누적 추이

**중단 조건:**
- Crash/Exception
- Guard trigger > 0
- Memory > 500MB

**PASS 기준:**
- Duration 60분 ± 5초
- Entry ≥ 20 (ge_rate ≥ 3%)
- RT ≥ 10
- No crash

---

### Post-Execution (각 실행 후 필수)

#### 1. KPI 수집
```powershell
# KPI summary JSON 확인
Get-Content "logs/d77-0/*_kpi_summary.json" | ConvertFrom-Json

# Telemetry report JSON 확인
Get-Content "logs/d92-2/*/d92_2_spread_report.json" | ConvertFrom-Json
```

**수집 항목:**
- `total_trades`, `round_trips_completed`
- `total_pnl_usd`, `wins`, `losses`, `win_rate_pct`
- `exit_reasons` (TP/SL/TIME_LIMIT 비율)
- `ge_rate`, `p50/p90/p95/max` (Telemetry)

#### 2. 비교 분석
| Metric | D92-3 (6.0 bps) | D92-4a (5.0 bps) | D92-4b (4.8 bps) |
|--------|-----------------|------------------|------------------|
| Duration | 60.01m | ??? | ??? |
| GE Rate | 1.04% | ??? | ??? |
| Entry | 11 | ??? | ??? |
| RT | 11 | ??? | ??? |
| PnL | -$40,200 | ??? | ??? |
| TP Exits | 0 | ??? | ??? |
| SL Exits | 0 | ??? | ??? |
| TIME_LIMIT | 11 | ??? | ??? |

#### 3. 판정 기준
**성공 (GO):**
- ge_rate 3-7% 달성
- TP 또는 SL 트리거 ≥ 1
- PnL 정산 논리적 (Quantity 정상 확인)

**조건부 성공 (CONDITIONAL GO):**
- ge_rate < 3% (여전히 낮음) → 4.5 bps 추가 실험
- PnL 정산 의심스러움 → 코드 리뷰 필요

**실패 (NO-GO):**
- Entry 0건 (smoke에서도)
- Crash/Exception
- PnL 계산 버그 확정

---

## 📊 예상 결과 (시나리오)

### 시나리오 A: Threshold 5.0 bps 성공
```
GE Rate: 4.5% (목표 달성)
Entry: 45개 (60분)
RT: 30개
PnL: -$5,000 (개선, Quantity 정상화 가정)
TP Exits: 5개 (16.7%)
SL Exits: 2개 (6.7%)
TIME_LIMIT: 23개 (76.7%)

판정: ✅ GO (프로덕션 준비)
다음: D92-5 (RiskGuard Zone-Aware 통합)
```

### 시나리오 B: Threshold 5.0 bps 여전히 낮음
```
GE Rate: 2.0% (미달)
Entry: 20개
RT: 12개
PnL: -$18,000 (개선 미미)
TP Exits: 0
TIME_LIMIT: 12개 (100%)

판정: ⚠️ CONDITIONAL GO
다음: 4.8 bps 또는 4.5 bps 추가 실험
```

### 시나리오 C: Quantity 버그 확정
```
GE Rate: 4.5% (정상)
Entry: 45개
RT: 30개
PnL: -$120,000 (악화, 비논리적)
Quantity/RT: 200 BTC (명백한 버그)

판정: ❌ NO-GO
다음: executor.py 코드 리뷰 및 버그 수정
```

---

## 🛠️ Config 변경 예시

### config/arbitrage/zone_profiles_v2.yaml

#### 현재 (D92-3)
```yaml
symbols:
  BTC:
    default_profiles:
      - advisory_z2_focus
    zone_boundaries:
      - [2.0, 4.0]   # Zone 2
      - [4.0, 6.0]   # Zone 3
      - [6.0, 20.0]  # Zone 4  ← threshold = 6.0 bps
    notes: "D92-2 Calibrated - threshold 6.0 bps"
```

#### D92-4a (5.0 bps)
```yaml
symbols:
  BTC:
    default_profiles:
      - advisory_z2_focus
    zone_boundaries:
      - [2.0, 4.0]   # Zone 2
      - [4.0, 5.0]   # Zone 3 (축소)
      - [5.0, 20.0]  # Zone 4  ← threshold = 5.0 bps
    notes: "D92-4 Re-tuning - threshold 5.0 bps (p95=4.82 + margin)"
```

#### D92-4b (4.8 bps)
```yaml
symbols:
  BTC:
    default_profiles:
      - advisory_z2_focus
    zone_boundaries:
      - [2.0, 4.0]   # Zone 2
      - [4.0, 4.8]   # Zone 3 (축소)
      - [4.8, 20.0]  # Zone 4  ← threshold = 4.8 bps (p95 직접)
    notes: "D92-4 Re-tuning - threshold 4.8 bps (p95 exact)"
```

---

## 📝 실행 명령어 요약

### 1. 환경 준비 (1회만)
```powershell
.\abt_bot_env\Scripts\Activate.ps1
docker exec -it arbitrage-redis redis-cli FLUSHALL
Get-Process python | Where-Object {$_.MainWindowTitle -notlike "*launcher*"} | Stop-Process -Force
```

### 2. Config 수정
```powershell
# zone_profiles_v2.yaml 편집 (VSCode 등)
# BTC zone_boundaries 수정 → Git add (commit은 실험 후)
```

### 3. Smoke Test (10분)
```powershell
python scripts/run_d92_1_topn_longrun.py --top-n 10 --duration-minutes 10 --dry-run false `
  2>&1 | Tee-Object -FilePath "logs/d92-4/smoke_10m_t5.0.log"
```

### 4. Base Run (60분, smoke PASS 시)
```powershell
python scripts/run_d92_1_topn_longrun.py --top-n 10 --duration-minutes 60 --dry-run false `
  2>&1 | Tee-Object -FilePath "logs/d92-4/base_60m_t5.0.log"
```

### 5. 결과 수집
```powershell
# KPI + Telemetry JSON 확인
Get-Content logs/d77-0/*_kpi_summary.json | ConvertFrom-Json | Select total_trades, round_trips_completed, total_pnl_usd, exit_reasons
Get-Content logs/d92-2/*/d92_2_spread_report.json | ConvertFrom-Json | Select -ExpandProperty symbols | Select -ExpandProperty "BTC/KRW"
```

---

## 🎯 성공 기준 (Acceptance Criteria)

### AC1: 진입률 개선
- **Target:** ge_rate ≥ 3% (D92-3 1.04%에서 3배 증가)
- **Measure:** Telemetry report의 `ge_rate` 필드
- **PASS:** 3-7% 범위 (너무 높으면 quality 저하)

### AC2: TP/SL 작동 확인
- **Target:** TP or SL exits ≥ 1
- **Measure:** KPI summary의 `exit_reasons` 필드
- **PASS:** `take_profit` > 0 OR `stop_loss` > 0

### AC3: PnL 정산 논리성
- **Target:** PnL이 ge_rate/RT 증가와 비례
- **Measure:** `total_pnl_usd` / `round_trips_completed`
- **PASS:** Per RT loss가 -$3,654.5에서 감소 OR Quantity 정상 확인

### AC4: 실행 안정성
- **Target:** 60분 완주, No crash
- **Measure:** `actual_duration_minutes` ≥ 59.9
- **PASS:** 100% completion, exit code 0

### AC5: Telemetry 완전성
- **Target:** p50/p90/p95/max/ge_rate 전부 수집
- **Measure:** Telemetry JSON 필드 존재
- **PASS:** 모든 필드 not null

---

## 🚀 다음 액션 (Immediate)

1. **Config 수정**
   - `config/arbitrage/zone_profiles_v2.yaml` BTC threshold → 5.0 bps
   - Git add (commit은 실험 후)

2. **Smoke Test 실행**
   - 10분 실행
   - Entry ≥ 1 확인

3. **Base Run 실행 (smoke PASS 시)**
   - 60분 실행
   - 실시간 모니터링 (10분마다)

4. **결과 분석**
   - KPI/Telemetry 수집
   - 시나리오 A/B/C 판정

5. **리포트 작성**
   - `docs/D92/D92_4_RETUNING_REPORT.md`
   - 다음 threshold 결정 (4.8/4.5 bps 또는 종료)

---

## 📌 Summary

**현재 상태:** D92-3 완료 (threshold 6.0 bps, ge_rate 1.04%, 11 RT)  
**다음 목표:** Threshold 하향 → 진입률 3-7% 달성  
**실험 방법:** 5.0 / 4.8 / 4.5 bps 순차 테스트 (10m smoke + 60m base)  
**성공 기준:** ge_rate ≥ 3%, TP/SL ≥ 1, PnL 논리적, 60분 완주  
**판정 후 액션:** GO (D92-5), CONDITIONAL GO (추가 실험), NO-GO (버그 수정)

**실행 준비:** ✅ READY (Config 수정만 필요)  
**예상 소요:** 10m smoke + 60m base = 70분/threshold  
**최대 소요:** 70분 × 3 thresholds = 3.5시간 (worst case)

---

**작성자:** Windsurf AI  
**상태:** 📋 READY TO EXECUTE  
**버전:** 1.0
