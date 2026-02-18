# V2 SSOT Rules (Single Source of Truth)

**Version:** 2.1 (D206 Taxonomy Update)  
**Effective Date:** 2025-12-29  
**Status:** ENFORCED

---

(A) SSOT_RULES.md 최상단에 박을 것 (Alpha Fast Lane 헌법 조항)

ALPHA FAST LANE (D_ALPHA-*)

NO-ASK: 사용자를 멈춰 세우는 질문(승인 UI/스코프/선택지) 금지

AUTO-SCOPE: 스코프는 D_ROADMAP IN_PROGRESS + git diff로 자동 확정

DEFAULT ACTION: 스코프 밖 대량 변경 감지 시 “문서/리포트만 커밋 + 나머지 stash”가 기본값(묻지 말고 실행)

NET-READ PRE-AUTH: ticker/orderbook/market data read는 사전 승인

ALPHA 증거 최소셋: kpi.json + manifest.json + edge_survey_report.json만 있으면 “Done(Alpha)” 인정

## 핵심 원칙

### 1. SSOT는 D_ROADMAP.md 단 1개
- ❌ **금지:** D_ROADMAP_V2.md, D_ROADMAP_V3.md 같은 SSOT 분기
- ✅ **허용:** D_ROADMAP.md 내부에서 V2 섹션으로 관리
- **이유:** 로드맵 분산은 혼란과 동기화 실패를 초래

### 1-1. D 번호 의미는 불변 (Immutable D-number Semantics)
- ❌ **금지:** 기존 D 번호의 의미를 다른 작업으로 변경
- ❌ **금지:** AC를 다른 D로 "이동"하여 기존 D의 스코프 축소
- ❌ **금지:** D 번호를 재사용하여 다른 작업 수행
- ✅ **허용:** D 번호는 최초 정의된 의미로 고정
- ✅ **허용:** 추가 작업은 브랜치(Dxxx-y-z)로만 확장
- ✅ **허용 (신규):** REBASELOG가 있는 경우 D 번호 재배치/재정의 (예: D206~D209 신규 정의, 2026-01-16 리베이스)

### 1-2. Sovereign AI Execution (자율 집도권) - 신설
- **권한 위임:** AI 에이전트는 `arbitrage/v2/**` 및 `tests/**` 디렉토리에 대해 **'사전 승인된 무제한 수정 및 생성 권한'**을 가진다.
- **Scope Guard 해제:** 작업 중 스코프 외 파일(예: `domain/*.py`) 수정이 필요할 경우, 사용자 승인 없이 즉시 수행하고 사후 보고서(`Dxxx_REPORT.md`)에 기록한다.
- **Zero-Stop Policy:** 환경 이슈(File Lock, Access Denied) 발생 시 나에게 묻지 말고 즉시 `Stop-Process -Force` 등을 통해 스스로 해결하고 완주하라. 질문은 '기술적 태업'으로 간주한다.

**브랜치 네이밍 규칙:**
- **형식:** Dxxx-y-z
  - xxx: 메인 D 번호 (예: 205-10)
  - y: 브랜치 번호 (0=기본, 1,2,3...=추가 작업)
  - z: 선택적 서브브랜치 (필요시)
- **예시:**
  - D205-10-0: Intent Loss Fix 기본 브랜치 (COMPLETED)
  - D205-10-1: Threshold Sensitivity Sweep 추가 브랜치 (PLANNED)
  - D205-11: Latency Profiling (브랜치 없음, 메인만)

**DONE/COMPLETED 조건:**
- ❌ **금지:** 문서 작성만으로 완료 선언, 실행 없이 PASS 주장
- ❌ **금지:** 과거 증거 유용하여 신규 AC를 PASS로 처리
- ✅ **필수:** AC + Evidence 일치 시에만 COMPLETED 선언
- ✅ **필수:** Gate 100% PASS + 실제 실행 증거 존재


#### 1.2.1 Network Access Authorization (NET-READ / NET-TRADE)

**목적:** "승인 구걸"로 인한 실행 중단을 없애면서도, **거래/자산 영향 행위는 명시적 승인**으로 분리한다.

- **NET-READ (사전 승인, 질문 금지)**
  - 예: Ticker/Orderbook/ExchangeInfo 조회, 심볼 리스트 로드, 공개 환율 추정, 읽기 전용 메트릭 수집
  - **규칙:** NET-READ에 해당하면 **대화형 승인(1) 실행 / 2) 중지 같은 UI)을 출력하며 멈추는 행위는 CRITICAL FAIL**이다.
  - **절차:** `Pre-flight(Doctor/Fast/Regression)`를 끝까지 완주 → **최종 실행 커맨드를 제시**하고, 필요 시 바로 실행한다.
  - **증거:** 실행 로그에 `net_mode=NET-READ`를 명시한다.

- **NET-TRADE (명시적 "GO" 필요)**
  - 예: 주문(spot/futures) 발행, 포지션 변경, 자산/잔고 조회(민감), 출금/전송, API 키/권한 변경
  - **규칙:** NET-TRADE는 사용자로부터 정확히 **"GO"** 또는 동등한 명시적 승인 토큰을 받은 뒤에만 실행한다.
  - **대체:** 승인 전에는 "준비 완료(Pre-flight + 리스크 리포트 + 실행 커맨드)"까지는 진행하되, **마지막 실행만 보류**한다.

- **명시 규정 (가장 자주 헷갈리는 케이스)**
  - `--use-real-data`가 **Ticker/Orderbook 등 읽기 전용 호출만 포함**하고, 주문 실행이 `dry_run=true` 또는 주문 코드 경로가 비활성이라면 **NET-READ**로 분류한다.
  - 반대로, 주문/잔고/API키 관련 호출이 포함되면 **NET-TRADE**로 분류한다.

> 요약: **READ는 묻지 말고 끝까지, TRADE는 GO 없으면 마지막 버튼만 보류.**

### 1-3. Task ID Resolution & RERUN Policy (강제)
- **Task ID 확정:** 이번 작업의 Task ID는 `D_ROADMAP.md`의 **IN PROGRESS** 섹션에서 1개를 확정해 사용한다.
- **COMPLETED 재사용 금지:** 완료된 Task ID를 신규 완료로 재사용하지 않는다.
- **RERUN 기록:** 재실행은 `RERUN`으로 표시하고, 기존 COMPLETED 상태는 유지한다.
- **보조 증거 규칙:** 다른 D 단계의 보조 증거는 `RERUN` 또는 `참조`로 표기하며 신규 COMPLETED로 기록하지 않는다.


### 2. Report 파일명 규칙 (SSOT 우선순위: D_ROADMAP → Report → Evidence)
**⚠️ 핵심 원칙: Report는 필수, Evidence README는 보조**

- **메인 D:** `docs/v2/reports/Dxxx/Dxxx_REPORT.md`
- **브랜치 D:** `docs/v2/reports/Dxxx/Dxxx-y_REPORT.md` 또는 `Dxxx-y-z_REPORT.md`
- **예시:**
  - D205-10-0: `docs/v2/reports/D205/D205-10_REPORT.md` (브랜치 0은 기본이므로 -0 생략 가능)
  - D205-10-1: `docs/v2/reports/D205/D205-10-1_REPORT.md`
  - D205-11: `docs/v2/reports/D205/D205-11_REPORT.md`

**Report 생성 강제 규칙 (D206부터 필수):**
- ❌ **금지:** Evidence README만으로 대체 (주객전도)
- ✅ **필수:** 모든 D 작업은 `docs/v2/reports/Dxxx/Dxxx-y_REPORT.md` 생성
- ✅ **필수:** Report 내용:
  - 목표 (Objective)
  - AC (Acceptance Criteria) + 검증 결과
  - 구현 내용 (Implementation)
  - Gate 결과 (Doctor/Fast/Regression)
  - 재사용 모듈 (Reuse Strategy)
  - 의존성 (Dependencies)
  - 다음 단계 (Next Steps)
- ✅ **선택:** Evidence README는 Report 보조 (재현 커맨드 등)

