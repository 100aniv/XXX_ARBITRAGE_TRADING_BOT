# D205-13: Auto Tuning Orchestrator v1 - 재사용 스캔

**작성일:** 2026-01-05  
**목적:** V1 자동튜닝 유산 스캔 + D205-13 구현 시 재사용 후보 식별

---

## 📋 스캔 범위

D205-13은 **Record/Replay 기반 자동 파라미터 튜닝 오케스트레이션**을 목표로 합니다.  
V1에 이미 튜닝 인프라가 구축되어 있으므로, **scan-first → reuse-first** 원칙에 따라 재사용 가능한 모듈을 먼저 식별합니다.

---

## 🔍 V1 자동튜닝 유산 (재사용 후보)

### 1. `arbitrage/tuning_session.py` ✅ **재사용 강력 추천**
- **클래스:** `TuningSessionPlanner`
- **기능:** Parameter grid 조합 생성 (cartesian product), job plan 생성
- **재사용 근거:** D205-7(Parameter Sweep) 기반, grid search 로직 검증됨
- **위치:** `arbitrage/tuning_session.py:61-151`
- **의존성:** dataclasses, typing (표준 라이브러리만 사용)

### 2. `arbitrage/tuning_session_runner.py` ✅ **재사용 가능**
- **클래스:** `TuningSessionRunner`
- **기능:** JSONL job plan 로드 → 순차 실행, 결과 집계
- **재사용 근거:** D40 검증됨, 로컬 실행 안정적
- **위치:** `arbitrage/tuning_session_runner.py:31-270`
- **의존성:** subprocess, logging (표준 라이브러리만 사용)

### 3. `arbitrage/v2/execution_quality/sweep.py` ✅ **재사용 필수**
- **클래스:** `ParameterSweep`
- **기능:** Record/Replay 기반 파라미터 스윕, ExecutionQuality 튜닝
- **재사용 근거:** D205-7 구현, V2 네임스페이스, Replay 통합
- **위치:** `arbitrage/v2/execution_quality/sweep.py:38-265`
- **의존성:** arbitrage.v2.replay.replay_runner (V2 의존성만)

### 4. `arbitrage/tuning_analysis.py` ⚠️ **조건부 재사용**
- **클래스:** `TuningAnalyzer`
- **기능:** 튜닝 결과 분석, 랭킹, 요약
- **재사용 근거:** D26 검증됨, 분석 로직 재사용 가능
- **제약:** CSV 기반 (V2는 NDJSON/JSON 선호), 일부 리팩토링 필요
- **위치:** `arbitrage/tuning_analysis.py:41-192`

### 5. `arbitrage/tuning_orchestrator.py` ❌ **재사용 불가**
- **클래스:** `TuningOrchestrator`
- **기능:** 분산 튜닝 세션 관리 (K8s/Docker)
- **재사용 불가 근거:**
  - D205-13 목표: 로컬 오케스트레이션만 (분산 X)
  - 인프라 의존성 과다 (K8s, Docker 필수)
  - SSOT 원칙 위반 (인프라 우선 금지)
- **위치:** `arbitrage/tuning_orchestrator.py:67-340`

---

## 🎯 D205-13 구현 전략 (재사용 우선)

### Phase 1: 기존 모듈 통합 (신규 코드 최소화)
1. **ParameterSweep** (arbitrage/v2/execution_quality/sweep.py) 재사용
   - ExecutionQuality 파라미터 스윕 로직 그대로 사용
   - 입력: market.ndjson (Record), 출력: sweep_results.json

2. **TuningSessionPlanner** (arbitrage/tuning_session.py) 재사용
   - Grid 조합 생성 로직 그대로 사용
   - 출력: jobs.jsonl (job plan)

3. **TuningSessionRunner** (arbitrage/tuning_session_runner.py) 재사용
   - JSONL job plan 실행 로직 그대로 사용
   - 순차 실행 (분산 불필요)

### Phase 2: 얇은 오케스트레이션 계층 추가
- **arbitrage/v2/tuning/auto_tuner.py** (신규, 최소 구현)
  - 책임: Phase 1 모듈 연결 (Planner → Sweep → Runner)
  - 금지: 신규 grid search 로직, 분산 인프라

### Phase 3: 결과 분석 (선택적)
- **TuningAnalyzer** 리팩토링 (CSV → JSON/NDJSON)
  - 필요 시 arbitrage/v2/tuning/analyzer.py로 이관

---

## 📊 재사용 가능성 평가

| 모듈 | 재사용 가능성 | V2 호환성 | 이유 |
|------|-------------|----------|------|
| `ParameterSweep` | ✅ 필수 | V2 | D205-7 기반, Replay 통합 |
| `TuningSessionPlanner` | ✅ 강력 추천 | V1 (호환 가능) | Grid 조합 로직 검증됨 |
| `TuningSessionRunner` | ✅ 가능 | V1 (호환 가능) | 로컬 실행 안정적 |
| `TuningAnalyzer` | ⚠️ 조건부 | V1 (리팩토링 필요) | CSV → JSON 변환 필요 |
| `TuningOrchestrator` | ❌ 불가 | V1 (인프라 과다) | 분산 불필요, SSOT 위반 |

---

## 🚫 금지 사항 (SSOT 원칙)

1. **분산 튜닝 클러스터 구현 금지**
   - D205-13 목표: 로컬 오케스트레이션만
   - K8s/Docker 배포는 D206+ 영역

2. **자동 적용 기본 ON 금지**
   - 튜닝 결과는 "후보 산출"까지만
   - 적용은 수동 승인 또는 조건부 ON (명시적 설정 필요)

3. **신규 Grid Search 알고리즘 구현 금지**
   - 기존 ParameterSweep 재사용 필수
   - Bayesian/Optuna 등은 D205-13 범위 밖

4. **웹 UI/대시보드 구현 금지**
   - CLI + JSON 출력만 (D206-4 영역)

---

## 📝 다음 단계 (D205-13 구현 시)

1. **Step 0-E:** 본 스캔 문서 정독
2. **Step 1:** ParameterSweep, TuningSessionPlanner, TuningSessionRunner 코드 읽기
3. **Step 2:** 얇은 오케스트레이션 계층 설계 (auto_tuner.py)
4. **Step 3:** 통합 구현 (신규 코드 < 100줄 목표)
5. **Step 4:** Gate 3단 (Doctor/Fast/Regression)
6. **Step 5:** Evidence 패키징 (manifest.json, tuning_results.json)
7. **Step 6-8:** 문서 + Git

---

## 🔗 의존성 (D_ROADMAP 기준)

**Depends on:**
- D205-5 (Record/Replay) ✅ DONE
- D205-7 (Parameter Sweep) ✅ DONE
- D205-9 (Realistic Paper Validation) ✅ DONE

**Strongly recommended:**
- D205-12 (Admin Control) ✅ DONE (안전한 pause/panic 없이 자동화 금지)

**Blocks:**
- D206 (배포/Ops) - 자동 튜닝 검증 후 진행 권장
