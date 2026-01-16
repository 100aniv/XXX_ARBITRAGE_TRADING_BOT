# LEGACY D206~D209 Archive (2026-01-16 Rebase 이전 원본)

**Archive Date:** 2026-01-17  
**Reason:** 2026-01-16 Roadmap Rebase - "돈 버는 로직 우선" 헌법 원칙 강제  
**Status:** 보존 전용 (수행하지 않음, D 번호 재할당 안 함)  
**Purpose:** 정보 누락 0% 보장, 역사적 추적성 유지

---

## ⚠️ 중요 공지

이 문서는 **2026-01-16 Roadmap Rebase 이전의 구 D206~D209 원본**을 보존한 아카이브입니다.

**이 문서의 내용은:**
- ✅ 역사적 추적성을 위한 보존용
- ✅ 커밋/증거 경로 참조용
- ❌ 실제 수행 대상 아님
- ❌ D 번호 재할당 안 함

**실제 수행 대상:**
- **신 D206~D209:** 엔진 내재화 + 수익 로직 + Safe Launch + LIVE 설계 (D_ROADMAP.md 참조)

---

## 매핑 테이블 (Rebase 전후)

| 구 D 번호 | 신 D 번호 | 제목 | 상태 | 커밋/증거 |
|----------|----------|------|------|-----------|
| **구 D206** | **신 D210 (ARCHIVED)** | 운영 프로토콜 엔진 내재화 + 수익 로직 모듈화 | PARTIAL | - |
| 구 D206-0 | 신 D210-0 (ARCHIVED) | 운영 프로토콜 엔진 내재화 | DONE | f54ebb5, 31cd2fa |
| 구 D206-1 | 신 D210-1 (ARCHIVED) | 수익 로직 모듈화 및 튜너 인터페이스 | COMPLETED | 8541488, eddcc66 |
| 구 D206-2 | 신 D210-2 (ARCHIVED) | 자동 파라미터 튜너 | PLANNED | - |
| 구 D206-3 | 신 D210-3 (ARCHIVED) | 리스크 컨트롤 | PLANNED | - |
| 구 D206-4 | 신 D210-4 (ARCHIVED) | 실행 프로파일 통합 | PLANNED | - |
| **구 D207** | **신 D211 (ARCHIVED)** | V1 거래 로직 → V2 마이그레이션 | PLANNED | - |
| 구 D207-1 | 신 D211-1 (ARCHIVED) | V1 거래 로직 분석 및 마이그레이션 계획 | PLANNED | - |
| 구 D207-2 | 신 D211-2 (ARCHIVED) | V1 Entry/Exit 규칙 이식 | PLANNED | - |
| 구 D207-3 | 신 D211-3 (ARCHIVED) | V1 Fee/Slippage 모델 이식 | PLANNED | - |
| 구 D207-4 | 신 D211-4 (ARCHIVED) | V1 Risk 관리 이식 | PLANNED | - |
| **구 D208** | **신 D212 (ARCHIVED)** | Paper 모드 수익성 검증 | PLANNED | - |
| 구 D208-1 | 신 D212-1 (ARCHIVED) | Paper 수익성 검증 (Real MarketData) | PLANNED | - |
| **구 D209** | **신 D213 (ARCHIVED)** | Infrastructure & Operations | PLANNED | - |
| 구 D209-1 | 신 D213-1 (ARCHIVED) | Grafana | PLANNED | - |
| 구 D209-2 | 신 D213-2 (ARCHIVED) | Docker Compose | PLANNED | - |
| 구 D209-3 | 신 D213-3 (ARCHIVED) | Runbook + Gate/CI | PLANNED | - |
| 구 D209-4 | 신 D213-4 (ARCHIVED) | Admin Control Panel | PLANNED | - |

---

## 구 D206 원문: 운영 프로토콜 엔진 내재화 + 수익 로직 모듈화

**Freeze Point:** D205-18-4R2 (Run Protocol 강제화)까지 안정화 기반 확립  
**Strategy:** 엔진 내재화 (OPS_PROTOCOL → Engine) → 수익 로직 모듈화 → 리스크 컨트롤 → 실행 프로파일 통합  
**Constitutional Basis:** SSOT_RULES.md > D_ROADMAP.md > OPS_PROTOCOL.md > V2_ARCHITECTURE.md

