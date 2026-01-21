# Operational Protocol (운영 프로토콜)

**Version:** 1.0  
**Effective Date:** 2026-01-12  
**Status:** ACTIVE  
**Parent Document:** [`SSOT_RULES.md`](SSOT_RULES.md)

**Constitutional Basis:**
> "운영 프로토콜은 OPS_PROTOCOL.md를 따른다. 충돌 시 SSOT_RULES.md가 우선한다."

---

## 1. Document Purpose & Scope

### 1.1 Purpose
이 문서는 **XXX Arbitrage V2 시스템의 운영 프로토콜**을 정의합니다.
- **Run Protocol:** 실행 → 검증 → 종료 시퀀스
- **Exit Code 규약:** WARN = FAIL 원칙
- **Evidence 관리:** 최소셋 정의 + Atomic Flush
- **Healthcheck 연동:** Docker/compose 헬스체크 전략
- **장애 대응:** SIGTERM/Graceful Shutdown + Recovery

### 1.2 Scope
- **대상:** arbitrage/v2/** 모든 실행 모드 (Paper/Live/Smoke/Baseline/Longrun)
- **환경:** 로컬 PC, Docker/compose, CI/CD
- **제외:** V1 레거시 (arbitrage/**, 폐기 예정)

### 1.3 Target Audience
- **개발자:** 새 기능 추가 시 Run Protocol 준수
- **운영자:** 실행/모니터링/장애 대응 절차
- **감사자:** Evidence 검증 및 정합성 확인

---

## 2. Operational Invariants (불변 조건)

> **Invariants:** 이 조건들이 위반되면 시스템은 즉시 종료되어야 합니다 (Exit Code 1).

### 2.1 Wallclock Duration Invariant
- **조건:** 실제 실행 시간(wallclock)과 예상 시간의 차이가 ±5% 이내
- **위반 시:** `orchestrator.run()` 즉시 Exit Code 1 반환
- **근거:** duration_seconds는 wall-clock 기준 (실제 경과 시간)
- **검증:** `abs(actual_duration - expected_duration) <= expected_duration * 0.05`

### 2.2 Heartbeat Density Invariant
- **조건:** heartbeat.jsonl 간격이 65초 이하 (60초 기준 + 5초 버퍼)
- **위반 시:** `orchestrator.run()` 즉시 Exit Code 1 반환
- **근거:** RunWatcher 정상 작동 증명 (모니터링 시스템 연동)
- **검증:** `max_gap_seconds <= 65`

### 2.3 DB Invariant
- **조건:** `closed_trades × 3 ≈ db_inserts_ok` (±2 허용)
- **위반 시:** `orchestrator.run()` 즉시 Exit Code 1 반환
- **근거:** 거래당 order(1) + fill(1) + trade(1) = 3번 DB insert
- **검증:** `abs(db_inserts_ok - closed_trades * 3) <= 2`
- **코드:** `arbitrage/v2/core/orchestrator.py:252-267`

### 2.4 Evidence Completeness Invariant
- **조건:** Evidence Minimum Set 모든 파일 존재
- **위반 시:** `orchestrator.run()` 즉시 Exit Code 1 반환
- **근거:** 감사 추적 및 재현성 확보
- **검증:** 모든 파일 존재 확인 (파일 크기 > 0)

### 2.5 Graceful Shutdown Invariant (F5)
- **조건:** SIGTERM 수신 후 10초 내 Evidence Flush 완료
- **위반 시:** 강제 종료 전 마지막 Evidence 저장 시도
- **근거:** 장애 시에도 증거 보존 필수
- **검증:** `finally` 블록 실행 + 타임아웃 10초
- **코드:** `arbitrage/v2/core/orchestrator.py:79-95` (signal handler)
- **메커니즘:**
  1. `signal.signal(SIGTERM, handler)` 등록
  2. Handler가 `_sigterm_received = True` 설정
  3. 메인 루프 break → Evidence Flush → Exit 1

---

## 2.6 모드별 Invariant (Mode-Specific Invariants)

**원칙:** 실행 환경(BACKTEST/PAPER/LIVE)에 따라 Invariant 적용 범위와 정의가 달라짐

### 2.6.1 PAPER 모드 Invariant

**적용 대상:** `execution.environment = "paper"`

**공통 Invariant (2.1~2.5) 적용:**
- ✅ Wallclock Duration Invariant (±5%)
- ✅ Heartbeat Density Invariant (≤65초)
- ✅ DB Invariant (closed_trades × 3)
- ✅ Evidence Completeness Invariant
- ✅ Graceful Shutdown Invariant

**PAPER 전용 Invariant:**
1. **Real MarketData 필수**
   - 조건: `use_real_data = true` 강제
   - 위반 시: Bootstrap 단계에서 즉시 Exit 1
   - 근거: Mock 데이터는 unit test 전용, PAPER는 상용급 시뮬레이션
   - 검증: Preflight Check에서 config.use_real_data 확인

2. **Slippage/Latency/PartialFill 모델 주입**
   - 조건: `execution.rigor = "ssot"` 시 FillModelConfig 모든 모델 활성화
   - 위반 시: Bootstrap 단계에서 Warning 로그 (강제 Exit는 아님, D206-2에서 강제 예정)
   - 근거: 현실 마찰 모델 없이는 승률 95%+ False Positive 발생
   - 검증: config.execution.rigor == "ssot" → fill_model.enable_slippage/latency/partial_fill == true

3. **승률 경고 기준 (D205-18-4 REAL 검증 기준)**
   - 조건: winrate ≥ 95% → WARNING 로그, edge_after_cost 교차 검증 필수
   - 위반 시: FAIL 아님, WARNING으로 기록 (Report에 분석 필수)
   - 근거: Paper 모드 본질적 한계 (슬리피지 없음, 즉시 체결)
   - 검증: KPI.winrate >= 0.95 → log warning + is_optimistic_warning 플래그 기록

4. **승률 100% Kill-switch (D207-3)**
   - 조건: closed_trades >= 20 AND winrate = 100%
   - 위반 시: ExitCode=1, stop_reason="WIN_RATE_100_SUSPICIOUS"
   - 근거: Mock 데이터 또는 낙관 편향 가능성
   - 검증: RunWatcher가 stop_reason 설정 + snapshot 증거 저장

### 2.6.2 LIVE 모드 Invariant (설계 단계, D206-0~4 구현 예정)

**적용 대상:** `execution.environment = "live"`

**공통 Invariant 변형 적용:**
- ⚠️ Wallclock Duration Invariant: **윈도우 기반 재정의** (무한루프/스케줄러 대응)
  - PAPER: 고정 duration (20m, 60m) → 실제 실행 시간 ±5%
  - LIVE: rolling 1h window → 최근 1시간 이내 heartbeat/trade 존재 검증
  - 조건: 최근 1시간 이내 최소 1개 heartbeat + 최소 1개 trade (또는 opportunity)
  - 위반 시: 1시간 동안 아무 활동 없음 → Exit 1 (market 중단 또는 엔진 정지)
  
- ✅ Heartbeat Density Invariant (≤65초) - 동일
- ✅ DB Invariant (closed_trades × 3) - 동일
- ✅ Evidence Completeness Invariant - 동일
- ✅ Graceful Shutdown Invariant - 동일

**LIVE 전용 Invariant:**
1. **Real-time FX Integration 필수**
   - 조건: `fx_provider.type != "fixed"` 강제
   - 위반 시: Bootstrap 단계에서 즉시 Exit 1 (Fail Fast)
   - 근거: LIVE 모드에서 고정 FX는 실거래 리스크 (D205-15-4)
   - 검증: config.fx_provider.type == "live" or "crypto_implied"

2. **Risk Guard 활성화 필수**
   - 조건: RiskGuard 모듈 활성화 (max_drawdown, max_consecutive_losses 설정)
   - 위반 시: Bootstrap 단계에서 즉시 Exit 1
   - 근거: 실거래 손실 방지 필수 (D206-3)
   - 검증: config.risk_guard.enabled == true

3. **Stop Reason 체계 (D206-3 설계)**
   - NORMAL: 계획 시간 도달 또는 스케줄 완료
   - ERROR_INVARIANT_VIOLATION: Invariant 위반 (Wallclock/Heartbeat/DB/Evidence)
   - MANUAL_HALT: 운영자 수동 중단
   - RISK_DRAWDOWN: 리스크 임계치 초과 (손실 한도, 연속 손실 등)
   - 각 Stop Reason별 Alerting 모듈 Hook 필요

### 2.6.3 BACKTEST 모드 Invariant (계획 단계)

**적용 대상:** `execution.environment = "backtest"`

**공통 Invariant 완화:**
- ⚠️ Wallclock Duration Invariant: **적용 안 함** (시뮬레이션 속도는 가변적)
- ❌ Heartbeat Density Invariant: **적용 안 함** (백테스트는 batch 실행)
- ✅ DB Invariant (closed_trades × 3) - 동일
- ✅ Evidence Completeness Invariant - 동일
- ❌ Graceful Shutdown Invariant: **적용 안 함** (배치 완료 후 종료)

**BACKTEST 전용 Invariant:**
1. **Historical Data 완전성**
   - 조건: 백테스트 기간 내 데이터 결측 ≤ 1% (설정 가능)
   - 위반 시: 경고 로그 (Exit는 아님)
   - 근거: 데이터 결측이 많으면 백테스트 신뢰도 저하
   - 검증: missing_data_ratio < 0.01

2. **재현성 검증**
   - 조건: 동일 입력 데이터 → 동일 결과 (deterministic)
   - 위반 시: 재현성 테스트 FAIL
   - 근거: 백테스트 결과는 재현 가능해야 검증 가능
   - 검증: 2회 실행 결과 diff == 0

---

## 3. Run Protocol (실행 프로토콜)

### 3.1 실행 단계 (Sequential)

#### 3.1.1 Bootstrap (초기화)
1. **Config 로드:** `config/v2/config.yml` 읽기
2. **DB/Redis 연결:** 연결 실패 시 즉시 Exit 1
3. **Preflight Check:** `arbitrage/v2/core/preflight_checker.py` 실행
4. **Run ID 생성:** `d205_18_2d_<phase>_<timestamp>` 포맷
5. **Evidence 디렉토리 생성:** `logs/evidence/<run_id>/`

#### 3.1.2 Execution (실행)
1. **Orchestrator 시작:** `orchestrator.run(duration_minutes, ...)`
2. **RunWatcher 시작:** 60초 heartbeat + FAIL 조건 모니터링
3. **Main Loop:** 기회 탐지 → Intent 변환 → Trade 처리
4. **KPI 수집:** opportunities_generated, closed_trades, net_pnl 등
5. **Evidence 누적:** decision_trace, metrics_snapshot 등

#### 3.1.3 Validation (검증)
1. **Wallclock Duration 검증:** Invariant 2.1 체크
2. **Heartbeat Density 검증:** Invariant 2.2 체크
3. **DB Invariant 검증:** Invariant 2.3 체크
4. **Evidence Completeness 검증:** Invariant 2.4 체크
5. **RunWatcher Stop Reason 확인:** ERROR 시 Exit 1

#### 3.1.4 Termination (종료)
1. **Normal Termination:**
   - 모든 Validation PASS → Evidence 저장 → Exit 0
2. **Abnormal Termination:**
   - Validation FAIL → Evidence 저장 → Exit 1
3. **Forced Termination (SIGTERM):**
   - `finally` 블록 → Atomic Evidence Flush → Exit 1

### 3.2 Exit Code 규약

| Exit Code | 의미 | 조건 |
|-----------|------|------|
| **0** | SUCCESS | 모든 Validation PASS |
| **1** | FAILURE | Invariant 위반, RunWatcher ERROR, Exception 발생 |
| **2** | Reserved | (미사용) |

**#### 2.4 WARN = FAIL Principle (Operational Warnings Only)
- **원칙:** Operational WARNING은 Exit Code 1 (가짜 PASS 차단)
- **범위:** 프리플라이트 체크, 런타임 무결성 검증 (wallclock/heartbeat/DB/evidence)
- **제외:** KPI 경고 (winrate 0%, consecutive losses)는 RunWatcher가 별도 처리
- **금지:** Operational WARNING을 PASS로 간주
- **상세:** [`OPS_PROTOCOL.md#32-exit-code-규약`](OPS_PROTOCOL.md#32-exit-code-규약)

**Operational WARN → FAIL 예시:**
- ❌ wallclock duration ±5% 초과
- ❌ heartbeat.jsonl 65초 초과 간격
- ❌ DB invariant 위반 (closed_trades × 3 ≠ db_inserts ±2)
- ❌ Evidence 파일 누락 (chain_summary/heartbeat/kpi/manifest)

**KPI WARN → 로그만 (RunWatcher FAIL 조건으로 처리):**
- ⚠️ winrate = 0% (100 거래 후 → RunWatcher FAIL 조건 A)
- ⚠️ negative edge 5분 연속 (→ RunWatcher FAIL 조건 B)
- ⚠️ consecutive losses 10회 (→ RunWatcher FAIL 조건 E)

---

## 4. Execution Modes (실행 모드)

### 4.1 Baseline Mode
- **Duration:** 20분 (1200초)
- **Purpose:** 기본 기능 검증
- **AC:** wallclock=20m ± 1m, heartbeat >= 20줄, net_pnl 기록
- **Evidence:** chain_summary.json, heartbeat.jsonl, kpi.json

### 4.2 Longrun Mode
- **Duration:** 60분 또는 180분
- **Purpose:** 장기 안정성 검증 (메모리 누수, DB 성능)
- **AC:** wallclock 정확도 ±5%, heartbeat 연속성, DB invariant
- **Evidence:** 위 + daily_report.json

### 4.3 Smoke Mode
- **Duration:** 1~5분
- **Purpose:** 빠른 회귀 검증
- **AC:** 정상 부팅 + 기회 생성 1회 이상
- **Evidence:** chain_summary.json, heartbeat.jsonl

---

## 5. Evidence Minimum Set (증거 최소셋)

### 5.1 필수 파일 (모든 모드)
1. **chain_summary.json**
   - duration_seconds (wall-clock 기준)
   - closed_trades, wins, losses, net_pnl
   - opportunities_generated
   - stop_reason

2. **heartbeat.jsonl**
   - timestamp, epoch_time (60초 간격)
   - kpi snapshot
   - guards (peak_pnl, drawdown_pct, consecutive_losses)

3. **kpi.json**
   - 최종 KPI 스냅샷
   - db_counts (db_inserts_ok, db_inserts_failed)

4. **manifest.json**
   - run_id, timestamp, git_sha
   - config, phase, duration_minutes

### 5.2 조건부 파일
- **stop_reason_snapshot.json:** RunWatcher FAIL 시 생성
- **daily_report.json:** Longrun 모드 시 생성
- **decision_trace.json:** 디버깅 모드 시 생성

### 5.3 Atomic Evidence Flush
```python
finally:
    try:
        db_counts = self.ledger_writer.get_counts() if hasattr(self, 'ledger_writer') else None
        if hasattr(self, 'kpi') and hasattr(self, 'evidence_collector'):
            self.save_evidence(db_counts=db_counts)
            logger.info("[OPS_PROTOCOL] Atomic Evidence Flush completed")
    except Exception as flush_error:
        logger.error(f"[OPS_PROTOCOL] Atomic Evidence Flush failed: {flush_error}")
    
    self.stop_watcher()
```

---

## 6. Docker Healthcheck Integration

### 6.1 Healthcheck 전략
- **Source:** heartbeat.jsonl (60초 간격)
- **Interval:** 60초
- **Timeout:** 5초
- **Retries:** 3회 연속 실패 → unhealthy

### 6.2 Healthcheck Command
```bash
#!/bin/sh
# healthcheck.sh
heartbeat_file="/app/logs/evidence/${RUN_ID}/heartbeat.jsonl"

if [ ! -f "$heartbeat_file" ]; then
  echo "FAIL: heartbeat.jsonl not found"
  exit 1
fi

# 마지막 heartbeat 시간 확인
last_epoch=$(tail -1 "$heartbeat_file" | jq -r '.epoch_time')
now=$(date +%s)
gap=$((now - last_epoch))

if [ "$gap" -gt 65 ]; then
  echo "FAIL: heartbeat stale (gap=${gap}s > 65s)"
  exit 1
fi

echo "PASS: heartbeat fresh (gap=${gap}s)"
exit 0
```

### 6.3 docker-compose.yml 예시
```yaml
services:
  arbitrage:
    healthcheck:
      test: ["CMD", "/app/healthcheck.sh"]
      interval: 60s
      timeout: 5s
      retries: 3
      start_period: 120s
```

---

## 7. SIGTERM / Graceful Shutdown Sequence

### 7.1 신호 처리 순서
1. **SIGTERM 수신:** OS 또는 Docker/K8s에서 발생
2. **Graceful Stop 트리거:** `orchestrator.request_stop()` 호출
3. **Main Loop 종료:** 현재 iteration 완료 후 break
4. **Evidence Flush:** `finally` 블록에서 무조건 실행 (10초 제한)
5. **Exit:** Exit Code 1 (비정상 종료)

### 7.2 타임아웃 처리
- **Flush 제한:** 10초 (초과 시 강제 종료)
- **SIGKILL 대비:** `finally` 블록은 반드시 실행됨 (OS 보장)

### 7.3 구현 예시
```python
import signal

def sigterm_handler(signum, frame):
    logger.warning("[OPS_PROTOCOL] SIGTERM received, requesting graceful stop")
    orchestrator.request_stop()

signal.signal(signal.SIGTERM, sigterm_handler)
```

---

## 8. Failure Modes & Recovery

### 8.1 Failure Modes

| 모드 | 원인 | 증상 | Recovery |
|------|------|------|----------|
| **F1: Wallclock Drift** | 시스템 과부하, sleep 부정확 | duration_seconds 불일치 | Exit 1 + 재실행 |
| **F2: Heartbeat Loss** | RunWatcher 스레드 중단 | heartbeat.jsonl 누락 | Exit 1 + 재실행 |
| **F3: DB Insert Fail** | DB 연결 끊김, Constraint 위반 | db_inserts_ok != expected | Exit 1 + DB 복구 |
| **F4: Evidence Missing** | 디스크 Full, 권한 오류 | 파일 누락 | Exit 1 + 디스크 정리 |
| **F5: SIGTERM Timeout** | Evidence Flush 10초 초과 | 강제 종료 | 수동 Evidence 복구 |

### 8.2 Recovery 절차

#### F1: Wallclock Drift
1. **진단:** `chain_summary.json`에서 duration_seconds 확인
2. **원인:** `top`, `iostat`로 시스템 부하 확인
3. **조치:** 부하 감소 후 재실행

#### F2: Heartbeat Loss
1. **진단:** `heartbeat.jsonl` 존재 여부 + 라인 수
2. **원인:** RunWatcher 스레드 로그 확인
3. **조치:** 코드 수정 + 재실행

#### F3: DB Insert Fail
1. **진단:** `db_counts` 확인 (db_inserts_failed > 0)
2. **원인:** DB 로그 확인 (constraint 위반, 연결 끊김)
3. **조치:** DB 스키마 수정 + 재실행

#### F4: Evidence Missing
1. **진단:** `manifest.json` 확인 + 파일 목록
2. **원인:** 디스크 공간, 권한 확인
3. **조치:** 디스크 정리 + 재실행

#### F5: SIGTERM Timeout
1. **진단:** `finally` 블록 로그 확인
2. **원인:** Evidence Flush가 10초 초과
3. **조치:** 수동으로 Evidence 복구 (DB 쿼리)

---

## 9. Gate Integration (Gate 3단)

### 9.1 Gate 단계
1. **Doctor Gate:** 코드 컴파일 검증 (`python -m compileall`)
2. **Fast Gate:** 핵심 유닛 테스트 (< 1분, integration 제외)
3. **Regression Gate:** 전체 테스트 (< 10분, slow 포함)

### 9.2 Gate 실행 표준 프로시저
```powershell
# Doctor Gate
.\abt_bot_env\Scripts\python.exe -m compileall arbitrage\v2\core\*.py -q

# Fast Gate
.\abt_bot_env\Scripts\python.exe -m pytest tests/ -k "not slow and not integration" -q --tb=no --timeout=120

# Regression Gate
.\abt_bot_env\Scripts\python.exe -m pytest tests/ -v --timeout=300
```

### 9.3 Gate 100% PASS 기준
- **FAIL 1건도 허용 안 함**
- **WARNING은 조사 필요 (잠재적 FAIL)**
- **SKIP은 사유 명시 필수**

---

## 10. Link Verification (Atomic Cross-Linking)

### 10.1 링크 검증 원칙
- **모든 문서 수정 시 상호 참조 검증 필수**
- **Broken Link = Critical Issue → 즉시 수정**
- **포맷:** `[링크 텍스트](상대경로#anchor)` (절대경로 금지)

### 10.2 링크 검증 대상
- `SSOT_RULES.md` → `OPS_PROTOCOL.md` (절차 참조)
- `D_ROADMAP.md` → `OPS_PROTOCOL.md` (Post-D205 Rebuild Track)
- `V2_ARCHITECTURE.md` → `OPS_PROTOCOL.md` (Operational Flow)

### 10.3 검증 명령
```bash
# Markdown 링크 검증 (수동)
rg '\[.*\]\((.*?)\)' docs/v2/*.md
```

---

## 11. Version History

| Version | Date | Changes | Author |
|---------|------|---------|--------|
| 1.0 | 2026-01-12 | 초판 작성 (D205-RB-DOCS-1) | Cascade |

---

## 12. References

- **Parent Document:** [`SSOT_RULES.md`](SSOT_RULES.md)
- **Architecture:** [`V2_ARCHITECTURE.md`](V2_ARCHITECTURE.md)
- **Roadmap:** [`../../D_ROADMAP.md`](../../D_ROADMAP.md) (Post-D205 Rebuild Track)
- **Evidence Format:** [`design/EVIDENCE_FORMAT.md`](design/EVIDENCE_FORMAT.md)
