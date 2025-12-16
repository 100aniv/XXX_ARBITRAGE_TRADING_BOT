# D94: 1h+ Long-run PAPER 안정성 Gate SSOT

**Status:** 🚀 IN PROGRESS
**Date:** 2025-12-16
**Author:** Windsurf AI

---

## 목표 (Objective)

D94는 **1시간+ Long-run PAPER 안정성**을 SSOT Runner로 정의하고, 재현 가능한 Evidence를 생성하여 다음을 달성:

1. **Long-run 안정성 보증**
   - 1h+ PAPER 실행 Crash-free, Error-free 검증
   - 재현 가능한 KPI JSON + 판정 JSON + 로그 tail 생성
   - docs/D94/evidence/에 커밋 가능한 증거 저장

2. **자동화된 판정 규칙**
   - Critical/Semi-Critical/Variable 필드 분리
   - tolerance 기반 판정 (PASS / PASS_WITH_WARNINGS / FAIL)
   - 판정 근거를 decision JSON에 기계적으로 기록

3. **계단식 실행 옵션**
   - Smoke(20m) → Baseline(1h) 자동 진행
   - Smoke FAIL 시 즉시 중단 (리소스 절약)
   - 각 단계별 KPI JSON 저장

---

## Acceptance Criteria (AC)

### AC-1: 루트 스캔 및 재사용 설계 ✅ COMPLETE
- [x] 기존 Gate/Runner 패턴 스캔 완료
- [x] 재사용 근거 문서화

**재사용 설계**:
1. **run_gate_10m_ssot_v3_2.py** (Gate wrapper 패턴)
   - Secrets check 통합
   - KPI JSON 생성 (logs/gate_10m/gate_10m_YYYYMMDD_HHMMSS/gate_10m_kpi.json)
   - subprocess로 PAPER runner 호출
   - Exit code 0/2 정책

2. **run_d93_gate_reproducibility.py** (판정 로직)
   - Critical/Semi-Critical/Variable 필드 분류
   - tolerance 기반 판정
   - Evidence 폴더 복사 (docs/D93/evidence/)
   - decision JSON 생성

3. **run_d77_0_topn_arbitrage_paper.py** (PAPER 실행 엔트리포인트)
   - --universe top20/top50
   - --run-duration-seconds (600초 기본, 확장 가능)
   - --data-source real
   - --monitoring-enabled
   - --validation-profile none (Gate는 안정성 검증, Win Rate 제외)

### AC-2: D94 SSOT Runner 구현
- [ ] scripts/run_d94_longrun_paper_gate.py 작성
- [ ] 입력 파라미터:
  - --duration-sec (기본 3600)
  - --smoke (true면 1200초 먼저 실행)
  - --log-tail-lines (기본 200)
  - --out-dir (기본: docs/D94/evidence)
- [ ] subprocess로 run_d77_0_topn_arbitrage_paper.py 호출
- [ ] KPI JSON 포맷: 기존 gate_10m_kpi.json + D94 메타 필드

### AC-3: Evidence 파일 생성
- [ ] docs/D94/evidence/d94_1h_kpi.json (1h 실행 KPI)
- [ ] docs/D94/evidence/d94_decision.json (판정 결과)
- [ ] docs/D94/evidence/d94_log_tail.txt (로그 tail + 에러카운트)
- [ ] docs/D94/evidence/d94_smoke_kpi.json (Smoke 실행 시)

### AC-4: 판정 규칙 자동화
- [ ] Critical 필드 (FAIL 즉시):
  - exit_code != 0
  - KPI JSON 누락/파싱 실패
  - duration < (target - 60s)
- [ ] Semi-Critical 필드 (tolerance):
  - round_trips_count >= 1 (0이면 FAIL)
  - 에러 카운트 기준치 초과 시 PASS_WITH_WARNINGS
- [ ] Variable 필드 (참고용):
  - pnl_usd, 체결 수 변동
