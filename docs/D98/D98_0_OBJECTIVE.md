# D98-0 Objective: Production Readiness

**Status**: 🚧 IN PROGRESS  
**시작일**: 2025-12-18  
**Branch**: `rescue/d97_d98_production_ready`  
**목표**: LIVE 실행 준비 완료 (실제 LIVE 실행 없음, 준비만)

---

## 1. Executive Summary

**D98-0 범위**: LIVE 모드 실행을 위한 안전장치, 프리플라이트 체크, 런북, 시크릿 관리 SSOT 구축

**핵심 원칙**:
- ✅ LIVE 실행은 이번 단계에서 절대 금지 (준비만)
- ✅ Fail-Closed 안전장치: 실수로도 LIVE가 실행되지 않게
- ✅ 기존 모듈 최대 재사용 (over-engineering 금지)
- ✅ PAPER 모드에서 검증 가능한 것만 테스트

---

## 2. AS-IS 스캔 요약 (기존 인프라)

### 2.1 KPI/Metrics 저장 로직

**위치**: `scripts/run_d77_0_topn_arbitrage_paper.py`
- `_save_metrics()`: KPI JSON 저장 (32개 필드 포함)
- `_save_checkpoint()`: 주기적 체크포인트 (60초)
- `--kpi-output-path`: CLI 인자로 출력 경로 지정
- **상태**: ✅ 완전 구현됨 (D97에서 검증 완료)

**재사용 전략**: 그대로 사용, 추가 수정 불필요

---

### 2.2 Secrets/Settings 관리

**모듈**:
- `arbitrage/secrets.py`: Secrets 로딩 레이어
- `arbitrage/config/settings.py`: Settings 관리
- `scripts/check_required_secrets.py`: 필수 시크릿 검증
- `tests/test_d78_2_secrets_providers.py`: 테스트 커버리지

**환경 파일**:
- `.env.paper`: PAPER 모드 설정 (ARBITRAGE_ENV=paper)
- `.env.live`: **존재하지 않음** (안전)

**상태**: ✅ PAPER 모드 완전 구현, LIVE 모드 구조만 존재

**재사용 전략**:
- 기존 secrets.py 재사용
- LIVE 안전장치만 추가 (환경변수 검증)

---

### 2.3 Monitoring & Alerting

**모듈**:
- `arbitrage/monitoring.py`: 메트릭 수집
- `arbitrage/sys_monitor.py`: 시스템 모니터링
- `arbitrage/alert.py`: 알림 시스템
- `arbitrage/alerting/notifiers/telegram_notifier.py`: Telegram 알림
- `arbitrage/k8s_monitor.py`, `k8s_alerts.py`: K8s 모니터링

**Prometheus**:
- `.env.paper`에 설정됨 (PROMETHEUS_ENABLED=true, PORT=9100)
- Grafana 설정도 존재

**상태**: ✅ 완전 구현됨

**재사용 전략**: 그대로 사용, LIVE 특화 알림만 추가

---

### 2.4 Tuning 인프라 (광범위)

**핵심 모듈** (8개):
1. `arbitrage/tuning.py`: 기본 튜닝 엔진
2. `arbitrage/tuning_advanced.py`: Optuna 기반 고급 튜닝
3. `arbitrage/tuning_orchestrator.py`: 오케스트레이터
4. `arbitrage/tuning_session.py`: 세션 관리
5. `arbitrage/tuning_session_runner.py`: 로컬 러너
6. `arbitrage/k8s_tuning_session_runner.py`: K8s 분산 러너
7. `arbitrage/tuning_analysis.py`: 결과 분석
8. `tuning/parameter_tuner.py`: 파라미터 튜너

**Runner Scripts** (44개):
- `scripts/run_d24_tuning_session.py`
- `scripts/run_d68_tuning.py`
- `scripts/run_d82_5_threshold_sweep.py`
- `scripts/run_d90_3_zone_profile_sweep.py`
- `scripts/run_arbitrage_tuning.py`
- `scripts/run_k8s_tuning_pipeline.py`
- 등 (전체 목록: `docs/D97/TUNING_INFRA_SCAN.md` 참조)

**Test Coverage** (142개 파일, 1523 매치):
- `tests/test_d23_advanced_tuning.py` (46)
- `tests/test_d24_tuning_session.py` (38)
- `tests/test_d36_k8s_pipeline.py` (100)
- `tests/test_d38_arbitrage_tuning.py` (83)
- 등

**문서 SSOT** (10개+):
- `docs/D23_ADVANCED_TUNING_ENGINE.md`
- `docs/D24_TUNING_SESSION_RUNNER.md`
- `docs/D36_K8S_TUNING_PIPELINE.md`
- 등

**상태**: ✅ 완전 구현됨 (D23~D41 마일스톤 완료)

**평가**:
- Optuna 기반 Bayesian optimization 지원
- 로컬/K8s 분산 실행 지원
- DB(PostgreSQL)/Redis 기반 상태 관리
- 광범위한 테스트 커버리지

