# V2 Evidence SSOT (Single Source of Truth)

**작성일:** 2025-12-29  
**목적:** 모든 V2 실행(Paper/LIVE/Gate)의 증거 저장 포맷 및 규칙 SSOT 확정

---

## 📋 Evidence 원칙

1. **증거 없는 PASS 선언 금지**: 모든 실행은 반드시 증거 폴더에 산출물 저장
2. **표준 포맷 강제**: 모든 증거는 동일한 구조/파일명으로 저장
3. **자동 생성 규칙**: watchdog/just/gate 실행 시 evidence 자동 생성
4. **추적 가능성**: run_id로 모든 실행을 추적 가능하게 유지

---

## 🗂️ Evidence 디렉토리 구조

```
logs/evidence/
├── <run_id>/                          # 실행 세션 폴더
│   ├── manifest.json                  # 실행 메타데이터 (필수)
│   ├── gate.log                       # Gate 실행 로그 (필수)
│   ├── git_info.json                  # Git 상태 스냅샷 (필수)
│   ├── cmd_history.txt                # 실행 커맨드 기록 (필수)
│   ├── kpi_summary.json               # KPI 집계 (Paper 실행 시)
│   ├── error.log                      # 에러 로그 (실패 시)
│   ├── stdout.txt                     # 표준 출력 (선택)
│   └── artifacts/                     # 추가 산출물 (선택)
│       ├── config_snapshot.yml        # 실행 시점 config 스냅샷
│       ├── db_schema_version.txt      # DB 스키마 버전
│       └── ...
```

---

## 🆔 Run ID 규칙

**포맷:** `YYYYMMDD_HHMMSS_<d-number>_<short_hash>`

**예시:**
```
20251229_023000_d200_2_48b14fe
20251229_024530_d204_2_a1b2c3d
20251229_030000_gate_doctor_f5e6d7c
```

**구성:**
- `YYYYMMDD_HHMMSS`: 실행 시작 시각 (UTC+9)
- `<d-number>`: D 단계 번호 (d200_2, d204_2, gate_doctor 등)
- `<short_hash>`: Git commit short hash (7자)

---

## 📄 필수 산출물 상세

### 1. manifest.json (필수)

**목적:** 실행 메타데이터 기록

**포맷:**
```json
{
  "run_id": "20251229_023000_d200_2_48b14fe",
  "timestamp": "2025-12-29T02:30:00+09:00",
  "d_number": "d200-2",
  "task_name": "Bootstrap Lock + Evidence SSOT",
  "status": "PASS",
  "duration_seconds": 180,
  "python_version": "3.13.11",
  "git": {
    "branch": "rescue/d99_15_fullreg_zero_fail",
    "commit": "48b14fe74dfeb2018b282bd1c025717a00a60b92",
    "status": "clean"
  },
  "environment": {
    "docker_redis": "running",
    "docker_postgres": "stopped",
    "venv": "abt_bot_env"
  },
  "gates": {
    "doctor": "PASS",
    "fast": "PASS",
    "regression": "PASS"
  }
}
```

### 2. gate.log (필수)

**목적:** Gate 실행 로그 (doctor/fast/regression)

**포맷:**
```
[2025-12-29 02:30:00] ===== GATE EXECUTION START =====
[2025-12-29 02:30:00] Gate: doctor
[2025-12-29 02:30:01] Command: pytest --collect-only -q
[2025-12-29 02:30:05] Result: PASS (289 tests collected)
[2025-12-29 02:30:05] 
[2025-12-29 02:30:05] Gate: fast
[2025-12-29 02:30:05] Command: pytest tests/test_d98_preflight.py tests/test_d48_upbit_order_payload.py -v
[2025-12-29 02:30:10] Result: PASS (27/27 PASS, 0.67s)
[2025-12-29 02:30:10] 
[2025-12-29 02:30:10] Gate: regression
[2025-12-29 02:30:10] Command: pytest tests/test_d98_preflight.py tests/test_d48_upbit_order_payload.py -v
[2025-12-29 02:30:15] Result: PASS (27/27 PASS, 0.67s)
[2025-12-29 02:30:15] ===== GATE EXECUTION END =====
[2025-12-29 02:30:15] Status: ALL GATES PASS ✅
```

### 3. git_info.json (필수)

**목적:** Git 상태 스냅샷

**포맷:**
```json
{
  "timestamp": "2025-12-29T02:30:00+09:00",
  "branch": "rescue/d99_15_fullreg_zero_fail",
  "commit": "48b14fe74dfeb2018b282bd1c025717a00a60b92",
  "commit_message": "[D200-1] SSOT hardening + roadmap lock + config/db skeleton",
  "status": "clean",
  "remote": {
    "origin": "https://github.com/100aniv/XXX_ARBITRAGE_TRADING_BOT.git",
    "tracking_branch": "rescue/d99_15_fullreg_zero_fail"
  },
  "modified_files": [
    "D_ROADMAP.md",
    "README.md",
    "docs/v2/design/SSOT_MAP.md"
  ],
  "added_files": [
    "db/migrations/v2_schema.sql",
    "db/migrations/v2_schema_rollback.sql",
    "docs/v2/design/REDIS_KEYSPACE.md",
    "tests/test_v2_config.py"
  ]
}
```

### 4. cmd_history.txt (필수)

**목적:** 실행 커맨드 기록

