# D87-3: FillModel Advisory vs Strict Long-run PAPER A/B - 실행 가이드

**작성일:** 2025-12-07  
**상태:** 🚀 **READY TO RUN** (모든 준비 완료)

## 목표

D87-1 Advisory Mode와 D87-2 Strict Mode의 **실제 효과를 3시간씩 장기 PAPER 실행으로 검증**.

**핵심 검증 사항:**
- Strict 모드가 Z2 Zone에 **정말로 더 집중**하는가?
- Z1/Z3/Z4 비중이 **정말로 감소**하는가?
- Z2 평균 포지션 사이즈가 **정말로 증가**(1.2배)하는가?
- PnL과 Risk 관점에서 **의미 있는 개선**인가, **과도한 집중**인가?

---

## 실행 환경

### 필수 조건

1. **가상환경 활성화**
   ```powershell
   cd "C:\Users\bback\Desktop\부업\9) 코인 자동매매\arbitrage-lite"
   abt_bot_env\Scripts\activate
   ```

2. **Docker 컨테이너 확인**
   - Redis: 포트 6379
   - PostgreSQL: 포트 5432
   
   ```powershell
   docker ps
   ```

3. **프로세스 정리** (중복 실행 방지)
   ```powershell
   # 기존 실행 중인 python arbitrage 프로세스 확인
   Get-Process | Where-Object {$_.ProcessName -like "*python*"}
   
   # 필요시 kill (ID는 실제 확인 후 사용)
   # Stop-Process -Id <PID>
   ```

### 실행 파라미터

| 파라미터 | Advisory | Strict |
|----------|----------|--------|
| `--duration-seconds` | 10800 (3h) | 10800 (3h) |
| `--l2-source` | real | real |
| `--fillmodel-mode` | **advisory** | **strict** |
| `--calibration-path` | logs/d86-1/calibration_20251207_123906.json | logs/d86-1/calibration_20251207_123906.json |
| `--session-tag` | d87_3_advisory_3h | d87_3_strict_3h |

---

## 실행 명령어

### Step 1: Advisory 모드 3시간 실행

**명령어:**
```powershell
python scripts/run_d84_2_calibrated_fill_paper.py ^
    --duration-seconds 10800 ^
    --l2-source real ^
    --fillmodel-mode advisory ^
    --calibration-path logs/d86-1/calibration_20251207_123906.json ^
    --session-tag d87_3_advisory_3h
```

**예상 출력:**
- **로그 디렉토리:** `logs/d87-3/d87_3_advisory_3h/`
- **Fill Events:** `fill_events_YYYYMMDD_HHMMSS.jsonl`
- **KPI:** `kpi_YYYYMMDD_HHMMSS.json`

**모니터링 체크리스트:**
- [ ] WebSocket 연결 성공 (Upbit L2)
- [ ] 초반 5-10분: 트레이드 정상 발생
- [ ] 30분마다: 로그 확인, 에러 없음
- [ ] 3시간 완료 후: Fill Events 1000개 이상 확보 목표

**완료 후 대기 시간:** 10분 (안정화)

---

### Step 2: Strict 모드 3시간 실행

**명령어:**
```powershell
python scripts/run_d84_2_calibrated_fill_paper.py ^
    --duration-seconds 10800 ^
    --l2-source real ^
    --fillmodel-mode strict ^
    --calibration-path logs/d86-1/calibration_20251207_123906.json ^
    --session-tag d87_3_strict_3h
```

**예상 출력:**
- **로그 디렉토리:** `logs/d87-3/d87_3_strict_3h/`
- **Fill Events:** `fill_events_YYYYMMDD_HHMMSS.jsonl`
- **KPI:** `kpi_YYYYMMDD_HHMMSS.json`

**모니터링 체크리스트:**
- [ ] WebSocket 연결 성공
- [ ] 초반 5-10분: Strict 모드 로그에서 "strict" 키워드 확인
- [ ] Z2 집중 경향 초기 확인 (로그에서 Zone 정보 체크)
- [ ] 30분마다: 로그 확인
- [ ] 3시간 완료 후: Fill Events 1000개 이상 확보 목표

---

## Step 3: A/B 분석

**명령어:**
```powershell
python scripts/analyze_d87_3_fillmodel_ab_test.py ^
    --advisory-dir logs/d87-3/d87_3_advisory_3h ^
    --strict-dir logs/d87-3/d87_3_strict_3h ^
    --output logs/d87-3/d87_3_ab_summary.json
```

**출력:**
- **JSON 요약:** `logs/d87-3/d87_3_ab_summary.json`
- **콘솔 출력:** Zone별 비교 테이블, 핵심 결론

**분석 결과 해석:**
- **Z2 비중:** Strict > Advisory (목표: +10%p 이상)
- **Z1/Z3/Z4 비중:** Strict < Advisory (목표: -5%p 이상)
- **총 트레이드 수:** Strict < Advisory (예상: -10~-20%, Z2 집중으로 인한 선택성 증가)
- **Z2 평균 사이즈:** Strict > Advisory (목표: +9% = 1.1→1.2배 차이)

