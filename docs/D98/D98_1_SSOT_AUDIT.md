# D98-1 SSOT Audit: 미완료/조건부/미사용 항목 조사

**작성일:** 2025-12-21  
**작성자:** Windsurf AI  
**목적:** D98-1 (Preflight Real-Check Fail-Closed) 착수 전 프로젝트 상태 정확히 파악

---

## 1. Executive Summary

**Audit 목표:**
- 지금까지 "완료"로 표시된 항목 중 실제로 미완료/조건부/미사용인 것 식별
- "산으로 가는" 흐름 방지를 위해 SSOT에 사실 명확히 기록
- D98-1 작업 범위와 하지 않을 범위를 명확히 구분

**핵심 발견:**
1. ✅ **D83-1 (Real L2 WebSocket)**: 구현 완료, D83-1.6에서 ALL PASS 달성
2. ⚠️ **D98-1 (ReadOnly Guard)**: 구현 완료되어 있지만, 사용자가 요청한 "Real-Check Preflight"와는 다른 내용
3. ✅ **D98-0~D98-4**: Defense-in-Depth 아키텍처 완성, 전 단계 PASS
4. ⚠️ **조건부/미완료 항목**: D83-1.5 초기 CONDITIONAL 상태는 D83-1.6에서 해소됨

**결론:**
- 기존 D98-1 REPORT는 "ReadOnly Guard" (주문 차단)
- 이번 작업은 "Real-Check Preflight" (DB/Redis/Exchange 실제 연결 검증)
- 두 작업은 별개이므로 이번 작업을 "D98-1 Real-Check Preflight"로 명확히 구분

---

## 2. D83 시리즈 상태 (Real L2 WebSocket)

### 2.1 D83-1: Real L2 WebSocket Provider

**상태:** ✅ **COMPLETE** (D83-1.6에서 최종 PASS)

**구현 내역:**
- `arbitrage/exchanges/upbit_l2_ws_provider.py` (310 lines)
- `tests/test_d83_1_real_l2_provider.py` (250 lines, 7/7 PASS)
- Runner 통합: `scripts/run_d84_2_calibrated_fill_paper.py` (--l2-source mock|real)

**초기 이슈 (D83-1.5):**
- ⚠️ CONDITIONAL: Real WebSocket 메시지 수신 실패
- 원인: bytes 디코딩 누락 + Upbit 구독 포맷 불일치

**해결 (D83-1.6):**
- ✅ FIX #1: `ws_client.py`에 bytes → UTF-8 디코딩 로직 추가
- ✅ FIX #2: `upbit_ws_adapter.py`에 Upbit 공식 구독 포맷 적용 (배열 + ticket)
- ✅ 검증: 219개 메시지 수신 (30초), Real L2 PAPER 5분 ALL PASS

**Acceptance Criteria (D83-1.6):**
- ✅ Duration ≥ 300초 (300.2s)
- ✅ Fill Events ≥ 40개 (60개)
- ✅ BUY std/mean > 0.1 (1.891)
- ✅ SELL std/mean > 0.1 (1.245)
- ✅ WebSocket Reconnect ≤ 1회 (0회)
- ✅ Fatal Exceptions = 0

**회수 필요 여부:** ❌ **회수 불필요** - D83-1.6에서 완전 해결됨

**근거 파일:**
- `docs/D83/D83-1_REAL_L2_WEBSOCKET_REPORT.md`
- `docs/D83/D83-1_5_REAL_L2_SMOKE_REPORT.md`
- `docs/D83/D83-1_6_UPBIT_WS_DEBUG_NOTE.md`

---

## 3. D98 시리즈 상태 (Production Readiness)

### 3.1 D98-0: LIVE Preflight 인프라

**상태:** ✅ **COMPLETE**

**구현 내역:**
- Preflight 스크립트: `scripts/d98_live_preflight.py`
- Runbook: `docs/D98/D98_RUNBOOK.md`
- Secrets 관리: `.env.live.example`, 환경변수 SSOT

**테스트 결과:**
- 15+16 tests PASS
- Documentation PASS

### 3.2 D98-1: Read-only Preflight Guard

**상태:** ✅ **COMPLETE** (기존 구현)

**구현 내역:**
- `arbitrage/config/readonly_guard.py` (ReadOnlyGuard 클래스)
- `arbitrage/exchanges/paper_exchange.py` (@enforce_readonly 데코레이터)
- `scripts/d98_live_preflight.py` (READ_ONLY_ENFORCED=true 강제)

**테스트 결과:**
- 21/21 단위 테스트 PASS
- 17/17 통합 테스트 PASS
- 총 38/38 PASS

**핵심 기능:**
- ✅ ReadOnlyGuard: Fail-Closed 원칙, 주문 함수 차단
- ✅ create_order, cancel_order 차단 (READ_ONLY_ENFORCED=true)
- ✅ get_balance, get_orderbook 등 조회 함수는 허용