**포맷:**
```
# D200-2 Bootstrap Lock + Evidence SSOT
# Execution: 2025-12-29 02:30:00 UTC+9

## Step 0: SSOT 문서 검증
Command: (읽기 작업, 커맨드 없음)
Status: PASS

## Step 1: .windsurfrule [BOOTSTRAP] 추가
Command: git add .windsurfrule
Status: PASS

## Step 2: SSOT_MAP 정교화
Command: git add docs/v2/design/SSOT_MAP.md
Status: PASS

## Step 3: Evidence SSOT 문서 생성
Command: (파일 생성)
Status: PASS

## Gate: doctor
Command: .\abt_bot_env\Scripts\python.exe -m pytest --collect-only -q
Status: PASS (289 tests)

## Gate: fast
Command: .\abt_bot_env\Scripts\python.exe -m pytest tests/test_d98_preflight.py tests/test_d48_upbit_order_payload.py -v
Status: PASS (27/27)

## Git Commit
Command: git commit -m "[D200-2] bootstrap lock + evidence spec"
Status: PASS (commit: abc1234)

## Git Push
Command: git push origin rescue/d99_15_fullreg_zero_fail
Status: PASS
```

### 5. kpi_summary.json (Paper 실행 시)

**목적:** Paper 실행 KPI 집계

**포맷:**
```json
{
  "run_id": "20251229_024530_d204_2_a1b2c3d",
  "duration_seconds": 3600,
  "symbols_count": 20,
  "entries": 12,
  "exits": 8,
  "winrate_pct": 66.7,
  "pnl_usd": 45.23,
  "avg_latency_ms": 62,
  "max_memory_mb": 180,
  "avg_cpu_pct": 35,
  "uptime_pct": 99.8,
  "reconnect_count": 1,
  "errors": 0,
  "status": "PASS"
}
```

---

## 🤖 자동 생성 규칙

### 1. watchdog 실행 시

```bash
# watchdog 시작 시 자동으로 evidence 폴더 생성
logs/evidence/<run_id>/
├── manifest.json (watchdog 시작 시 생성)
├── gate.log (실시간 기록)
├── git_info.json (시작 시 스냅샷)
└── cmd_history.txt (실시간 기록)
```

### 2. just doctor/fast/regression 실행 시

```bash
# just 명령 실행 시 자동으로 gate.log 기록
just doctor
  → logs/evidence/<run_id>/gate.log 자동 append
  → manifest.json 업데이트 (doctor: PASS/FAIL)

just fast
  → logs/evidence/<run_id>/gate.log 자동 append
  → manifest.json 업데이트 (fast: PASS/FAIL)

just regression
  → logs/evidence/<run_id>/gate.log 자동 append
  → manifest.json 업데이트 (regression: PASS/FAIL)
```

### 3. Paper 실행 시

```bash
# Paper 실행 시 자동으로 KPI 수집
python -m arbitrage.v2.harness.paper_runner --duration 3600
  → logs/evidence/<run_id>/kpi_summary.json 자동 생성
  → logs/evidence/<run_id>/gate.log 기록
```

---

## 🛠️ Evidence Pack 유틸 (tools/evidence_pack.py)

**목적:** Evidence 폴더 자동 생성 및 압축

**기능:**
1. 현재 git hash/branch/status 스냅샷
2. Gate 커맨드 기록
3. Evidence 폴더 압축 (zip)

**사용:**
```python
from tools.evidence_pack import EvidencePacker

packer = EvidencePacker(d_number="d200-2", task_name="Bootstrap Lock")
packer.start()  # manifest.json, git_info.json 생성

# ... 작업 수행 ...

packer.add_gate_result("doctor", "PASS")
packer.add_gate_result("fast", "PASS")
packer.add_gate_result("regression", "PASS")

packer.finish()  # 폴더 압축, manifest.json 최종 업데이트
```

---

## 📊 Evidence 검증 체크리스트

| 항목 | 필수 | 확인 |
|------|------|------|
| manifest.json 존재 | ✅ | run_id, timestamp, status 포함 |
| gate.log 존재 | ✅ | doctor/fast/regression 결과 기록 |
| git_info.json 존재 | ✅ | commit hash, branch, status 포함 |
| cmd_history.txt 존재 | ✅ | 모든 실행 커맨드 기록 |
| kpi_summary.json (Paper만) | ⚠️ | entries, exits, pnl_usd 포함 |
| error.log (실패 시) | ⚠️ | 마지막 에러 메시지 포함 |
| 폴더명 규칙 준수 | ✅ | YYYYMMDD_HHMMSS_<d>_<hash> |

---

## 🚫 금지 사항

- ❌ Evidence 폴더 수동 삭제 (히스토리 보존)
- ❌ manifest.json 수동 편집 (자동 생성만)
- ❌ 증거 없는 PASS 선언
- ❌ 다른 포맷의 증거 저장 (표준 포맷만)

---

## 📝 다음 단계

이 문서는 **SSOT**입니다. Evidence 포맷 변경 시 반드시 이 문서를 업데이트하세요.

**업데이트 규칙:**
1. 새 필드 추가 시 → 해당 섹션 업데이트 + 예시 추가
2. 포맷 변경 시 → 커밋 메시지에 `[EVIDENCE]` 태그
3. 자동 생성 규칙 변경 시 → tools/evidence_pack.py 업데이트 + 문서 동기화

**참조:**
- SSOT_MAP: `docs/v2/design/SSOT_MAP.md` (Evidence SSOT 섹션)
- 구현: `tools/evidence_pack.py` (자동 생성 로직)
