
# XXX_ARBITRAGE_TRADING_BOT — TEST & VALIDATION SSOT TEMPLATE

## (완전 자동화 / 강제 실행 / 운영급)

---

## 0) 헤더

[Windsurf TEST PROMPT] Dxxx-y TEST / VALIDATION  
모델: Claude Thinking (3 credits)

DONE 정의:
- 모든 테스트 단계 PASS
- Evidence + Metrics + Logs 확보
- D_ROADMAP 업데이트
- Git commit + push

---

## 1) 테스트 절대 원칙
- 테스트는 사람 개입 없이 자동 실행
- 중간 질문 금지
- FAIL 시 즉시 중단 → 수정 → 동일 프롬프트 재실행
- 의미 있는 지표 없으면 FAIL

---

## 2) Step 0 — 인프라 & 런타임 부트스트랩

### 0-A. Python 가상환경
```bash
python -m venv .venv
source .venv/bin/activate
python --version
pip --version
```

### 0-B. 기존 실행 프로세스 종료 (강제)
```bash
# Linux / macOS
pkill -f run_paper.py || true
pkill -f python || true

# Windows (PowerShell)
Get-Process python* -ErrorAction SilentlyContinue | Stop-Process -Force
```

- 이전 paper/live 프로세스 잔존 시 FAIL

### 0-C. Docker 인프라 확인
```bash
docker ps
docker compose ps
docker compose up -d
```

필수 컨테이너:
- postgres
- redis
- prometheus
- grafana (있을 경우)

### 0-D. DB / Redis 초기화 (강제)
```bash
python scripts/reset_db.py
python scripts/reset_redis.py
```

---

## 3) Step 1 — 코드 무결성 & Fast Gate
```bash
python -m compileall .
pytest tests/fast --maxfail=1
```

---

## 4) Step 2 — Core Regression
```bash
pytest tests/core --disable-warnings
```

---

## 5) Step 3 — Smoke PAPER Test
```bash
python scripts/run_paper.py --mode paper --duration 20m
```

PASS 기준:
- 주문 ≥ 1
- 포지션 정상
- 0 trades → FAIL + DecisionTrace

---

## 6) Step 4 — Monitoring 검증
```bash
curl http://localhost:9090/metrics
```

필수 메트릭:
- trade_count
- net_edge_after_exec
- latency_ms
- error_rate

---

## 7) Step 5 — Extended PAPER
```bash
python scripts/run_paper.py --mode paper --duration 1h --monitoring on
```

---

## 8) Step 6 — Wallclock Verification (장기 실행 필수)

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
```json
{
  "planned_total_hours": <number>,
  "phase_hours": [<phase1_h>, <phase2_h>, ...],
  "started_at_utc": "<ISO 8601, timezone-aware>",
  "last_tick_at_utc": "<ISO 8601>",
  "ended_at_utc": "<ISO 8601, 종료 시>",
  "monotonic_elapsed_sec": <number, SSOT>,
  "poll_sec": <number>,
  "samples_collected": <number>,
  "expected_samples": <number>,
  "completeness_ratio": <number, 0.0~1.0>,
  "max_spread_bps": <number>,
  "p95_spread_bps": <number>,
  "max_edge_bps": <number>,
  "min_edge_bps": <number>,
  "mean_edge_bps": <number>,
  "trigger_count": <number>,
  "trigger_timestamps": [<array>],
  "stop_reason": "<enum>",
  "phase_checkpoint_reached": <boolean>,
  "phase_checkpoint_time_utc": "<ISO 8601 or null>",
  "feasibility_decision": "<string or null>"
}
```

**stop_reason enum:**
- `TIME_REACHED`: 계획 시간 도달 (정상 종료)
- `TRIGGER_HIT`: 트리거 조건 충족 (성공)
- `EARLY_INFEASIBLE`: 조기 불가능 판정 (시장 제약)
- `ERROR`: 에러 발생
- `INTERRUPTED`: 사용자 중단 (Ctrl+C)

**PASS 기준:**
- `completeness_ratio ≥ 0.95` (정상)
- `completeness_ratio < 0.95` but `stop_reason = EARLY_INFEASIBLE` (PARTIAL 허용)
- `ended_at_utc` 존재 (종료 확인)
- `monotonic_elapsed_sec` 기준 시간 검증

**FAIL 기준:**
- `watch_summary.json` 미생성
- 필수 필드 누락
- `completeness_ratio < 0.95` + `stop_reason ≠ EARLY_INFEASIBLE`
- `stop_reason = ERROR`

**시간 기반 완료 선언 금지:**
- "3h 완료", "10h 실행" 같은 문구는 `watch_summary.json`에서 자동 추출한 값만 사용
- 인간이 손으로 시간 쓰는 것 절대 금지
- 문서/리포트에서 시간 언급 시 반드시 `watch_summary.json` 필드 인용

**Evidence 무결성:**
- 파일 write 시 `f.flush() + os.fsync(f.fileno())` 강제
- 가능하면 원자적 갱신 (temp file → fsync → os.replace)
- 모든 종료 경로(정상/예외/Ctrl+C)에서 watch_summary.json 생성 보장

---

## 9) Step 7 — Evidence 패키징
```text
logs/evidence/Dxxx-y_TEST/
- manifest.json
- kpi.json
- metrics_snapshot.json
- decision_trace.json
- watch_summary.json (장기 실행 시 필수)
```

---

## 10) Step 8 — D_ROADMAP 업데이트
- PASS / FAIL
- Evidence 경로
- 신규 문제는 추가만 허용

---

## 10) Step 8 — Git
```bash
git status
git diff --stat
git commit -m "[TEST] Dxxx-y validation"
git push
```

---

## 11) FAIL 처리 규칙
- 우회 금지
- 테스트 통과 전까지 반복