**⚠️ 중요한 발견:**
- 기존 D98-1은 "ReadOnly Guard" (주문 실행 차단)
- 사용자가 요청한 D98-1은 "Real-Check Preflight" (DB/Redis/Exchange 실제 연결 검증)
- **두 작업은 별개이며, 이번 작업은 새로운 목표**

### 3.3 D98-2: Live Adapters ReadOnly Guard

**상태:** ✅ **COMPLETE**

**구현 내역:**
- Live Exchange (Upbit, Binance)에 ReadOnly Guard 적용
- 14+18 tests PASS

### 3.4 D98-3: Executor-Level Guard

**상태:** ✅ **COMPLETE**

**구현 내역:**
- Executor 층에 중앙 게이트 구현
- 8+6 tests PASS

### 3.5 D98-4: Settings Live Key Guard

**상태:** ✅ **COMPLETE**

**구현 내역:**
- `arbitrage/config/live_safety.py` (LiveSafetyValidator)
- `arbitrage/config/settings.py` (Settings 통합)
- 16+19 tests PASS

**핵심 기능:**
- ✅ Fail-Closed 6단계 검증
- ✅ LIVE_ARM_ACK, LIVE_ARM_AT (10분 이내), LIVE_MAX_NOTIONAL_USD (10~1000 USD)

**전체 D98 시리즈 테스트:**
- Fast Gate: 164/164 PASS
- Core Regression: 2468 PASS

---

## 4. 미완료/조건부/미사용 항목 정리

### 4.1 ❌ 미완료 항목 (0건)

없음. D83-1, D98-0~4 모두 완료 상태.

### 4.2 ⚠️ 조건부 항목 (0건)

- D83-1.5 초기 CONDITIONAL 상태는 D83-1.6에서 완전 해소됨
- 현재 조건부로 남아있는 항목 없음

### 4.3 📦 구현 존재하지만 미사용 항목

#### 항목 1: D98-1 ReadOnly Guard (부분 미사용)

**모듈:** `arbitrage/config/readonly_guard.py`  
**원래 의도:** Preflight 실행 시 실주문 0건 보장  
**현재 미사용 이유:** Preflight 스크립트에서 READ_ONLY_ENFORCED=true 강제 설정하지만, 실제 DB/Redis/Exchange 연결 검증은 하지 않음  
**조치 계획:** 이번 D98-1 (Real-Check Preflight)에서 실제 연결 검증 추가

#### 항목 2: Mock L2 Provider (Paper 모드 기본값)

**모듈:** `MockMarketDataProvider`  
**원래 의도:** L2 orderbook 시뮬레이션  
**현재 상태:** Real L2 WebSocket (D83-1) 구현 완료되었지만, Runner 기본값은 여전히 mock  
**조치 계획:** 이번 단계에서는 변경하지 않음 (No Side-track)

---

## 5. D98-1 (Real-Check Preflight) 범위 정의

### 5.1 이번 단계에서 **하는** 것

**목표:** Preflight 실행 시 DB/Redis/Exchange를 실제로 연결하고, 응답/권한/환경이 맞는지 검증. 하나라도 불일치하면 Fail-Closed로 즉시 종료.

**구현 항목:**
1. ✅ **Redis Real-Check**
   - ping + set/get 테스트
   - 실패 시 PreflightError 발생

2. ✅ **Postgres Real-Check**
   - DSN 연결 + SELECT 1
   - 필수 테이블 존재 확인 (가능하면)
   - 실패 시 PreflightError 발생

3. ✅ **Exchange Real-Check (환경 분기)**
   - Paper: PaperExchange 설정/의존성 real-check
   - Live: LiveSafetyValidator 통과 후 public health call 1개만
   - 실패 시 PreflightError 발생

4. ✅ **Evidence 저장**
   - `docs/D98/evidence/d98_1_preflight_realcheck_YYYYMMDD_HHMM.txt`
   - `docs/D98/evidence/d98_1_preflight_json_YYYYMMDD_HHMM.json`

5. ✅ **테스트 작성**
   - 단위 테스트: Redis/Postgres/Exchange Real-Check
   - 통합 테스트: Redis down → FAIL, Postgres down → FAIL
   - READ_ONLY_ENFORCED와의 정합성 검증

6. ✅ **문서/ROADMAP 업데이트**
   - `D98_1_REPORT.md` (새로 작성, 기존과 구분)
   - `D98_1_AS_IS_SCAN.md` (preflight 진입점 분석)
   - `D_ROADMAP.md` (D98-1 상태 업데이트)
   - `CHECKPOINT_2025-12-17_ARBITRAGE_LITE_MID_REVIEW.md` (동기화)