---

## Acceptance Criteria

### C1: 완주 (Critical)
- [ ] Advisory 3h 오류 없이 완료
- [ ] Strict 3h 오류 없이 완료
- [ ] WebSocket 재연결 < 5회/세션

### C2: 데이터 충분성 (Critical)
- [ ] Advisory Fill Events ≥ 1000개
- [ ] Strict Fill Events ≥ 1000개
- [ ] Entry Trades ≥ 500개/세션

### C3: Z2 집중 효과 (Critical)
- [ ] Strict Z2 비중 > Advisory Z2 비중 (Trades 기준 +10%p 이상)
- [ ] Strict Z2 비중 > Advisory Z2 비중 (Notional 기준 +10%p 이상)

### C4: Z1/Z3/Z4 회피 효과 (High Priority)
- [ ] Strict Z1+Z3+Z4 비중 < Advisory Z1+Z3+Z4 비중 (-5%p 이상)

### C5: Z2 포지션 사이즈 증가 (High Priority)
- [ ] Strict Z2 평균 사이즈 > Advisory Z2 평균 사이즈 (+5% 이상)

### C6: 리스크 균형 (Medium Priority)
- [ ] Strict 총 PnL ≈ Advisory 총 PnL (±20% 이내)
- [ ] Strict Max DD ≈ Advisory Max DD (±30% 이내)
- [ ] Strict가 과도하게 위험하지 않음 (정성적 평가)

---

## 예상 실행 시간

- **Advisory 3h:** 10800초 (3시간)
- **Strict 3h:** 10800초 (3시간)
- **분석:** 2-3분
- **총 소요 시간:** 약 6시간 5분

**권장 실행 시간:**
- 밤 11시 ~ 오전 5시 (자는 동안)
- 주말 오전 (모니터링 가능한 시간대)

---

## 트러블슈팅

### 1. WebSocket 연결 실패
**증상:** "No snapshot received after 10s" 경고
**대응:**
- Upbit API 상태 확인 (https://status.upbit.com/)
- 네트워크 연결 확인
- 재실행 (자동 재연결 로직 있음)

### 2. Fill Events 0개
**증상:** JSONL 파일이 비어 있음
**대응:**
- FillEventCollector 활성화 확인 (`enabled=True`)
- Executor 로그 확인 (`execute_trades` 호출 여부)
- Mock Trade 생성 주기 확인 (10초마다 1회)

### 3. 메모리 부족
**증상:** Python 프로세스 OOM
**대응:**
- 불필요한 로그 레벨 낮추기 (`logging.WARNING`)
- L2 스냅샷 버퍼 크기 제한 (최대 1000개)
- OS 메모리 확인 (최소 4GB 권장)

### 4. 중간 중단
**증상:** 실행 도중 프로세스 종료
**대응:**
- 에러 로그 확인 (`logs/` 디렉토리)
- 부분 데이터라도 분석 가능 (duration < 3h)
- 재실행 시 `--session-tag`를 다르게 설정하여 데이터 덮어쓰기 방지

---

## 리포트 작성

분석 완료 후 `docs/D87/D87_3_FILLMODEL_ADVISORY_VS_STRICT_LONGRUN_PAPER_REPORT.md`를 작성해야 합니다.

**리포트 템플릿:** (별도 파일 참조)
- 실행 개요
- 실행 로그 요약
- Zone별 통계
- A/B 결과
- Risk & Limitation
- 결론 및 TO-BE

---

## Next Steps

D87-3 완료 후:
- **D87-4:** RiskGuard/Alerting 통합 (Risk-aware Fill Model)
- **D9x:** Symbol별 Calibration, Auto Re-calibration
- **Production:** Strict Mode 파라미터 튜닝 및 실전 적용

---

## 요약

**준비 완료:**
- ✅ Runner 스크립트 확장 (fillmodel-mode, session-tag 지원)
- ✅ 분석 스크립트 작성 (A/B 비교)
- ✅ 실행 가이드 작성
- ✅ 3시간 실행 명령어 준비

**실행 시작:**
```powershell
# Advisory 3h
python scripts/run_d84_2_calibrated_fill_paper.py --duration-seconds 10800 --l2-source real --fillmodel-mode advisory --calibration-path logs/d86-1/calibration_20251207_123906.json --session-tag d87_3_advisory_3h

# Strict 3h (Advisory 완료 후)
python scripts/run_d84_2_calibrated_fill_paper.py --duration-seconds 10800 --l2-source real --fillmodel-mode strict --calibration-path logs/d86-1/calibration_20251207_123906.json --session-tag d87_3_strict_3h

# 분석
python scripts/analyze_d87_3_fillmodel_ab_test.py --advisory-dir logs/d87-3/d87_3_advisory_3h --strict-dir logs/d87-3/d87_3_strict_3h --output logs/d87-3/d87_3_ab_summary.json
```

**🚀 모든 준비 완료. 실행만 시작하면 됩니다!**