**ROADMAP 반영 전략**:
- D98에서는 tuning 구현하지 않음 (이미 완료됨)
- ROADMAP에 "tuning 인프라 존재 (D23~D41 완료)" 명시
- TO-BE에서 "Production 튜닝 파이프라인" 항목으로 연결

---

### 2.5 Preflight/HealthCheck

**기존 문서**:
- `docs/D92/D92_7_PREFLIGHT.md`
- `docs/D92/D92_6_PREFLIGHT_LOG.md`

**상태**: ⚠️ 문서만 존재, 자동화 스크립트 부재

**재사용 전략**:
- D92 preflight 체크리스트 재사용
- `scripts/d98_live_preflight.py` 신규 작성 (dry-run)

---

## 3. D98-0 구현 범위

### 3.1 LIVE ARMING 안전장치 (코드)

**목표**: 실수로도 LIVE가 실행되지 않는 Fail-Closed 구조

**구현**:
- `ARBITRAGE_ENV=live` 시 기본 동작: **즉시 종료**
- 오직 다음 조건 **모두** 만족 시만 진행 가능:
  1. `LIVE_ARM_ACK="I_UNDERSTAND_LIVE_RISK"`
  2. `LIVE_ARM_AT` (UTC timestamp, 10분 이내)
  3. `LIVE_MAX_NOTIONAL_USD` (상한값 명시 및 검증)
- 단위 테스트: 기본 케이스는 FAIL이 PASS

**파일**:
- `arbitrage/config/live_safety.py` (신규)
- `tests/test_d98_live_safety.py` (신규)

---

### 3.2 Live Preflight 스크립트 (Dry-run)

**목표**: LIVE 실행 전 자동 점검 (실제 API 호출 없이 모킹)

**구현**:
- `scripts/d98_live_preflight.py` (신규)
- 점검 항목:
  1. 환경변수/시크릿 존재 여부
  2. 거래소 Health/RateLimit 훅 (모킹)
  3. 오픈 포지션/오더/잔고 훅 (모킹)
  4. DB/Redis 연결 상태
- 결과: `docs/D98/evidence/live_preflight_dryrun.json`

**단위 테스트**:
- `tests/test_d98_preflight.py` (신규)
- API 호출 mock 처리

---

### 3.3 Secrets SSOT & Git 안전

**구현**:
- `.gitignore` 재확인 (.env.*, secrets/)
- D98 문서에 "Secrets 운영 원칙" 명시
- Preflight에서 `.env.live` 존재 시 자동 FAIL (이번 단계)

---

### 3.4 Runbook/Playbook (운영 문서)

**목표**: 운영자가 따라할 수 있는 단계별 절차

**파일**: `docs/D98/D98_RUNBOOK.md` (신규)

**내용**:
- Kill-switch 절차
- 중단/롤백 절차
- 단계적 램프업 (paper → live 소액 → 점진 확대)
- 모니터링 KPI (10종) 및 이상 징후 대응
- **LIVE 테스트 전 사용자 승인 필수** 명시

---

## 4. Acceptance Criteria

| # | Criterion | Target | Status |
|---|-----------|--------|--------|
| 1 | AS-IS 스캔 완료 | 모듈/문서 경로 | ✅ DONE |
| 2 | LIVE 안전장치 구현 | Fail-Closed | 🚧 TODO |
| 3 | Live Preflight 스크립트 | Dry-run | 🚧 TODO |
| 4 | Secrets SSOT | Git 안전 | 🚧 TODO |
| 5 | Runbook 작성 | 운영 절차 | 🚧 TODO |
| 6 | 단위 테스트 | PASS | 🚧 TODO |
| 7 | Fast Gate | PASS | 🚧 TODO |
| 8 | Core Regression | 44/44 PASS | 🚧 TODO |
| 9 | D97 1h Baseline | PASS (KPI JSON) | 🚧 TODO |
| 10 | 문서 업데이트 | ROADMAP/CHECKPOINT | 🚧 TODO |
| 11 | Git Commit & Push | Korean message | 🚧 TODO |

---

## 5. 다음 단계

### 5.1 D98-0 (이번 작업)
- LIVE 준비 인프라 구축
- 실제 LIVE 실행 없음

### 5.2 D98-1 (다음 작업, 사용자 승인 필요)
- LIVE Preflight 실제 실행 (API 호출)
- 소액 LIVE 테스트 (상한값 설정)
- 실시간 모니터링 및 kill-switch 대기

### 5.3 D99+ (미래)
- LIVE 점진 확대
- Production 튜닝 파이프라인
- Multi-exchange 확장

---

## 6. 리스크

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| 실수로 LIVE 실행 | Low | Critical | Fail-Closed 안전장치 |
| .env.live 커밋 | Low | High | .gitignore 검증 |
| Preflight 누락 | Medium | High | 자동화 스크립트 |
| 운영자 절차 오류 | Medium | High | Runbook 상세화 |

---

**작성일**: 2025-12-18  
**작성자**: Windsurf (Claude Opus 4.5)  
**검토 필요**: 사용자 승인 (LIVE 실행 전)