### 5.2 이번 단계에서 **하지 않는** 것 (No Side-track)

**명확한 범위 제한:**
1. ❌ **Mock L2 → Real L2 기본값 변경**: D83-1 완료되었지만 Runner 기본값 변경 안 함
2. ❌ **D98-2+ 작업 착수**: Live Exchange ReadOnly Guard 추가 적용 안 함
3. ❌ **새 Preflight 기능 추가**: DB 마이그레이션 검증, 환경변수 전수 검사 등 범위 외
4. ❌ **성능 최적화**: Preflight 속도 개선, 병렬 검증 등 미실시
5. ❌ **Private endpoint 호출**: Exchange health check는 public endpoint만 사용

---

## 6. D83-1 회수 계획 (다음 단계로 고정)

### 6.1 회수 필요 여부

**결론:** ❌ **회수 불필요**

**근거:**
- D83-1.6에서 Upbit WebSocket 정상 작동 확인 (219개 메시지 수신)
- Real L2 PAPER 5분 테스트 ALL PASS (std/mean > 0.1)
- 모든 Acceptance Criteria 충족
- 문서 및 ROADMAP 정리 완료

### 6.2 D83 시리즈 다음 단계

**D83-2:** Binance L2 WebSocket Provider (향후 작업)  
**D83-3:** Multi-Exchange L2 Aggregation (향후 작업)

**현재 우선순위:**
- D98 시리즈 완결이 우선
- D83-2는 M4 (Observability) 이후 착수

---

## 7. D_ROADMAP / CHECKPOINT 동기화 필요 사항

### 7.1 D_ROADMAP.md 업데이트 필요

**D98-1 섹션:**
- 현재 상태: PLANNED 또는 미명시
- 변경 필요: "IN PROGRESS" 표시
- Acceptance Criteria 추가:
  - AC1: Redis Real-Check (ping + set/get)
  - AC2: Postgres Real-Check (SELECT 1 + 테이블 확인)
  - AC3: Exchange Real-Check (env별 분기)
  - AC4: Fail-Closed 원칙 (하나라도 실패 시 즉시 종료)
  - AC5: Evidence 파일 저장
  - AC6: 테스트 100% PASS
  - AC7: 문서/ROADMAP 동기화

**D83-1 섹션:**
- 현재 상태: CONDITIONAL (D83-1.5)
- 변경 필요: "✅ COMPLETE (D83-1.6 PASS)" 표시
- 근거: D83-1.6에서 ALL PASS 달성

### 7.2 CHECKPOINT 업데이트 필요

**추가 섹션:** "조건부/미완료 항목 현황"

**내용:**
- D83-1 초기 CONDITIONAL → D83-1.6 RESOLVED
- D98-1 기존 구현 (ReadOnly Guard) vs 이번 작업 (Real-Check Preflight) 구분 명시
- 미사용 항목: Mock L2 Provider (Real L2 완료되었으나 기본값 유지)

---

## 8. 리스크 & 완화 전략

| Risk | Probability | Impact | Mitigation | Status |
|------|-------------|--------|------------|--------|
| Preflight 중 실주문 발생 | Low | Critical | ReadOnly Guard (기존 D98-1) + Real-Check (이번 작업) | ✅ 이중 방어 |
| DB/Redis 연결 실패 시 오류 메시지 불명확 | Medium | Medium | PreflightError에 상세 메시지 포함 | 📋 설계 반영 |
| Exchange public endpoint 호출 시 rate limit | Low | Low | 단일 호출만 수행, retry 없음 | 📋 설계 반영 |
| 테스트 환경과 실제 환경 불일치 | Medium | High | pytest fixture로 격리, 실제 Docker 환경에서 통합 테스트 | 📋 계획 수립 |

---

## 9. 결론

**SSOT Audit 완료 결과:**
1. ✅ D83-1: 회수 불필요, D83-1.6에서 완전 해결
2. ✅ D98-0~4: 전 단계 완료, Defense-in-Depth 완성
3. ⚠️ D98-1 (기존): ReadOnly Guard 구현 완료
4. 📋 D98-1 (이번): Real-Check Preflight 구현 필요 (새로운 목표)

**명확한 범위:**
- **이번 작업:** DB/Redis/Exchange 실제 연결 검증 (Fail-Closed)
- **하지 않을 것:** Mock→Real 기본값 변경, D98-2+ 착수, 성능 최적화

**다음 단계:**
- D98-1 AS-IS Scan (preflight 진입점 분석)
- D98-1 구현 (Real-Check Preflight)
- 테스트 100% PASS
- 문서/ROADMAP 동기화
- Git commit/push

---

**작성 완료:** 2025-12-21 00:30 KST  
**작성자:** Windsurf AI  
**버전:** v1.0
