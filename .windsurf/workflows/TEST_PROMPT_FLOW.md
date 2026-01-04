---
description: 테스트 프롬프트 플로우 (D_TEST_TEMPLATE.md 기반, 12 Steps)
---

# 테스트 프롬프트 플로우 (TEST_PROMPT_FLOW)

## 핵심 원칙
- **자동 실행**: 사람 개입 없이 자동 실행
- **의미 있는 지표**: 0 trades → FAIL
- **Wallclock 강제**: 장기 실행(≥1h)은 watch_summary.json 필수
- **시간 허위 선언 금지**: watch_summary.json 기반만
- **Evidence 무결성**: 원자적 갱신 강제
- **Gate 3단 필수**: Doctor / Fast / Regression 100% PASS
- **Git 강제**: commit + push 필수

## 프롬프트 헤더 (필수)
```
[Windsurf TEST PROMPT] Dxxx-y TEST / VALIDATION

모델: Claude Thinking (3 credits)

DONE 정의:
- 모든 테스트 단계 PASS
- Evidence + Metrics + Logs 확보
- D_ROADMAP 업데이트
- Git commit + push
```

## 테스트 절대 원칙
1. **자동 실행**: 사람 개입 없이 자동 실행
2. **중간 질문 금지**: 모든 결정은 자동화 규칙 기반
3. **FAIL 시 처리**: 즉시 중단 → 수정 → 동일 프롬프트 재실행
4. **의미 있는 지표**: 지표 없으면 FAIL

## 12단계 테스트 플로우

### Step 0: 인프라 & 런타임 부트스트랩

#### 0-A. Python 가상환경
```bash
python -m venv .venv
source .venv/bin/activate
python --version
pip --version
```

#### 0-B. 기존 실행 프로세스 종료 (강제)
```bash
# Linux / macOS
pkill -f run_paper.py || true
pkill -f python || true

# Windows (PowerShell)
Get-Process python* -ErrorAction SilentlyContinue | Stop-Process -Force
```
- 이전 paper/live 프로세스 잔존 시 FAIL

#### 0-C. Docker 인프라 확인
```bash
docker ps
docker compose ps
docker compose up -d
```
**필수 컨테이너**: postgres, redis, prometheus, grafana (있을 경우)

#### 0-D. DB / Redis 초기화 (강제)
```bash
python scripts/reset_db.py
python scripts/reset_redis.py
```

### Step 1: 코드 무결성 & Fast Gate
```bash
python -m compileall .
pytest tests/fast --maxfail=1
```

### Step 2: Core Regression
```bash
pytest tests/core --disable-warnings
```

### Step 3: Smoke PAPER Test
```bash
python scripts/run_paper.py --mode paper --duration 20m
```
**PASS 기준:**
- 주문 ≥ 1
- 포지션 정상
- 0 trades → FAIL + DecisionTrace

### Step 4: Monitoring 검증
```bash
curl http://localhost:9090/metrics
```
**필수 메트릭:**
- trade_count
- net_edge_after_exec
- latency_ms
- error_rate

### Step 5: Extended PAPER
```bash
python scripts/run_paper.py --mode paper --duration 1h --monitoring on
```

### Step 6: Wallclock Verification (장기 실행 필수)

**적용 대상:**
- 장기 실행 테스트(≥1h)
- Wait Harness / 모니터링 / 대기 작업
- Phased Run / Early-Stop 포함 작업

**필수 증거:**
```text
logs/evidence/Dxxx-y_<timestamp>/
- watch_summary.json (SSOT)
- heartbeat.json (선택)
- market_watch.jsonl (선택, 샘플 기록)
```

**watch_summary.json 필수 필드:**
- planned_total_hours, phase_hours
- started_at_utc, last_tick_at_utc, ended_at_utc
- monotonic_elapsed_sec (SSOT)
- poll_sec, samples_collected, expected_samples
- completeness_ratio (0.0~1.0)
- max_spread_bps, p95_spread_bps, max_edge_bps, min_edge_bps, mean_edge_bps
- trigger_count, trigger_timestamps
- stop_reason (enum: TIME_REACHED | TRIGGER_HIT | EARLY_INFEASIBLE | ERROR | INTERRUPTED)
- phase_checkpoint_reached, phase_checkpoint_time_utc, feasibility_decision

**PASS 기준:**
- completeness_ratio ≥ 0.95 (정상)
- completeness_ratio < 0.95 but stop_reason = EARLY_INFEASIBLE (PARTIAL 허용)
- ended_at_utc 존재 (종료 확인)
- monotonic_elapsed_sec 기준 시간 검증

**FAIL 기준:**
- watch_summary.json 미생성
- 필수 필드 누락
- completeness_ratio < 0.95 + stop_reason ≠ EARLY_INFEASIBLE
- stop_reason = ERROR

**시간 기반 완료 선언 금지:**
- "3h 완료", "10h 실행" 같은 문구는 watch_summary.json에서 자동 추출한 값만 사용
- 인간이 손으로 시간 쓰는 것 절대 금지

**Evidence 무결성:**
- 파일 write 시 f.flush() + os.fsync(f.fileno()) 강제
- 가능하면 원자적 갱신 (temp file → fsync → os.replace)
- 모든 종료 경로(정상/예외/Ctrl+C)에서 watch_summary.json 생성 보장

### Step 7: Evidence 패키징
```text
logs/evidence/Dxxx-y_TEST/
├── manifest.json
├── kpi.json
├── metrics_snapshot.json (선택)
├── decision_trace.json (선택)
└── watch_summary.json (장기 실행 시 필수)
```

### Step 8: D_ROADMAP 업데이트
- PASS / FAIL 명시
- Evidence 경로 기록
- 신규 문제는 추가만 허용 (삭제 금지)

### Step 9: Git 커밋
```bash
git status
git diff --stat
git commit -m "[TEST] Dxxx-y validation"
git push
```

### Step 10: FAIL 처리 규칙
- **우회 금지**: 테스트 통과 전까지 반복
- **자동 디버깅**: 원인 파악 → 수정 → 재실행
- **Evidence 기록**: 모든 실패 원인 문서화

### Step 11: Closeout Summary (출력 양식 고정)
**반드시 포함:**
- **Gate Results**: Doctor / Fast / Regression (PASS/FAIL)
- **Evidence Path**: logs/evidence/Dxxx-y_TEST/
- **KPI**: 핵심 지표 (trade_count, net_edge_after_exec, latency_p95 등)
- **Status**: PASS / FAIL / PARTIAL

## 필수 vs 선택적 실행

### 필수 실행 (항상)
- Step 0: 인프라 부트스트랩
- Step 1: Fast Gate
- Step 2: Core Regression
- Step 7: Evidence 패키징
- Step 8: D_ROADMAP 업데이트
- Step 9: Git 커밋

### 선택적 실행 (필요할 때만)
- Step 3: Smoke PAPER Test
- Step 4: Monitoring 검증
- Step 5: Extended PAPER
- Step 6: Wallclock Verification (장기 실행 시 필수)

---

**참조**: @[D_TEST_TEMPLATE.md] (모든 세부사항)  
**메모리**: 5b1ae48f-dcc5-4efe-990a-98107b1da83f (D_TEST_TEMPLATE 메모리)  
**상태**: 테스트 프롬프트 플로우 (12단계, Wallclock Verification 포함)