**D206 범위 (엔진/수익 로직 전용):**
- D206-0: 운영 프로토콜 엔진 내재화 (WARN=FAIL, State Management)
- D206-1: 수익 로직 모듈화 및 튜너 인터페이스
- D206-2: 자동 파라미터 튜너 (Bayesian Optimization)
- D206-3: 리스크 컨트롤 (position limit, loss cutoff)
- D206-4: 실행 프로파일 통합 (SMOKE/BASELINE/LONGRUN)

**문제 인식:**
- V1: 65+ run_*.py 스크립트 난립, Runner가 자체 루프 보유
- V2 현재: Engine은 stub, PaperRunner가 사실상 엔진 역할
- 해결: Engine에 유일한 루프, Runner는 얇은막 (OPS_PROTOCOL.md 참조)

---

### 구 D206-0: 운영 프로토콜 엔진 내재화

**상태:** ✅ COMPLETED (2026-01-15)  
**커밋:** f54ebb5 (initial), 31cd2fa (FIXPACK)  
**테스트:** PASS (check_ssot_docs=0, pytest=0)  
**문서:** `docs/v2/reports/D206/D206-0_REPORT.md`

**구현 내용:**
- OrchestratorState enum 추가
- WarningCounterHandler 추가 (WARN=FAIL 원칙)
- get_state() / get_warning_counts() 메서드 추가
- ExecutionConfig dataclass 추가
- FIXPACK: WARN=FAIL 진짜 강제, warning_count > 0 시에도 Exit 1

**목적:**
- Run Protocol 엔진 통합 (Orchestrator 단일 루프)
- WARN=FAIL 원칙 강제
- Evidence 원자화 & Flush
- Graceful Termination (SIGTERM)

**AC:**
- AC-1~5: Orchestrator 단일 루프, Invariant 강제, Graceful Termination, Heartbeat 통합, 엔진 상태 관리

**Evidence:**
- `tests/test_d206_0_ops_protocol.py`
- `logs/evidence/d206_0_ops_protocol_integration_<날짜>/`

---

### 구 D206-1: 수익 로직 모듈화 및 튜너 인터페이스

**상태:** ✅ COMPLETED (2026-01-16)  
**커밋:** 8541488  
**테스트:** pytest 10/10 PASS  
**문서:** `docs/v2/reports/D206/D206-1_REPORT.md`

**목적:**
- Profit Loop 재설계 (하드코딩 제거)
- 모델/전략 모듈화 (플러그인 형태)
- 튜너 인터페이스 도입

**AC:**
- AC-1: 파라미터 SSOT화 (config.yml)
- AC-2: 전략/모델 인터페이스 구현
- AC-3: TradeProcessor 개선
- AC-4: 튜너 훅 설계
- AC-5: 회귀 테스트 통과

**Evidence:**
- `docs/v2/reports/D206/D206-1_REPORT.md`
- `logs/evidence/d206_1_hardened_*/`

---

### 구 D206-2: 자동 파라미터 튜너 (PLANNED, 미수행)

**상태:** PLANNED  
**목적:** Auto-Tuning 엔진 구축 (Bayesian Optimization)

**AC:**
- AC-1: Bayesian 튜너 구현 (50회 Iteration)
- AC-2: 튜닝 결과 향상 (+15% 이상)
- AC-3: Automated Sweep Evidence
- AC-4: 통합 테스트
- AC-5: 모니터링 & Alert 연동
- AC-6: 문서화

---

### 구 D206-3: 리스크 컨트롤 (PLANNED, 미수행)

**상태:** PLANNED  
**목적:** 리스크 가드 통합 (Kill-Switch)

**AC:**
- AC-1: RiskGuard 모듈 구현
- AC-2: StopReason 체계
- AC-3: 예외 핸들러 일원화
- AC-4: 종료 플로우 테스트
- AC-5: Alert 시스템 연동
- AC-6: 문서/런북 갱신

---

### 구 D206-4: 실행 프로파일 통합 (PLANNED, 미수행)

**상태:** PLANNED  
**목적:** 프로파일 기반 실행 모드 (PAPER/SMOKE/BASELINE/LONGRUN)

**AC:**
- AC-1: Profile 정의 및 적용
- AC-2: 단일 Run 엔트리
- AC-3: 프로파일별 Evidence 변화
- AC-4: 프로파일별 AC 검증
- AC-5: 모니터링 & Alert
- AC-6: Backward Compatibility

---

## 구 D207 원문: V1 거래 로직 → V2 마이그레이션 (PLANNED, 미수행)