- [ ] decision JSON 필드:
  - decision: "PASS" | "PASS_WITH_WARNINGS" | "FAIL"
  - reasons: [...]
  - tolerances: {...}
  - critical_checks: {...}
  - semi_checks: {...}

### AC-5: Fast Gate 5종 + Core Regression
- [ ] Fast Gate 5종 100% PASS
- [ ] Core Regression 44 tests 100% PASS

### AC-6: D94 1h 실행 및 증거
- [ ] 1h PAPER 실행 완료 (exit_code=0)
- [ ] Evidence 파일 3~4종 생성 확인
- [ ] decision: PASS 또는 PASS_WITH_WARNINGS

### AC-7: 문서화
- [ ] docs/D94/D94_0_OBJECTIVE.md (본 문서)
- [ ] docs/D94/D94_1_LONGRUN_PAPER_REPORT.md (실행 결과)
- [ ] D_ROADMAP.md D94 섹션 업데이트

### AC-8: Git
- [ ] git status clean
- [ ] 의미 있는 커밋 1개
- [ ] push 완료

---

## 산출물 (Deliverables)

### 1. 문서
- `docs/D94/D94_0_OBJECTIVE.md` (본 문서)
- `docs/D94/D94_1_LONGRUN_PAPER_REPORT.md` (최종 보고서)

### 2. 스크립트
- `scripts/run_d94_longrun_paper_gate.py` (D94 SSOT Runner)

### 3. 증거 파일 (Evidence)
- `docs/D94/evidence/d94_1h_kpi.json` (1h 실행 KPI)
- `docs/D94/evidence/d94_decision.json` (판정 결과)
- `docs/D94/evidence/d94_log_tail.txt` (로그 tail + 에러카운트)
- `docs/D94/evidence/d94_smoke_kpi.json` (Smoke 실행 시)

---

## 실행 커맨드 (Commands)

### 1h Baseline (기본)
```bash
python scripts/run_d94_longrun_paper_gate.py --duration-sec 3600
```

### Smoke(20m) + 1h 계단식
```bash
python scripts/run_d94_longrun_paper_gate.py --smoke --duration-sec 3600
```

### 커스텀 duration
```bash
python scripts/run_d94_longrun_paper_gate.py --duration-sec 7200  # 2h
```

---

## 판정 규칙 (Judgment Rules)

### Critical 필드 (완전 일치 요구)
| 필드 | 조건 | FAIL 시 |
|------|------|---------|
| exit_code | == 0 | 즉시 FAIL |
| KPI JSON | 존재 및 파싱 성공 | 즉시 FAIL |
| duration | >= (target - 60s) | 즉시 FAIL |

### Semi-Critical 필드 (tolerance 허용)
| 필드 | 조건 | tolerance | FAIL/WARN |
|------|------|-----------|-----------|
| round_trips_count | >= 1 | 없음 | 0이면 FAIL |
| error_count | 로그 ERROR/Traceback | <= 10 | 초과 시 WARN |

### Variable 필드 (참고용)
- pnl_usd: 시장 종속, 비교 불가
- entry_trades, exit_trades: 변동 가능
- avg_loop_latency_ms: 참고

### Exit Code 규칙
- 0: PASS 또는 PASS_WITH_WARNINGS
- 2: FAIL

---

## 다음 단계 (Next Steps)

D94 완료 후:
- **D95**: Multi-Symbol TopN 확장 (Top50+ 동시 실행)
- **D96**: Production Readiness Checklist
- **D97**: Real Market Data 기반 Exit 신호

---

## 참고 (References)

- D93 재현성 검증: `docs/D93/D93_1_REPRODUCIBILITY_REPORT.md`
- Gate 10m SSOT: `scripts/run_gate_10m_ssot_v3_2.py`
- PAPER Runner: `scripts/run_d77_0_topn_arbitrage_paper.py`
- Core Regression: `docs/D92/D92_CORE_REGRESSION_DEFINITION.md`