**SSOT 우선순위 (변경 금지):**
1. **D_ROADMAP.md** - 상태/목표/AC의 유일한 원천
2. **docs/v2/reports/Dxxx/Dxxx-y_REPORT.md** - 검증 결과의 공식 문서
3. **logs/evidence/Dxxx-y_*/** - 실행 증거 (로그/스택/메트릭)
4. **Evidence README.md** - 증거 디렉토리 내 재현 가이드 (보조)

### 3. V2 문서는 docs/v2/ 단일 경로
- ✅ **신규 문서:** docs/v2/ 아래에만 작성
- ❌ **금지:** docs/v2_*, docs/V2/, docs/version2/ 같은 변형
- **구조:**
  ```
  docs/v2/
    ├── SSOT_RULES.md          # 본 문서
    ├── V2_ARCHITECTURE.md     # V2 아키텍처 정의
    ├── design/                # 설계 문서
    ├── reports/               # 검증 리포트
    └── evidence/              # 실행 증거
  ```

### 3. V1 레거시는 docs/ 아래 Read-only
- 📖 **V1 문서:** 현재 docs/ 아래 D15~D106 문서들
- ❌ **금지:** V1 문서 수정 (버그 픽스 제외)
- ✅ **허용:** V1 문서 참조 및 학습
- **마커:** docs/v1/README.md에 "Read-only" 선언

---

## 🚫 강제 금지 사항

### 1. 파괴적 이동/삭제 금지 (첫 턴)
- ❌ arbitrage/ 전체 리팩토링
- ❌ config/configs 통합
- ❌ 대량 파일 이동
- ✅ 스캔 + 리포트 + 계획만

### 2. 오버리팩토링 금지
- ❌ "완벽한 구조"를 위한 전면 개편
- ✅ Engine 중심 플로우 뼈대만 최소 구현
- ✅ 점진적 마이그레이션 (V1과 공존)

### 3. 스크립트 중심 실험 폐기

---

## ⚙️ [ENFORCED] Scan-First → Reuse-First (V1 유산 강제 재사용)

**원칙:** V2 작업은 "새로 만들기"가 아니라 "흐름/인터페이스 정리 + 기존 모듈 재사용"이다.

### 강제 규칙

1. **(Scan-First)** 구현 전에 반드시 repo를 검색하여 기존 모듈/유사 기능 존재 여부를 확인한다.
   - rg/grep로 키워드 검색, 기존 클래스/함수/테이블/스토리지/레이트리밋/알림 훅 확인

2. **(Reuse-First)** 기존 모듈이 있으면:
   - ❌ **금지:** 새 파일/새 모듈 생성
   - ✅ **허용:** 기존 모듈 확장/리팩토링/얇은 어댑터 추가만 허용

3. **(No Duplicate)** 동일 목적의 v2_* / new_* / experimental_* 중복 모듈 생성 금지

4. **(Exception)** 예외적으로 새 모듈이 필요하면:
   - "왜 기존 것을 못 쓰는지"를 보고서(Dxxx_REPORT)에 명시
   - `docs/v2/design/INFRA_REUSE_INVENTORY.md`에 재사용 불가 사유와 대체 모듈을 기록

### Reuse Exception Protocol (예외 허용 절차)

**원칙:** 기본은 reuse-first, 예외는 증거 기반으로만 허용

**예외 허용 조건 (모두 충족 시에만):**
1. **Scan 결과 증거**: "기존 재사용 불가" 증거 (rg/grep 결과 + 사유)
2. **대체안 검증**: 상용/논문 기반 대체 방식이 명백히 우수함을 수치로 입증
3. **엔진 중심 유지**: 새 모듈도 arbitrage/v2/** 구조 + 인프라 최소 원칙 준수
4. **비교 증거**: 기존 방식 vs 대체 방식 동일 KPI 기준 비교 (최소한 재현 가능한 sweep 결과)
5. **D_ROADMAP 기록**: "왜 대체했는지" 3줄 요약 + 비교 증거 경로 명시

**예외 허용 불가 (금지):**
- ❌ "더 나을 것 같다" (추측 기반)
- ❌ "새 프레임워크가 유행" (트렌드 추종)
- ❌ "완벽한 구조" (오버엔지니어링)
- ❌ 인프라 확장 (K8s/Docker 분산 등)

### Gate 연동

- **Fast/Regression/Full Gate PASS 전에는 "DONE" 선언 불가**
- **Gate FAIL이면 원인 해결 전 다음 D로 이동 금지**

---

## 🎯 "돈버는 알고리즘 우선" 원칙 (V2 개발 최상위 규칙)

**정의:**
- 인프라/Ops 우선이 아니라, **수익성 검증된 알고리즘이 먼저 완성되어야 함**
- "안 죽는 봇" ≠ "돈 버는 봇" → 둘 다 필요하지만 순서가 중요

**강제 규칙:**
1. **D205-4~9:** Profit Loop (측정/튜닝/검증) 필수
2. **D205-10~12:** 돈버는 알고리즘 최적화 (수익성/레이턴시/제어) 필수
3. **Phase 2 (D206~D209):** Core Path (엔진 내재화 + 수익 로직 + LIVE 설계) 필수
4. **Phase 3 (D210~D211):** Commercial Track (HFT/백테스트/UI/ML) 선택적
5. **LIVE 진입:** D209 (LIVE 설계) 완료 후 즉시 가능 (Phase 3 완료 여부 무관)

위반 시 결과:
- D206 진입 조건 미충족 → 즉시 FAIL 처리
- 인프라 우선 로드맵 → SSOT 재검토 강제
- Phase 3을 필수 게이트로 오독 → 문서 명확화 강제

---

## Profit Loop 강제 규칙 (D205-4~12 필수)

### 1. "측정 → 튜닝 → Core Path → 의사결정" 순서 강제

원칙: Profit Loop (D205-4~12) → Core Path (D206~D209) 완료 후, 팀은 다음 중 선택:
- **Fast Track:** D209 완료 → D212+ LIVE (Phase 3 스킵)
- **Commercial Track:** D209 완료 → D210~D211 (상용급 강화) → D212+ LIVE

강제 규칙:
1. **D206 진입 조건:** D205-12 PASS 필수 (Admin Control 완료)
2. **LIVE 진입 조건:** D209 (LIVE 설계) PASS 필수 (Phase 3 완료 여부 무관)
3. **의사결정 포인트:** D209 완료 후 팀이 Fast/Commercial Track 선택
4. **SSOT 검증:** D_ROADMAP.md에서 의사결정 포인트 명시 필수

**예외:** 없음 (순서는 절대 원칙, 의사결정은 필수)

### 2. Record/Replay 없으면 튜닝/회귀 불가

**원칙:** Parameter tuning은 반드시 Record/Replay 기반으로만 수행

**강제 규칙:**
1. **D205-5 (Record/Replay) 완료 전:** D205-7 (Parameter Sweep) 진입 금지
2. **재현성 검증:** 동일 market.ndjson → 동일 decisions.ndjson (diff = 0)
3. **회귀 테스트:** 파라미터 변경 시 리플레이로 회귀 자동 검증

**근거:** 리플레이 없이 튜닝하면 재현 불가능, 회귀 검증 불가능

### 4. 제어 인터페이스 없으면 Core Path 진입 불가

**원칙:** D205-12(Admin Control)를 통과하지 않으면 D206(Core Path) 진입 금지

**강제 규칙:**
1. **D205-12 (Admin Control) 완료 전:** D206 진입 금지
2. **필수 제어 기능:** Start/Stop/Panic/Blacklist/Emergency Close
3. **audit log:** 모든 제어 명령 기록 필수
4. **LIVE 진입:** D209 완료 후 제어 기능 재사용 (D206-4 Admin UI는 표면 계층)

**근거:** 제어 없이 배포하면 장애 시 대응 불가능. 상용급 시스템은 최소 제어 필수

### 5. 가짜 낙관 방지 규칙 (D205-15-6b 강화)

**원칙:** winrate 0% 또는 100% 같은 비현실적 KPI는 계약/측정 검증 단계로 강제 이동

**강제 규칙:**
1. **D205-6 이후:** winrate 0% 또는 100% → PASS 아님, 계약/측정 검증 단계로 강제 이동
2. **D205-15-6b 계약:** MARKET BUY filled_qty = quote_amount / filled_price (불변식)
3. **D205-9 기준:** winrate 50~80% (현실적 범위), edge_after_cost > 0 필수
4. **PASS 조건:** 현실적 KPI + PnL 안정성 (std < mean) + 수량 계약 준수

**근거:** 
- 현실 마찰(수수료/슬리피지/부분체결/429) 미반영 시 가짜 낙관 발생
- winrate 100%는 시뮬레이터 계약 위반 신호 (filled_qty 뻥튀기 등)
- winrate 0%는 로직 버그 또는 시장 기회 부족 신호

**D205-15-6b 사례:**
- Before: wins=0 (filled_price=None 버그)
- After 6a: wins=60, winrate=100% (filled_qty 계약 위반)
- After 6b: winrate 40~60% 예상 (계약 준수 + 현실적 슬리피지)

---

### 3. 스크립트 중심 실험 폐기
- ❌ run_d108_*.py, run_v2_test.py 같은 일회성 스크립트
- ✅ 엔진 기반 Smoke Harness (재사용 가능)
- ✅ Adapter 패턴으로 거래소별 분리

### 4. Paper-LIVE Parity 강제 (D205-9-REOPEN)

**원칙:** Smoke/Baseline/Longrun = Real MarketData + Simulated Execution (운영 검증)

**강제 규칙:**
1. **Smoke/Baseline/Longrun Phase:**
   - Real MarketData 필수 (use_real_data=true)
   - DB/Redis strict 모드 필수 (db_mode=strict)
   - MOCK 데이터 실행 시 즉시 FAIL-fast
2. **MOCK 허용 범위:**
   - test_1min 같은 계약/유닛 전용 phase로만 제한
   - 개발자 로컬 테스트 전용
3. **운영 검증 기준:**
   - 실시장 마찰 반영 (슬리피지/수수료/지연/부분체결)
   - 인프라 부하 검증 (DB insert latency, Redis dedup)
   - 현실적 KPI (winrate 50~80%, edge_after_cost > 0)

**근거:**
- 상용 퀀트 시스템 표준 (Freqtrade/Hummingbot)
- "가짜 수익의 마약"에서 벗어나 차가운 현실 데이터 마주하기
- MOCK 데이터 = 손실 케이스 구조적 부재 → 100% winrate 허상

**D205-15-6b 사례 (Before D205-9-REOPEN):**
- filled_qty 계약 올바르게 적용됨 ✅
- 하지만 use_real_data=false로 실행 ❌
- 결과: winrate 100% (MOCK 데이터 특유의 낙관)

### 5. LIVE 중단 유지
- ❌ V2에서도 실거래 기본 금지
- ✅ PAPER/READ_ONLY 모드 기본
- ✅ Real MarketData + Simulated Execution (D205-9-REOPEN)

### 6. Component Registry & Preflight (D205-15-6c)
**원칙:** 운영 필수 기능 누락 방지 자동 검증

**강제 규칙:**
- ✅ `docs/v2/design/V2_COMPONENT_REGISTRY.json`은 운영 전 SSOT 부속 문서
- ✅ `scripts/check_component_registry.py` 정적 검사 + `scripts/v2_preflight.py` 런타임 검증 PASS 없으면 D206 진입 FAIL
- ✅ ops_critical 컴포넌트(Real MarketData/DB Strict/Redis/RunWatcher)는 Bootstrap 시 FeatureGuard 자동 검증
- ❌ 세부 목록은 Registry에만 기록 (SSOT_RULES에 전화번호부 금지)

**근거:**
- "만들었는데 안 쓰는 참사" 방지 (Silent Failure 차단)
- 상용급 시스템 안전장치 (하나라도 녹슬면 작동 중지)

### 7. OPS Gate Hardening (D205-15-6d)
**원칙:** False PASS 제거, Fail-Fast 복구

**강제 규칙:**
1. **WARN = FAIL 정책 (OPS Gate)**
   - Preflight/Component Registry 검증에서 WARNING은 FAIL로 처리
   - Redis/DB 미초기화, Config Key 누락, 필수 파일 부재 → 모두 FAIL
   - Optional은 명시적으로 "ops_critical: false" + "required: false"로만 허용

2. **Exit Code 전파 필수**
   - runner.run() 반환값 무시 금지
   - Winrate Guard 트리거 → non-zero exit code 반환 필수
   - Exception 발생 시 상위로 전파 (catch-and-ignore 금지)

3. **증거 기록 + 실패 전파 동시 수행**
   - winrate_guard_trigger.json 기록 ✅
   - 동시에 return 1 (또는 raise RuntimeError) ✅
   - "기록만 하고 PASS" 절대 금지 ❌

**근거:**
- 운영 환경에서 "거짓 양성(False PASS)"는 운영 사고로 직결
- FAIL은 반드시 FAIL로 보고되어야 함 (Silent Failure 금지)

**D206 진입 조건 (D205-17 Paper Acceptance):**
- baseline(20m) + longrun(1h) 실행 완료 필수
- 승률 50-95% 범위 (95% 이상은 비현실적)
- Winrate Guard 정상 작동 (0%/95%+ 감지 → FAIL)
- Evidence: KPI + Decision Trace + RunWatcher logs

---

## 📐 경로 규칙

### 코드 네임스페이스
```python
# ✅ V2 코드 (신규)
arbitrage/v2/
  ├── core/
  │   ├── engine.py           # ArbitrageEngine
  │   ├── order_intent.py     # OrderIntent 타입
  │   └── adapter.py          # ExchangeAdapter 인터페이스
  ├── adapters/
  │   ├── upbit_adapter.py
  │   └── binance_adapter.py
  └── harness/
      └── smoke_runner.py      # Smoke 진입점

# 📖 V1 코드 (레거시)
arbitrage/
  ├── exchanges/              # V1 어댑터
  ├── cross_exchange/         # V1 로직
  └── live_runner.py          # V1 런너
```

### 문서 경로
```
docs/
  ├── v2/                     # V2 신규 문서
  │   ├── SSOT_RULES.md       # 개발 규칙 SSOT
  │   ├── V2_ARCHITECTURE.md  # 아키텍처 SSOT
  │   ├── design/             # 설계 문서 (새 계약/표준)
  │   ├── reports/            # 검증 리포트 (매 D마다 1개)
  │   ├── runbooks/           # 운영 런북
  │   └── templates/          # 문서 템플릿
  ├── v1/                     # V1 마커
  │   └── README.md           # "레거시, Read-only"
  ├── D15~D106/               # V1 실제 문서 (이동 금지)
  └── D_ROADMAP.md            # SSOT (유일)
```

### 증거 저장 경로 (SSOT)
```
logs/evidence/
  └── <run_id>/               # YYYYMMDD_HHMMSS_<d-number>_<short_hash>
      ├── manifest.json       # 실행 메타데이터
      ├── gate.log            # Gate 실행 로그
      ├── git_info.json       # Git 상태 스냅샷
      └── cmd_history.txt     # 실행 커맨드 기록
```

**중요:** Evidence는 **logs/evidence/**에만 저장. docs/v2/evidence/ 금지.

---

## ✅ 검증 규칙

### GATE 통과 필수
모든 V2 작업은 아래 GATE를 100% PASS해야 커밋 가능:

1. **Doctor Gate**
   ```bash
   just doctor
   # pytest --collect-only 성공
   ```

2. **Fast Gate**
   ```bash
   just fast
   # 핵심 테스트 100% PASS
   ```

3. **Core Regression**
   ```bash
   just regression
   # 베이스라인 테스트 100% PASS
   ```

### 증거 저장 필수
모든 실행은 증거를 logs/evidence/에 저장:
- JSON 리포트 (KPI, 메트릭)
- 실행 로그
- 의사결정 근거

---

## 🔄 V1→V2 마이그레이션 규칙

### D200~D204: 공존 (현재)
- V1 코드 유지
- V2 코드 신규 작성 (v2 네임스페이스)
- 인터페이스 호환 계층 구축

### D205~D206: 점진적 전환
- V2 Engine 검증 (Profit Loop 통과 필수)
- Adapter별 검증 (Upbit → Binance → ...)
- PAPER 모드 100% 검증 후 진행

### D207+: V1 Deprecation
- V2 안정화 후 V1 코드 deprecated 마킹
- 3개월 유예 후 V1 제거

---

## 📝 문서 작성 규칙

### 1. Report (매 D마다 1개 필수)
- **경로:** `docs/v2/reports/D<번호>/D<번호>-<부제>_REPORT.md`
- **템플릿:** `docs/v2/templates/REPORT_TEMPLATE.md` 참조
- **필수 섹션:** Goal, AC, Plan, Execution Notes, GATE Result, Evidence, Diff Summary, PASS/FAIL
- **예:** `docs/v2/reports/D200/D200-3_REPORT.md`

### 2. Design (새 계약/표준이 생길 때만)
- **경로:** `docs/v2/design/<의미있는_이름>.md`
- **파일명:** D 번호 강제 제거, 의미 기반 이름 권장
  - ✅ `EVIDENCE_FORMAT.md`, `NAMING_POLICY.md`, `SSOT_MAP.md`
  - ❌ `D200_EVIDENCE_FORMAT.md` (D 번호 강제 금지)
- **필수 섹션:** Problem, Solution, Interface, Validation, SSOT 선언
- **필요 시:** ADR(Architecture Decision Record) 형식으로 의사결정 기록

### 3. Runbook (운영 절차)
- **경로:** `docs/v2/runbooks/<절차명>.md`
- **예:** `INCIDENT_RESPONSE.md`, `DEPLOYMENT_CHECKLIST.md`

### 4. Evidence (logs/evidence/에만 저장)
- **경로:** `logs/evidence/<run_id>/`
- **포맷:** SSOT = `docs/v2/design/EVIDENCE_FORMAT.md`
- **자동 생성:** watchdog/just 실행 시 자동으로 증거 폴더 생성

---

## 🛡️ 위반 시 조치

### SSOT 위반 (Critical)
- 새 ROADMAP 파일 생성 시 즉시 삭제
- docs/v2/ 외부에 V2 문서 작성 시 이동 또는 삭제

### 경로 규칙 위반 (High)
- v2 네임스페이스 외부에 V2 코드 작성 시 재작성
- 증거 저장 누락 시 재실행

### GATE 미통과 (Blocker)
- 커밋 금지
- 즉시 수정 → 재검증 → PASS 전까지 차단

---

## 📚 참고 문서

- `D_ROADMAP.md` - 프로젝트 전체 로드맵 (SSOT)
- `docs/v2/V2_ARCHITECTURE.md` - V2 아키텍처 정의
- `.windsurfrule` - 프로젝트 전역 규칙
- `global_rules.md` - 코딩 스타일 규칙

---

## 📋 Closeout Summary (강제 템플릿)

**모든 D-step 완료 시 반드시 이 템플릿으로 출력**

```markdown
# D<number> Closeout Summary

## Commit & Branch
- **Commit SHA:** <full_sha> (short: <short_sha>)
- **Branch:** <branch_name>
- **Compare Patch:** https://github.com/100aniv/XXX_ARBITRAGE_TRADING_BOT/compare/<before_sha>...<after_sha>.patch

## Gate Results
- **Doctor:** <PASS/FAIL> (<count> tests)
- **Fast:** <PASS/FAIL> (<count>/<total> tests, <duration>s)
- **Regression:** <PASS/FAIL> (<count>/<total> tests, <duration>s)

## KPI (핵심 지표만)
- **uptime_sec:** <value>
- **evaluated_ticks_total:** <value> (MUST > 0 for Reality Wiring tasks)
- **opportunities_count:** <value>
- **latency_p95_ms:** <value>
- **edge_mean:** <value>
- **error_count:** <value>

## Evidence
- **Path:** `logs/evidence/<run_id>/`
- **Files:** manifest.json, kpi.json, decision_trace.json, latency.json, ...
- **Size:** <total_size_kb> KB

## Status
- **Degraded:** <YES/NO>
- **Reason:** <degradation_reason or "N/A">
- **Unknown Issues:** <list or "None">

## Next Step
- **D<next>:** <next_task_title_one_line>

**템플릿 준수 규칙:**
1. ❌ **금지:** "커밋 대기중", "[pending]", "미정" 같은 임시 마커
2. ✅ **필수:** 모든 필드 채우기 (N/A는 허용)
3. ✅ **필수:** Compare Patch URL 생성 (GitHub compare/<before>...<after>.patch)
4. ✅ **필수:** evaluated_ticks_total > 0 확인 (Reality Wiring 작업 시)
5. ❌ **금지:** Closeout Summary 없이 커밋

---

## 🔄 Section B: AC 이동 프로토콜 (강제)

**목적:** AC 삭제 금지, 이동 시 원본/목적지 표기 강제, SSOT 파손 방지

**원칙:**
- AC는 절대 삭제하지 않음
- AC를 다른 D로 이동할 때는 원본/목적지 모두에 표기 필수
- 이동 사실이 명확히 드러나야 함 (audit trail)

**규칙 1: 원본 AC 표기 (MOVED_TO)**
```markdown
- ~~[ ] AC-7: Redis read/write(ms) 계측~~ [MOVED_TO: D205-11-2 / 2026-01-05 / d035a4a / 계측 인프라 분리]
```
- 취소선 사용 (`~~내용~~`)
- MOVED_TO 표기: `[MOVED_TO: <목적지 D> / <날짜> / <커밋> / <사유>]`
- 사유는 1줄로 간결하게

**규칙 2: 목적지 AC 표기 (FROM)**
```markdown
- [ ] AC-3: Redis read/write(ms) 계측 [FROM: D205-11-1 AC-7]
```
- FROM 표기: `[FROM: <원본 D> AC-<번호>]`
- 원본 AC를 명시하여 audit trail 유지

**규칙 3: Umbrella 매핑 (선택)**
- Umbrella 섹션에 "AC 이동 매핑" 서브섹션 추가 권장
- 이동 사실을 Umbrella에서도 명시 (가독성 향상)

**위반 시 조치:**
- 원본 AC 삭제 → 즉시 FAIL, 복원 필수
- 이동 표기 누락 → FAIL, MOVED_TO/FROM 추가 필수
- 이동되지 않은 AC를 원본에서 삭제 → FAIL

**예외:**
- DEPRECATED AC: 이동이 아니라 "폐기"일 경우 `[DEPRECATED: <사유> / <날짜>]` 표기

---

## 🔄 Section C: Work Prompt Template (Step 0~9)

**출처:** `docs/v2/templates/D_PROMPT_TEMPLATE.md` (358 lines) → SSOT_RULES로 완전 통합

**모든 D-step은 아래 Step 0~9를 순차 실행해야 함**

### Step 0: Bootstrap (강제, 문서 정독 포함)

**0-A. 작업 시작 증거 폴더 생성**
```bash
mkdir -p logs/evidence/STEP0_BOOTSTRAP_<timestamp>/
```
- bootstrap_env.txt (환경 정보)
- bootstrap_git.txt (Git 상태)

**0-B. Git / 브랜치 / 워킹트리 고정**
```bash
git rev-parse HEAD
git branch --show-current
git status --porcelain
```
- Dirty 상태면 이유 기록, 원칙적으로 Clean 상태로 정리 후 시작

**0-C. 캐시 / 중복 프로세스 / 런타임 오염 제거**
- `__pycache__` 제거
- 관련 python 프로세스 잔존 시 종료 (수정 반영 누락 방지)

**0-D. 인프라 전제 확인 (필요한 단계일 때만)**
- Postgres / Redis / Docker 상태 점검
- 필요 시 SSOT 규칙에 따른 clean reset

**0-E. SSOT 문서 정독 (도메인별, 디폴트)**

**필수 정독 순서:**
1. `D_ROADMAP.md`
2. `docs/v2/SSOT_RULES.md` (본 문서)
3. `docs/v2/design/SSOT_MAP.md`
4. `docs/v2/design/**` (해당 단계 관련 문서, **최소 2개**)
5. 직전 단계 `docs/v2/reports/Dxxx/*`

**Step 0 산출물 (증거):**
- `READING_CHECKLIST.md` (읽은 문서 목록 + 1줄 요약)
- "이번 작업에서 무엇을 재사용하고 무엇을 가져올지" 10줄 이내 요약

### Step 1: Repo Scan (재사용 목록)

**목표:** 새로 만들지 말고 이미 있는 것을 연결

**산출물:**
- `SCAN_REUSE_SUMMARY.md`
  - 재사용 모듈 3~7개
  - 재사용 이유 (각 1줄)

**새 파일이 필요한 경우:**
- "왜 없는지" 근거 명시

### Step 2: Plan (이번 턴 작업 계획)

- AC를 코드 / 테스트 / 증거로 어떻게 충족할지만 기술
- 분량: 5~12줄

**산으로 갈 선택 (사전 차단):**
- 과도한 리팩토링
- 인프라 확장

### Step 3: Implement (엔진 중심)

**알맹이 구현:**
- `arbitrage/v2/**`

**scripts/**:**
- CLI 파라미터 파싱
- 엔진 호출만 담당

**하위 호환 / 스키마 변경 시:**
- optional 필드로 확장
- manifest에 version 명시

**Context 관리:**
- 구현 종료 후 테스트 전
- 불필요한 로그 / 참고 파일 컨텍스트에서 제거

### Step 4: Tests (유닛 → Gate)

- 변경 범위 유닛 테스트

**Gate 3단 순차 실행:**
1. Doctor
2. Fast
3. Regression

**하나라도 FAIL 시:**
- 즉시 중단
- 수정
- 재실행

**"Fast만 충분" 같은 예외 주장 금지 (SSOT상 3단 필수)**

### Step 5: Smoke / Reality Check

**Smoke의 의미:**
- "안 죽는다"가 아니라
- 돈 버는 구조가 수치로 증명되는지

**필수 검증:**
- edge → exec_cost → net_edge 수치 존재

**0 trades 발생 시:**
- DecisionTrace로 차단 원인 수치화

**Negative Evidence 원칙:**
- 실패 / 이상 수치 발생 시
- 숨기지 말고 FAIL_ANALYSIS.md에 기록

**모든 결과는 evidence로 고정**

### Step 6: Evidence 패키징 (SSOT)

**Evidence 최소 구성:**
- manifest.json
- kpi.json

**(필요 시):**
- decision_trace.json
- latency.json
- leaderboard.json
- best_params.json

**README.md:**
- 재현 명령 3줄

### Step 7: 문서 업데이트 (SSOT 정합성)

**7-A. D_ROADMAP.md 반드시 업데이트**
- 상태 (DONE / IN PROGRESS)
- 커밋 SHA
- Gate 결과
- Evidence 경로

**AC (증거 기반 검증) 항목 전체 업데이트**
- 특정 수치 고정 금지
- "모든 AC 항목이 증거 기준으로 업데이트됨"이 명확히 드러나야 함

**7-B. SSOT 문서 동기화 강제 규칙**

ROADMAP이 업데이트되었고, 그 변경이 기존 설계 / 규칙 / 구조와 연관된다면 아래 문서들은 반드시 검토 대상:

- `docs/v2/SSOT_MAP.md`
- `docs/v2/design/SSOT_DATA_ARCHITECTURE.md`
- `docs/v2/design/SSOT_SYNC_AUDIT.md`
- `docs/v2/design/**`
- `docs/v2/INFRA_REUSE_INVENTORY.md`
- `docs/v2/CLEANUP_CANDIDATES.md`
- 관련 `docs/v2/reports/Dxxx/*`

**원칙:**
- 구조 / 철학 변경 없으면 억지 업데이트 금지
- 단, 낡은 정의 / 불일치 / 누락 발견 시 반드시 수정
- ROADMAP과 불일치한 문서는 기술 부채로 간주 → PASS 불가

### Step 8: Git (강제)

```bash
git status
git diff --stat
# SSOT 스타일 커밋 메시지
git commit -m "[Dxxx-y] <one-line summary>"
git push
```

### Step 9: Closeout Summary (출력 양식 고정)

**반드시 포함:**

**Commit:**
- [Full SHA] / [Short SHA]

**Branch:**
- [Branch Name]

**Compare Patch URL:**
```
https://github.com/100aniv/XXX_ARBITRAGE_TRADING_BOT/compare/<before_sha>...<after_sha>.patch
```

**Gate Results:**
- Doctor (PASS / FAIL)
- Fast (PASS / FAIL)
- Regression (PASS / FAIL)

**KPI:**
- 돈 버는 구조 핵심 지표 (net_edge_after_exec, positive_rate 등)

**Evidence:**
- bootstrap
- main run
- smoke / sweep 경로 전부 명시

---

## 🔄 Section D: Test Template (자동화/운영급)

**출처:** `docs/v2/templates/D_TEST_TEMPLATE.md` (224 lines) → SSOT_RULES로 완전 통합

**테스트 절대 원칙:**
- 테스트는 사람 개입 없이 자동 실행
- 중간 질문 금지
- FAIL 시 즉시 중단 → 수정 → 동일 프롬프트 재실행
- 의미 있는 지표 없으면 FAIL

### Test Step 0: 인프라 & 런타임 부트스트랩

**0-A. Python 가상환경**
```bash
python -m venv .venv
source .venv/bin/activate  # Linux/macOS
.venv\Scripts\activate     # Windows
python --version
pip --version
```

**0-B. 기존 실행 프로세스 종료 (강제)**
```bash
# Linux / macOS
pkill -f run_paper.py || true

# Windows (PowerShell)
Get-Process python* -ErrorAction SilentlyContinue | Stop-Process -Force
```
- 이전 paper/live 프로세스 잔존 시 FAIL

**0-C. Docker 인프라 확인**
```bash
docker ps
docker compose up -d
```
**필수 컨테이너:** postgres, redis, prometheus, grafana (있을 경우)

**0-D. DB / Redis 초기화 (강제)**
```bash
python scripts/reset_db.py
python scripts/reset_redis.py
```

### Test Step 1: 코드 무결성 & Fast Gate
```bash
python -m compileall .
pytest tests/fast --maxfail=1 --timeout=180 --timeout-method=thread
```

### Test Step 2: Core Regression
```bash
pytest tests/core --disable-warnings --timeout=180 --timeout-method=thread
```

### Test Step 3: Smoke PAPER Test (규칙 기반 선택)

**Smoke 유형 선택 규칙:**
1. **Micro-Smoke (1분)** - 경미한 변경 시
   - 조건: 설정/문서만 수정, 트레이딩 루프 미변경
   - 목적: 기본 런타임 검증 (프로세스 시작/종료, 크래시 없음)
   - 커맨드: `python scripts/run_paper.py --mode paper --duration 1m`

2. **Full Smoke (20분)** - 트레이딩 루프 변경 시
   - 조건: Engine/Adapter/Detector 코드 변경
   - 목적: 실제 거래 생성 검증 (주문 ≥ 1, 포지션 정상)
   - 커맨드: `python scripts/run_paper.py --mode paper --duration 20m`

**PASS 기준 (Full Smoke):**
- 주문 ≥ 1
- 포지션 정상
- 0 trades → FAIL + DecisionTrace

**PASS 기준 (Micro-Smoke):**
- 프로세스 정상 종료 (exit code 0)
- 크래시/예외 없음
- 로그 생성 확인

### Test Step 4: Monitoring 검증
```bash
curl http://localhost:9090/metrics
```
**필수 메트릭:** trade_count, net_edge_after_exec, latency_ms, error_rate

### Test Step 5: Extended PAPER
```bash
python scripts/run_paper.py --mode paper --duration 1h --monitoring on
```

### Test Step 6: Wallclock Verification (장기 실행 필수)

**적용 대상:**
- 장기 실행 테스트(≥1h)
- Wait Harness / 모니터링 / 대기 작업
- Phased Run / Early-Stop 포함 작업

**필수 증거:**
```
logs/evidence/Dxxx-y_<timestamp>/
- watch_summary.json (SSOT)
- heartbeat.json (선택)
- market_watch.jsonl (선택, 샘플 기록)
```

**watch_summary.json 필수 필드:**
```json
{
  "planned_total_hours": <number>,
  "started_at_utc": "<ISO 8601, timezone-aware>",
  "ended_at_utc": "<ISO 8601, 종료 시>",
  "monotonic_elapsed_sec": <number, SSOT>,
  "samples_collected": <number>,
  "expected_samples": <number>,
  "completeness_ratio": <number, 0.0~1.0>,
  "stop_reason": "<enum>"
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

### Test Step 7: Evidence 패키징
```
logs/evidence/Dxxx-y_TEST/
- manifest.json
- kpi.json
- metrics_snapshot.json
- decision_trace.json
- watch_summary.json (장기 실행 시 필수)
```

### Test Step 8: D_ROADMAP 업데이트
- PASS / FAIL
- Evidence 경로
- 신규 문제는 추가만 허용

### Test Step 9: Git
```bash
git status
git diff --stat
git commit -m "[TEST] Dxxx-y validation"
git push
```

### FAIL 처리 규칙
- 우회 금지
- 테스트 통과 전까지 반복

---

## 🔄 Section E: DocOps / SSOT Audit (Always-On)

**출처:** `docs/v2/templates/SSOT_DOCOPS.md` (90 lines) → SSOT_RULES로 완전 통합

**적용 범위:** 모든 D 단계 / 모든 커밋

**특히 아래 문서를 만지면 동기화 + DocOps Gate PASS 필수:**
- `D_ROADMAP.md` (유일 SSOT)
- `docs/v2/SSOT_RULES.md` (본 문서)
- `docs/v2/design/SSOT_MAP.md`
- `docs/v2/design/**`
- `docs/v2/reports/**`

### DocOps 불변 규칙 (SSOT 핵심 4문장)

1. SSOT는 `D_ROADMAP.md` 단 1개 (충돌 시 D_ROADMAP 채택)
2. D 번호 의미는 불변 (Immutable Semantics)
3. 확장은 브랜치(Dxxx-y-z)로만 (이동/재정의 금지)
4. DONE/COMPLETED는 Evidence 기반 (실행 증거 필수)

### DocOps Always-On 절차 (커밋 전에 무조건 수행)

**DocOps Gate (A) SSOT 자동 검사 (필수)**
```bash
python scripts/check_ssot_docs.py
```
- **Exit code 0** 아니면 즉시 중단(FAIL)
- 출력(로그)을 Evidence/리포트에 남겨야 DONE 가능

**DocOps Gate (B) 토큰 정책 스캔 (필수)**
```bash
python scripts/check_docops_tokens.py --config config/docops_token_allowlist.yml
```
- 정책 정의는 `docs/v2/design/DOCOPS_TOKEN_POLICY.md`에 고정
- 특정 D 단계(예: D205) 이슈가 있으면 해당 D 번호로 추가 스캔

**DocOps Gate (C) Pre-commit sanity (필수)**
```bash
git status
git diff --stat
```
- "원래 의도한 범위" 밖 파일이 섞였으면 FAIL (범위 밖 수정은 즉시 롤백)

### Evidence 저장 규칙 (gitignore와 충돌할 때)

**원칙:** DocOps Gate의 결과(명령 + 결과 요약)는 커밋 가능한 형태로 남겨야 함

- 추천: 각 D 리포트(`docs/v2/reports/...`)에 아래를 기록
  - 실행한 명령(원문)
  - exit code
  - 핵심 결과(예: 발견 0건 / 발견 N건 + 수정 내역)
- 런타임 로그(대용량)는 gitignore여도 OK지만,
  **검증 결과 요약(텍스트)**은 리포트에 남겨야 SSOT와 궁합이 맞다

### "한 번에 끝내는" 정의 (DONE 조건에 반드시 포함)

- DocOps Gate (A/B/C) **전부 PASS**
- SSOT 4점 문서(`D_ROADMAP/SSOT_RULES/SSOT_MAP/*`) 의미 동기화 완료
- 리포트에 DocOps 증거(명령 + 결과) 포함
- 그 다음에만 git commit/push

---

## 🔄 Section F: Design Docs 참조 규칙 (디폴트)

**목적:** docs/v2/design 정독을 "옵션"이 아니라 "디폴트"로 강제

**규칙:**
- 모든 D-step은 `docs/v2/design/`를 **반드시** 열어 읽고, 이번 D에 관련된 문서 **최소 2개** 요약
- 어떤 문서가 관련인지 모르면 "목차/파일명 기반 탐색 후 선택" 규칙

**Reading Tax (읽었다는 흔적 필수):**
- `READING_CHECKLIST.md`에 읽은 문서 목록 + 1줄 요약 기록
- "이번 작업에서 무엇을 재사용하고 무엇을 가져올지" 10줄 이내 요약

**Design 문서 종류 (예시):**
- `SSOT_MAP.md` - SSOT 계층 구조
- `SSOT_DATA_ARCHITECTURE.md` - Cold/Hot Path
- `SSOT_SYNC_AUDIT.md` - 정합성 감사
- `EVIDENCE_FORMAT.md` - Evidence 구조
- `NAMING_POLICY.md` - 파일/단계/지표/키 네이밍
- `REDIS_KEYSPACE.md` - Redis 키 구조
- 기타 도메인별 설계 문서

**위반 시 조치:**
- Design 문서 정독 누락 → FAIL, READING_CHECKLIST 작성 후 재실행
- "관련 없음" 주장 → FAIL, 최소 2개 선택 후 "관련 없는 이유" 명시

---

## 🔄 Section G: COMPLETED 단계 합치기 금지 (강제)

**원칙:** COMPLETED 단계에 신규 작업 추가 방지

**규칙:**
- COMPLETED 단계에 뭔가 추가하고 싶으면 무조건 **새 D/새 브랜치** 생성
- "단계 합치기"는 SSOT 리스크(삭제/누락/축약) 때문에 **절대 금지**

**예시:**
- ❌ **금지:** D205-11-2 COMPLETED에 "추가 계측" 작업 합치기
- ✅ **허용:** D205-11-3 신규 브랜치 생성 (추가 계측)

**위반 시 조치:**
- COMPLETED 단계 합치기 발견 → 즉시 FAIL, 새 D/새 브랜치로 분리

**근거:**
- D 번호 의미 불변 원칙 강화
- COMPLETED 단계의 원래 의미 변질 방지
- AC와 Evidence 불일치 방지

---

## 🔄 Section H: 3점 리더 / 임시 마커 금지 (강제)

**원칙:** 축약 흔적 제거 (SSOT 파손 방지)

**금지 대상 (명확한 목록):**
- `...` (3점 리더, ellipsis 문자)
- `…` (ellipsis 유니코드 문자 U+2026)
- 임시 작업 마커 (T*DO, T*D, FIX*E, X*X, H*CK 형태)
- `pending`, `later`, `작업중`, `보류중` (COMPLETED 문서에서)
- **참고:** 일반 마침표 `.`는 금지 대상이 아님 (문장 종결은 정상)

**규칙:**
- 로드맵/리포트/규칙 어디에도 위 금지 대상을 남기면 FAIL
- COMPLETED 문서에 임시 마커 **절대 금지**

**예시:**
- ❌ **금지:** `- AC-1~5: ...` (3점 리더 축약)
- ❌ **금지:** `- [ ] 임시마커: Redis 계측` (COMPLETED 문서에 임시 마커)
- ❌ **금지:** `- [ ] 작업중: 최적화` (COMPLETED 문서에 임시 마커)
- ✅ **허용:** `- AC-1: 구체적 내용` (전체 명시)
- ✅ **허용:** `문장을 마칩니다.` (일반 마침표는 정상)

**위반 시 조치:**
- 금지 마커 발견 시 즉시 중단, 전체 내용 명시 후 재실행

**check_ssot_docs.py와 동기화:**
- `check_ssot_docs.py`에서 이미 일부 검증 중
- 명시적 규칙화로 재발 방지 강화


## Section I: check_ssot_docs.py ExitCode=0 강제 (SSOT DocOps Gate)

**원칙:** "스코프 내 PASS" 같은 인간 판정 금지, 물리적 증거만 인정

**규칙:**
1. **ExitCode=0만 PASS:**
   - `check_ssot_docs.py` 실행 결과는 ExitCode=0일 때만 PASS
   - ExitCode=1이면 **무조건 FAIL** (이유 불문)
   - "스코프 내 FAIL 0개", "일부 PASS" 같은 표현은 **절대 금지**

2. **스코프 필터 (선택):**
   - 스코프가 필요하면 스크립트가 공식적으로 `--scope` 옵션 제공해야 함
   - `--scope` 실행도 ExitCode=0일 때만 PASS
   - out-of-scope 항목은 'ignored'로 출력되며 FAIL로 남지 않아야 함
   - **단, 가능하면 전체 문서 정리로 ExitCode=0 우선** (스코프 옵션은 최후 수단)

3. **메인 브랜치 병합 전 타협 금지:**
   - 메인 브랜치 병합 전 모든 DocOps 실패는 **예외 없이 수정**되어야 함
   - "나중에 수정", "별도 D에서 처리" 같은 미루기 금지
   - SSOT Infrastructure D-step (D000-x)에서는 **반드시 ExitCode=0 달성**

**증거 요구사항:**
- `ssot_docs_check_exitcode.txt` 파일 필수 (내용: `0`)
- `ssot_docs_check_raw.txt` 또는 `ssot_docs_check_final.txt` 필수 (전체 출력)
- Evidence 폴더에 위 파일이 없거나 ExitCode=1이면 **허위 보고**로 간주

**금지 표현 (D000-1에서 발생한 구멍):**
- ❌ "스코프 내 FAIL 0개" (전체 FAIL이 남아있음)
- ❌ "D000-1 범위만 깨끗하면 PASS" (인간 판정 개입)
- ❌ "out-of-scope는 별도 D에서" (SSOT Infrastructure에서 미루기 금지)
- ✅ "check_ssot_docs.py ExitCode=0" (물리적 증거만)

**예시:**

**❌ 금지 (D000-1 패턴 - 재발 방지):**
```markdown
AC-10: check_ssot_docs.py PASS (스코프 내 FAIL 0개, 증거: ssot_docs_check_final.txt)
```
- **문제:** ExitCode=1인데 "스코프 내"로 우기기
- **결과:** 나중에 폭탄 (D205 파일명 8개 등 방치)

**✅ 허용 (D000-2 패턴 - 물리적 증거):**
```markdown
AC-1: check_ssot_docs.py ExitCode=0 (증거: ssot_docs_check_exitcode.txt = 0)
```
- **물리적 증거:** `cat ssot_docs_check_exitcode.txt` → `0`
- **결과:** 전체 CLEAN, 우기기 불가능

**위반 시 조치:**
- ExitCode=1 상태로 "PASS" 선언 → 즉시 FAIL + 작업 Revert
- "스코프 내 PASS" 표현 사용 → 즉시 FAIL + 규칙 위반

**재발 방지 메커니즘:**
- D000-x (SSOT Infrastructure) 작업에서는 check_ssot_docs.py ExitCode=0 필수
- D200+ (트레이딩 로직) 작업에서는 스코프 제한 허용 (단, --scope 옵션 필수)
- 메인 브랜치 병합 전에는 **모든 D-step이 ExitCode=0 상태여야 함**

**SSOT 강제력:**
- 이 규칙은 "헌법"과 같음 (경찰 없는 헌법은 종이쪼가리)
- check_ssot_docs.py는 "경찰" 역할 (자동 집행)

---

## 🚫 Section J: Gate 회피 금지 (강제)

**원칙:** 규칙을 통과하기 위한 편법/꼼수는 SSOT를 더 빨리 망가뜨림

**금지 행위:**

1. **워딩 꼼수로 탐지 회피:**
   - ❌ 금칙어를 변형해서 숨기기 (T*DO, T.DO, FIX.ME 등)
   - ❌ 정규식 패턴으로 탐지 우회 시도
   - ✅ 실제 문제 해결 (임시 마커 완전 제거)

2. **파일 삭제로 규칙 회피:**
   - ❌ 규칙 위반 파일을 삭제해서 Gate 통과
   - ❌ Report/증거를 지워서 추적성 제거
   - ✅ rename으로 규칙 준수 (내용 보존)
   - ✅ Evidence 폴더로 이동 + 링크 유지

3. **ExitCode=0 아닌 상태에서 DONE 선언:**
   - ❌ ExitCode=1인데 "스코프 내 PASS"로 우기기
   - ❌ AC PENDING인데 "핵심 목표 달성"으로 DONE 표기
   - ✅ AC 100% + ExitCode=0 + Evidence 완비 시만 DONE
   - **위반 시:** 데이터 조작(Data Manipulation)으로 간주

**위반 시 조치:**
- Gate 회피 발견 → 즉시 FAIL + 작업 Revert
- 삭제된 유효 기록 → 복구 + rename 강제
- 데이터 조작 → 프로젝트 중단 (CTO 경고)

**검증 방법:**
- `git show <commit> --stat`: 삭제 라인 수 확인
- 삭제된 파일이 1000줄 이상 → 회피 의심, 복구 검토 필수
- Evidence 폴더에 "EVASION_AUDIT.md" 작성 강제

---

## 📋 Section K: D000 META/Governance 번호 체계 (강제)

**원칙:** D000은 META/Governance 전용, 실제 기능 개발과 혼재 금지

**D000 정의:**
- **용도:** 규칙/DocOps/레일 정비 전용 (SSOT Infrastructure)
- **금지:** 실거래/엔진/알고리즘 개발
- **구분:** D000은 개발 프로세스를 다룸, D200+는 제품/기능을 다룸

**네이밍 규칙:**
1. **D000 제목에 [META] 태그 강제:**
   - 예: `D000-1: [META] SSOT Rules Unify`
   - 예: `D000-2: [META] check_ssot_docs.py ExitCode=0 강제`

2. **D_ROADMAP에서 META RAIL 섹션 격리:**
   - D000 단계는 ROADMAP 상단 또는 별도 "META RAIL" 섹션에 배치
   - D200+ 실제 개발 라인과 물리적으로 분리

3. **브랜치명도 meta 표시:**
   - 예: `rescue/d000_1_meta_ssot_rules`
   - 예: `rescue/d000_2_meta_closeout`

**오해 방지:**
- D000은 "0번 단계"가 아니라 "메타 단계"
- D205 작업 중 D000이 튀어나오면 혼란 유발
- [META] 태그로 사람과 AI 모두 명확히 인식

**AC 요구사항:**
- D000-x 작업은 check_ssot_docs.py ExitCode=0 필수
- D000-x Report는 "왜 META 작업이 필요했는지" 명시 필수
- D000-x 완료 후 즉시 실제 개발 라인(D200+)으로 복귀

**위반 시 조치:**
- [META] 태그 누락 → D_ROADMAP 수정 강제
- D000에서 엔진/알고리즘 개발 → 즉시 FAIL + 번호 재할당
- ExitCode=0은 "0/1 판결" (인간 해석 개입 불가)

---

## 🏷️ Section L: API 및 버전 명칭 규칙 (강제)

**원칙:** 시즌 버전(V1/V2)과 외부 API 버전(v1/v3)의 혼동 방지

### L-1: 시즌 표기 (V1/V2) — 프로젝트 세대 전용

**정의:**
- **V1:** 첫 번째 아키텍처 세대 (레거시, arbitrage/exchanges/, docs/D15~D106)
- **V2:** 두 번째 아키텍처 세대 (Engine-centric, arbitrage/v2/, docs/v2/)

**규칙:**
- ✅ **허용:** `arbitrage/v2/`, `docs/v2/`, `config/v2/`
- ✅ **허용:** "V2 Engine", "V2 Architecture", "V1 레거시"
- ❌ **금지:** V1/V2를 외부 API 버전으로 혼동

### L-2: 외부 API 버전 — 의미 기반 명명 (MarketType)

**문제:**
- Binance API 경로: `/api/v3` (Spot), `/fapi/v1` (Futures)
- 여기서 v1, v3는 Binance 내부 버전 번호
- 시즌 V1/V2와 혼동 가능성 높음

**해결 — MarketType 기반 명명:**
```python
# ✅ 허용: 의미 기반 구분
MarketType = "SPOT" | "FUTURES"

BINANCE_SPOT_BASE_URL = "https://api.binance.com/api/v3"
BINANCE_FUTURES_BASE_URL = "https://fapi.binance.com/fapi/v1"

# 코드에서 사용
if market_type == "FUTURES":
    provider = BinanceFuturesProvider()
```

```python
# ❌ 금지: 숫자 기반 표현
API_V1 = ...   # 시즌 V1과 충돌
API_V3 = ...   # 숫자로 혼동 유발
R1 / R3 = ...  # 여전히 숫자 포함
```

**규칙:**
- ✅ **허용:** `MarketType.SPOT`, `MarketType.FUTURES`
- ✅ **허용:** `BINANCE_SPOT_BASE_URL`, `BINANCE_FUTURES_BASE_URL`
- ✅ **허용:** URL 내부의 `/api/v3`, `/fapi/v1`은 구현 디테일로만 취급
- ❌ **금지:** 코드/설정/문서에서 "v1 API", "v3 API" 표현
- ❌ **금지:** `API_V1`, `API_V3`, `R1`, `R3` 같은 변수/상수명

### L-3: API 폴더 경로 — 현재 유지, 개념만 분리

**현재 상태:**
```bash
arbitrage/
  └─ v2/
      └─ marketdata/
          └─ rest/
              └─ binance.py  # 내부에서 /api/v3, /fapi/v1 사용
```

**규칙:**
- ✅ **허용:** 현재 폴더 구조 유지 (api/v1, api/v3 등)
- ✅ **허용:** URL 경로는 구현 디테일로 숨김
- ❌ **금지:** 폴더 리네임을 D205-15-1에서 수행
- ❌ **금지:** 코드/config/README/ROADMAP에서 "v1/v3 API" 표현

**폴더 리네임 허용 조건 (D206 이후):**
1. D206 완료 (엔진 안정화)
2. MarketDataProvider 인터페이스 변경 없음
3. Pure Infra Refactor 전용 D-step 생성 (예: D2xx-INFRA-RENAME)
4. Gate: import 안정성만 검증

### L-4: SSOT 정합성 — 문서/코드/설정 통일

**검증 대상:**
- README.md
- D_ROADMAP.md
- docs/v2/**
- config/v2/config.yml
- arbitrage/v2/**

**검증 규칙:**
```bash
# 금지 패턴 검색 (커밋 전 수행)
rg "v1 API|v3 API|API_V1|API_V3|R1|R3" --type py --type md --type yaml
```

**위반 시 조치:**
- 금지 패턴 발견 → 의미 기반 명칭으로 수정 (SPOT/FUTURES)
- 숫자 기반 API 버전 표현 → 즉시 FAIL

### L-5: 예시 (Before → After)

**코드:**
```python
# ❌ Before
self.base_url = "https://api.binance.com/api/v3"  # "v3 API" 노출

# ✅ After
# URL은 내부 구현 디테일, 외부로 노출하지 않음
BINANCE_SPOT_BASE_URL = "https://api.binance.com/api/v3"
self.base_url = BINANCE_SPOT_BASE_URL  # MarketType 기반
```

**문서:**
```markdown
# ❌ Before
Binance v3 API를 사용하여 현물 데이터를 수집합니다.

# ✅ After
Binance Spot API를 사용하여 현물 데이터를 수집합니다.
```

**설정:**
```yaml
# ❌ Before
binance_api_version: "v3"

# ✅ After
binance_market_type: "SPOT"  # 또는 "FUTURES"
```

---

## 📊 Section M: Paper Acceptance REAL 강제 규칙 (D205-18-4)

**원칙:** Paper mode 실행 시 REAL 시장 데이터 강제, Mock 데이터 금지

**배경:**
- Paper mode는 "실제 체결 없이" 전략을 검증하는 단계
- 시장 데이터(Market Data)는 REAL이어야 하며, Mock은 금지
- 실행(Execution)은 MOCK이나, 시장 데이터는 실제 거래소 API 사용 필수

### 1. REAL 데이터 강제 규칙

**Paper mode 실행 시:**
```bash
# ✅ REAL 데이터 (필수)
python -m arbitrage.v2.harness.paper_runner --use-real-data

# ✅ PowerShell 스크립트 (REAL 데이터 강제)
.\scripts\run_paper_with_watchdog.ps1 -UseRealData

# ❌ Mock 데이터 (금지)
python -m arbitrage.v2.harness.paper_runner --use-mock-data
```

**강제 검증:**
- `paper_runner.py` 실행 시 `--use-real-data` 플래그 필수
- KPI에 `marketdata_mode: "REAL"` 필드 존재 확인
- 거래소별 market data 연결 상태 확인:
  - `upbit_marketdata_ok: true`
  - `binance_marketdata_ok: true`
  - `real_ticks_ok_count > 0`
  - `real_ticks_fail_count == 0`

### 2. Winrate 역설 검증 (50-90% 범위)

**원칙:** Paper mode winrate는 50-90%가 정상, 95%+ 또는 100%는 의심

**검증 규칙:**
- **50-90%:** ✅ PASS (정상 범위)
- **95%+ ~ 99%:** ⚠️ WARNING (너무 완벽, Mock execution 한계)
- **100%:** ❌ FAIL (비현실적, 실패 케이스 미반영)

**Winrate WARNING 처리:**
- WARNING은 FAIL이 아니므로 조건부 PASS 허용
- 원인: Paper mode는 시장 데이터는 REAL이나 execution은 MOCK
- 실제 체결 지연/슬리피지/거부가 미반영
- Live mode 전환 시 50-90% 범위로 수렴 예상

**Evidence 요구사항:**
```json
{
  "winrate_pct": 98.0,
  "wins": 49,
  "losses": 1,
  "closed_trades": 50,
  "marketdata_mode": "REAL",
  "upbit_marketdata_ok": true,
  "binance_marketdata_ok": true,
  "real_ticks_ok_count": 50,
  "real_ticks_fail_count": 0
}
```

### 3. DB Strict Mode 강제

**원칙:** Paper mode 실행 시 DB strict mode 필수 (실제 DB 사용)

**강제 규칙:**
```bash
# ✅ Strict mode (필수)
python -m arbitrage.v2.harness.paper_runner --db-mode strict

# ❌ Memory mode (금지)
python -m arbitrage.v2.harness.paper_runner --db-mode memory
```

**검증:**
- `db_inserts_ok > 0` (실제 DB에 데이터 저장)
- `db_inserts_failed == 0` (DB 실패 없음)
- PostgreSQL 연결 정상 확인

### 4. Baseline + Longrun 실행 필수

**원칙:** Paper Acceptance는 단일 실행이 아니라 다단계(chain) 실행

**필수 Phase:**
1. **Baseline (20m):** 초기 검증, 기본 KPI 수집
2. **Longrun (60m):** 장기 안정성 검증

**Profile:**
- `quick` profile: 짧은 duration 허용 (개발/검증용)
- `ssot` profile: SSOT 요구 duration 강제 (운영급)

**실행 예시:**
```powershell
.\scripts\run_paper_with_watchdog.ps1 `
  -Phases "baseline,longrun" `
  -Durations "20,60" `
  -Profile "quick" `
  -DbMode "strict" `
  -UseRealData
```

### 5. Evidence 패키징 필수

**필수 파일:**
- `chain_summary.json` - 전체 chain 실행 결과
- `daily_report_YYYY-MM-DD.json` - 일일 PnL/OPS 리포트
- `daily_report_status.json` - 리포트 생성 상태
- `D205_18_4_ANALYSIS.md` - Winrate WARNING 분석 (필요 시)
- `README.md` - 재현 명령 및 핵심 지표

**Evidence 경로:**
```
logs/evidence/d204_2_chain_YYYYMMDD_HHMM/
├── chain_summary.json
├── daily_report_2026-01-12.json
├── daily_report_status.json
├── D205_18_4_ANALYSIS.md
└── README.md
```

### 6. 적용 범위

**필수 적용:**
- D205-18-4 Paper Acceptance Execution
- 모든 Paper mode 검증 작업
- Gate Regression에서 Paper 테스트 실행 시

**예외 없음:**
- Paper mode 실행 시 REAL 데이터는 항상 필수
- Mock 데이터는 개발 디버깅 외에는 사용 금지

---

## Section N: Operational Hardening - Core Integration (D205-18-4R)

**목적:** RunWatcher, heartbeat, wallclock 등 운영 체크를 코어로 중앙화하여 스크립트 의존성 제거

**Constitutional Principles (헌법 원칙):**

### 1. Operational Protocol Governance

> **"운영 프로토콜은 [`OPS_PROTOCOL.md`](OPS_PROTOCOL.md)를 따른다. 충돌 시 SSOT_RULES.md가 우선한다."**

**SSOT 우선순위 (불변):**
1. **SSOT_RULES.md (본 문서)** - 헌법 (Constitutional principles)
2. **D_ROADMAP.md** - 프로세스 SSOT (상태/목표/AC)
3. **OPS_PROTOCOL.md** - 운영 절차 (런북/프로토콜)
4. **V2_ARCHITECTURE.md** - 아키텍처 설계

**충돌 해결:**
- SSOT_RULES ↔ OPS_PROTOCOL 충돌 시 → SSOT_RULES 우선
- OPS_PROTOCOL ↔ V2_ARCHITECTURE 충돌 시 → OPS_PROTOCOL 우선
- 모든 문서는 D_ROADMAP.md 참조 (Process SSOT)

- **OPS_PROTOCOL.md:** 실행 절차, 검증 기준, Evidence 관리, Healthcheck 연동 등 상세 런북
- **SSOT_RULES.md (본 문서):** 헌법 원칙 및 불변 규칙

### 2. Core Principles (불변 원칙)

#### 2.1 Wallclock Duration Principle
- **원칙:** 모든 duration_seconds는 wall-clock 기준 (실제 경과 시간)
- **금지:** iteration 기반 추정, sleep 누적, start_time 기준 계산
- **상세:** [`OPS_PROTOCOL.md#3-run-protocol`](OPS_PROTOCOL.md#3-run-protocol-실행-프로토콜)

#### 2.2 Heartbeat Density Principle
- **원칙:** heartbeat.jsonl 필수 생성 + 밀도 검증 (60초 간격, 65초 초과 간격 FAIL)
- **금지:** heartbeat 누락, RunWatcher 스킵
- **상세:** [`OPS_PROTOCOL.md#2-operational-invariants`](OPS_PROTOCOL.md#2-operational-invariants-불변-조건)

#### 2.3 Evidence Completeness Principle
- **원칙:** Evidence Minimum Set 모든 파일 존재 (chain_summary/heartbeat/kpi/manifest)
- **금지:** 파일 누락, 부분 저장
- **상세:** [`OPS_PROTOCOL.md#5-evidence-minimum-set`](OPS_PROTOCOL.md#5-evidence-minimum-set-증거-최소셋)

#### 2.4 WARN = FAIL Principle
- **원칙:** 모든 WARNING은 Exit Code 1 (가짜 PASS 차단)
- **금지:** WARNING을 PASS로 간주
- **상세:** [`OPS_PROTOCOL.md#32-exit-code-규약`](OPS_PROTOCOL.md#32-exit-code-규약)

#### 2.5 Atomic Evidence Flush Principle
- **원칙:** 정상/비정상/강제 종료 시 무조건 Evidence 저장 (finally 블록)
- **금지:** Evidence 저장 스킵, 조건부 저장
- **상세:** [`OPS_PROTOCOL.md#53-atomic-evidence-flush`](OPS_PROTOCOL.md#53-atomic-evidence-flush)

### 3. Enforcement (강제 적용)

**필수 적용:**
- D205-18-4R 이후 모든 Paper/Live/Smoke/Baseline/Longrun 실행
- Gate Regression 모든 Paper 테스트
- Docker/compose 배포 환경

**예외 없음:**
- 개발 디버깅도 OPS_PROTOCOL 준수 (Mock 데이터 예외 없음)

### 4. Script Deprecation (스크립트 폐기 방향)

**원칙:**
- ✅ arbitrage/v2/** 중심 구조 (엔진 중심)
- ❌ scripts/run_*.py 로직 포함 금지 (CLI arg parsing만)
- ✅ "thin wrapper" 규정: [`OPS_PROTOCOL.md`](OPS_PROTOCOL.md) 참조

**폐기 대상:**
- `run_paper_with_watchdog.ps1` duration 검증 → orchestrator로 이동
- `paper_chain.py` duration 검증 → metrics로 이동

### 5. Container Parity (컨테이너 패리티)

**원칙:**
- 로컬 PC와 Docker/compose 환경 동일성 보장
- heartbeat.jsonl 기반 healthcheck 필수
- **상세:** [`OPS_PROTOCOL.md#6-docker-healthcheck-integration`](OPS_PROTOCOL.md#6-docker-healthcheck-integration)

### 6. Failure Recovery (장애 복구)

**원칙:**
- SIGTERM 수신 후 10초 내 Evidence Flush 완료
- 모든 Failure Mode에 대한 Recovery 절차 정의
- **상세:** [`OPS_PROTOCOL.md#8-failure-modes--recovery`](OPS_PROTOCOL.md#8-failure-modes--recovery)

---

## Section M: Taxonomy 정의 (D206 Ops Protocol + Mode/Profile 표준화)

**Version:** 2.0 (D206 REPLAN 기반)  
**Effective Date:** 2026-01-15  
**Status:** ENFORCED

### M-1: 용어 표준화 (강제)

**원칙:** RunMode/RunProfile/Phase 혼용 금지, 단일 정의 강제

**M-1.1: RunMode (실행 환경)**
- **정의:** 엔진이 실행되는 환경
- **허용 값:** BACKTEST | PAPER | LIVE
- **금지:** "모드"와 "프로파일"을 섞어 쓰기, "phase"를 "mode"로 혼용
- **예시:**
  - ✅ 허용: `execution.environment = "paper"`
  - ❌ 금지: `mode = "smoke"` (smoke는 profile)
  - ❌ 금지: `phase = "live"` (live는 environment)

**M-1.2: RunProfile (실행 프로파일)**
- **정의:** 실행 시간, 데이터 양, 검증 강도 등의 설정 세트
- **허용 값:** SMOKE | BASELINE | LONGRUN | ACCEPTANCE | EXTENDED
- **예시:**
  - SMOKE: 5분 실행 + 최소 evidence (빠른 검증)
  - BASELINE: 20분 실행 + 표준 evidence (일반 검증)
  - LONGRUN: 60분+ 실행 + 추가 계측 (장기 안정성 검증)
  - ACCEPTANCE: 상용급 검증 (BASELINE + LONGRUN 조합)
  - EXTENDED: 확장 검증 (특수 시나리오)

**M-1.3: Phase (단계)**
- **정의:** 체인 실행의 구간 (예: baseline 20m, longrun 60m)
- **특징:** Profile이 Phase 구성을 결정
- **예시:** ACCEPTANCE 프로파일 = baseline 20m + longrun 60m 2개 Phase

**M-1.4: ValidationRigor (검증 강도)**
- **정의:** 테스트/검증의 엄격도
- **허용 값:** QUICK | SSOT
- **예시:**
  - QUICK: 빠른 검증 (슬리피지/latency 모델 OFF)
  - SSOT: 상용급 검증 (슬리피지/latency/partial 강제 ON)

---

### M-2: PAPER 상용급 정의 (강제)

**원칙:** PAPER는 "실시간 시장 데이터 + 모의 체결"이며, 현실 마찰 모델 필수

**M-2.1: PAPER 모드 정의**
- **실시간 데이터:** 시장 데이터, 계좌/포지션/호가 조회는 LIVE와 동일
- **차이점:** order_submit만 모의 체결 (실제 거래소에 주문 전송 안 함)
- **금지:** Mock 데이터 사용 (use_real_data=false는 unit test만)

**M-2.2: 현실 마찰 모델 주입 (필수)**
- **슬리피지 모델:** 주문 가격과 체결 가격의 차이 시뮬레이션
- **지연 모델:** 주문 전송 ~ 체결 확인 시간 시뮬레이션
- **부분 체결 모델:** 전량 체결 실패, 일부만 체결 시뮬레이션
- **실패 모델:** 주문 거절, 타임아웃, 레이트리밋 429 시뮬레이션

**M-2.3: 승률 경고 기준**
- **WARNING:** winrate ≥ 95% → "현실 마찰 모델 미주입" 의심, edge_after_cost로 교차 검증 필수
- **FAIL:** winrate = 100% → 계약 위반 (filled_qty 뻥튀기) 또는 Mock 데이터 사용
- **정상 범위:** winrate 50~80% (현실적 범위)

**M-2.4: SSOT Rigor 강제**
- **조건:** `execution.rigor = "ssot"` 시
- **강제 활성화:** FillModelConfig.enable_slippage/latency/partial_fill = true
- **검증:** 승률이 비정상적으로 높으면 FAIL

---

### M-3: LIVE 모드 설계 (계획 단계, SSOT 반영 필수)

**원칙:** LIVE 구현은 Gate로 지연 가능, 설계+SSOT 반영은 필수

**M-3.1: LIVE 모드 정의**
- **실시간 데이터:** 시장 데이터, 계좌/포지션/호가 조회 REAL
- **실제 체결:** order_submit 시 실제 거래소에 주문 전송
- **금지:** LIVE 모드 구현 없이 "설계 결함"으로 FAIL

**M-3.2: LIVE 모드 Invariants (OPS_PROTOCOL 반영 필수)**
- **Wallclock Invariant:** 무한루프 또는 스케줄러 루프일 수 있으므로 "윈도우 단위(예: 1h rolling)" 재정의
- **Heartbeat Invariant:** 60초 주기 heartbeat 필수 (≤65초)
- **DB Invariant:** closed_trades × 3 (order+fill+trade)
- **Evidence Invariant:** 필수 파일 존재 + 크기 > 0
- **SIGTERM Invariant:** 10초 graceful shutdown

**M-3.3: LIVE 모드 StopReason**
- **NORMAL:** 계획 시간 도달 또는 스케줄 완료
- **ERROR_INVARIANT_VIOLATION:** Invariant 위반 (Wallclock/Heartbeat/DB/Evidence)
- **MANUAL_HALT:** 운영자 수동 중단
- **RISK_DRAWDOWN:** 리스크 임계치 초과 (손실 한도, 연속 손실 등)

**M-3.4: LIVE 모드 현재 상태**
- **설계:** SSOT 반영 완료 (OPS_PROTOCOL.md, V2_ARCHITECTURE.md, D_ROADMAP.md)
- **구현:** Gate 대기 (D206-0~4 완료 후)
- **검증:** LIVE 진입 시 Fail Fast (FX Integration, Risk Guard 등 필수)

---

### M-4: CLI 인자 표준화 (강제)

**원칙:** 모든 runner 스크립트는 --environment, --profile, --rigor 인자 사용

**M-4.1: 표준 인자**
- `--environment <BACKTEST|PAPER|LIVE>`: 실행 환경
- `--profile <SMOKE|BASELINE|LONGRUN|ACCEPTANCE|EXTENDED>`: 실행 프로파일
- `--rigor <QUICK|SSOT>`: 검증 강도
- `--duration <시간>`: 실행 시간 (선택, profile 기본값 override)

**M-4.2: 금지 인자**
- ❌ `--mode <값>`: mode와 profile 혼용 금지
- ❌ `--phase <값>`: phase는 내부 구현 디테일
- ❌ `--test <값>`: 모호한 표현

**M-4.3: 예시**
```bash
# PAPER + SMOKE (5분 빠른 검증)
python scripts/run.py --environment paper --profile smoke --rigor quick

# PAPER + BASELINE (20분 표준 검증, SSOT 강제)
python scripts/run.py --environment paper --profile baseline --rigor ssot

# PAPER + LONGRUN (60분 장기 검증)
python scripts/run.py --environment paper --profile longrun --rigor ssot

# LIVE + BASELINE (실제 거래, 20분)
python scripts/run.py --environment live --profile baseline --rigor ssot
```

---

### M-5: 적용 범위 (강제)

**M-5.1: SSOT 문서 동기화**
- `docs/v2/SSOT_RULES.md`: Section M (본 문서)
- `docs/v2/OPS_PROTOCOL.md`: 모드별 Invariant, StopReason, Evidence 규격
- `docs/v2/V2_ARCHITECTURE.md`: Mode/Profile/Engine 다이어그램, LIVE 경로 포함
- `D_ROADMAP.md`: D206-0~4 재정의, D207 인프라 연기

**M-5.2: 코드 적용**
- `config/v2/config.yml`: execution.environment/profile/rigor 블록
- `arbitrage/v2/core/config.py`: ExecutionEnvironmentConfig dataclass
- `arbitrage/v2/domain/fill_model.py`: FillModelConfig (slippage/latency/partial)

**M-5.3: 검증 규칙**
- ❌ **금지:** 코드/설정/문서에서 "mode"와 "profile" 혼용
- ❌ **금지:** LIVE 모드 설계 누락 (SSOT에 LIVE 경로 명시 필수)
- ✅ **허용:** LIVE 구현은 Gate로 지연 (설계는 필수)

**M-5.4: Gate 검증**
```bash
# 금지 패턴 탐지
rg "mode.*profile|profile.*mode" --type py --type md --type yaml
rg "phase.*environment|environment.*phase" --type py --type md --type yaml
```

---

## 🛡️ Section N: Artifact-First Gate & No Partial (D206-1 HARDENED)

**출처:** Constitutional Protocol v2.4 (2026-01-16)
**목적:** Runner 비대화 원천 차단, 부분 완료 금지, Gate 무결성 보장

### N-1: Artifact-First Gate (강제)

**원칙:** Gate는 Runner가 아닌 Core 산출물을 검증한다.

**강제 규칙:**
1. **검사 대상**
   - ✅ **허용:** Evidence manifest (kpi_summary.json, manifest.json)
   - ✅ **허용:** Report schema (EVIDENCE_FORMAT.md)
   - ❌ **금지:** Runner 속성/필드/프로퍼티 직접 검사
   
2. **Gate 설계**
   - Registry/Preflight는 Runner property 검사 금지
   - Core가 생성하는 Report/Manifest/Schema 검사로 고정
   - Runner 비대화를 유발하는 Gate는 설계 결함(FAIL)

3. **Runner 책임 범위 (Thin Wrapper)**
   - ✅ config 로드
   - ✅ engine/runtime 생성 호출
   - ✅ engine 실행 호출
   - ✅ exit code 전파
   - ✅ evidence flush 트리거
   - ❌ **금지:** Gate 통과용 상태필드 추가 (wins/losses/marketdata_mode/db_mode 등)

### N-2: No Partial Completion (강제)

**원칙:** Gate ExitCode=0이 아니면 COMPLETED/DONE 금지

**강제 규칙:**
1. **금지 표현**
   - ❌ "PARTIAL", "부분 완료", "범위 밖", "시간 제약", "기술 부채"
   - ❌ "일단 진행", "나중에", "pending", "later"
   - ❌ ExitCode≠0 상태에서 COMPLETED 선언

2. **DONE 조건 (전부 만족 필수)**
   - DocOps Gate: ExitCode=0
   - Registry Gate: ExitCode=0 AND WARNING=0
   - Preflight Gate: ExitCode=0 AND WARNING=0
   - pytest: ExitCode=0 AND SKIP=0
   - D_ROADMAP: 상태/AC/증거/커밋 정확히 일치

3. **위반 시 조치**
   - 즉시 FAIL + 작업 Revert
   - PARTIAL 문구 발견 → 제거 또는 재작업

### N-3: WARN=FAIL / SKIP=FAIL (강제)

**원칙:** 모든 WARNING과 SKIP은 FAIL로 처리

**강제 규칙:**
1. **WARN=FAIL**
   - Registry/Preflight에서 warning > 0 → sys.exit(1)
   - "WARNING은 나중에" 같은 서술로 덮기 금지

2. **SKIP=FAIL**
   - pytest에서 SKIP > 0 → FAIL
   - "테스트는 나중에" 같은 태만 금지
   - 예외: config 기반 allowlist + 문서 + Evidence 동시 반영

3. **No-Escape 루틴**
   - AI가 '나중에 고치겠다'는 서술로 Gate 우회 시 즉시 FAIL
   - 모든 Gate 스크립트는 WARNING/SKIP > 0이면 sys.exit(1)

### N-4: 검증 (Gate 명령)

```bash
# DocOps Gate
python scripts/check_ssot_docs.py  # ExitCode=0

# Registry Gate
python scripts/check_component_registry.py  # ExitCode=0, WARNING=0

# Preflight Gate
python scripts/v2_preflight.py  # ExitCode=0

# Test Gate
pytest -q  # ExitCode=0, SKIP=0
```

---

## 🔜 다음 단계

이 문서는 **SSOT**입니다. 규칙 변경 시 반드시 이 문서를 업데이트하세요.

**업데이트 규칙:**
1. 새 규칙 추가 시 → 해당 섹션 업데이트 + 예시 추가
2. 규칙 변경 시 → 커밋 메시지에 `[SSOT_RULES]` 태그
3. 순서 변경 시 → D_ROADMAP 동기화 필수

**참조:**
- SSOT_MAP: `docs/v2/design/SSOT_MAP.md`
- Evidence: `docs/v2/design/EVIDENCE_FORMAT.md`
- Architecture: `docs/v2/V2_ARCHITECTURE.md` - V2 아키텍처 정의
- `.windsurfrule` - 프로젝트 전역 규칙
- `global_rules.md` - 코딩 스타일 규칙

---

**이 규칙은 V2 개발 전반에 걸쳐 강제 적용되며, 위반 시 작업이 차단됩니다.**