**전략:** V1 ArbitrageEngine 핵심 로직 100% V2 통합  
**Constitutional Basis:** Scan-First → Reuse-First

**D207 범위:**
- D207-1: V1 거래 로직 분석 및 마이그레이션 계획 수립
- D207-2: V1 Entry/Exit 규칙 → V2 이식
- D207-3: V1 Fee/Slippage 모델 → V2 이식
- D207-4: V1 Risk 관리 → V2 이식

(각 서브 단계 AC는 원본 D_ROADMAP.md의 구 D211-1~4 내용과 동일)

---

## 구 D208 원문: Paper 모드 수익성 검증 (PLANNED, 미수행)

**전략:** V2 엔진이 실제로 수익을 생성하는지 Paper 모드에서 검증  
**Constitutional Basis:** "돈 버는 알고리즘 우선"

**D208 범위:**
- D208-1: Real MarketData + Slippage/Latency 모델 강제, net_pnl > 0 증명

(AC는 원본 D_ROADMAP.md의 구 D212-1 내용과 동일)

---

## 구 D209 원문: Infrastructure & Operations (PLANNED, 미수행)

**전략:** 모니터링/배포/운영 자동화 진행  
**Constitutional Basis:** "돈 버는 알고리즘 우선" 원칙 - 인프라는 핵심 로직 검증 후에만

**D209 범위:**
- D209-1: Grafana (튜닝/운영 모니터링 용도만)
- D209-2: Docker Compose SSOT (패키징)
- D209-3: Runbook + Gate/CI Automation (운영 자동화)
- D209-4: Admin Control Panel (최소 제어)

(각 서브 단계 AC는 원본 D_ROADMAP.md의 구 D213-1~4 내용과 동일)

---

## 참조 정보

**Rebase 이유:**
1. 구 D206-1 "ProfitCore Bootstrap"은 뼈대만 (V1 도메인 모델 미통합, dict 기반)
2. 구 D206-2 Auto Tuner는 시기상조 (전략/상태기계 완성 전 튜닝은 "쓰레기 최적화")
3. 구 D207 마이그레이션 계획만 (실제 코드 통합 없음)
4. 구 D208 수익성 검증 불가 (전략 완성 전 수익성 증명 불가능)
5. Gate DOPING 상태 (Registry/Preflight가 파일 존재만 확인)

**해결 방안 (신 D206~D209):**
1. 신 D206: V1→V2 완전 이식 (도메인 모델 + 전략 로직 + Config SSOT + 주문 파이프라인)
2. 신 D207: Paper 수익성 (Real data + 실전 모델로 net_pnl > 0 증명)
3. 신 D208: 실패 대응 (주문 라이프사이클 + 리스크 가드 + Fail-Fast)
4. 신 D209: LIVE 설계만 (구현은 게이트로 봉인, 설계 문서만 작성)
5. Gate Integrity (신 D206-0에서 DOPING 제거 블로커로 선행 처리)

**SSOT 무결성:**
- ✅ 정보 누락 0% (기존 D206~D209 원문 → 이 아카이브로 이동)
- ✅ 커밋/증거 재귀속 (구 D206-1 커밋 8541488, eddcc66 → 신 D210-1 (ARCHIVED))
- ✅ D 번호 중복 방지 (매핑 테이블 기준 유일성 보장)
- ✅ AC 형식 통일 (모든 신규 D는 [ ] AC-1, [ ] AC-2... 체크리스트)

---

## 이 아카이브를 참조하는 방법

1. **커밋 추적:** 구 D206-1 커밋 8541488을 찾으려면 이 매핑 테이블 참조
2. **Evidence 경로:** 구 D206-0 증거는 `logs/evidence/d206_0_ops_protocol_integration_<날짜>/`
3. **보고서:** 구 D206-0/D206-1 보고서는 `docs/v2/reports/D206/D206-0_REPORT.md`, `D206-1_REPORT.md`

**이 아카이브는 수정하지 않습니다.** 역사적 기록으로만 유지합니다.

---

**Archive Maintenance Policy:**
- ✅ Read-Only (수정 금지)
- ✅ 역사적 추적성 유지
- ❌ 새로운 작업 추가 금지
- ❌ AC 체크/상태 변경 금지

**문의:** 이 아카이브에 대한 질문은 D_ROADMAP.md의 REBASELOG (2026-01-16) 섹션 참조
