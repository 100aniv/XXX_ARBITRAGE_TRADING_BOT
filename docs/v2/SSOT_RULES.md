# V2 SSOT Rules (Single Source of Truth)

**Version:** 1.0  
**Effective Date:** 2025-12-29  
**Status:** ENFORCED

---

## 🎯 핵심 원칙

### 1. SSOT는 D_ROADMAP.md 단 1개
- ❌ **금지:** D_ROADMAP_V2.md, D_ROADMAP_V3.md 같은 SSOT 분기
- ✅ **허용:** D_ROADMAP.md 내부에서 V2 섹션으로 관리
- **이유:** 로드맵 분산은 혼란과 동기화 실패를 초래

### 2. V2 문서는 docs/v2/ 단일 경로
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
- ❌ run_d108_*.py, run_v2_test.py 같은 일회성 스크립트
- ✅ 엔진 기반 Smoke Harness (재사용 가능)
- ✅ Adapter 패턴으로 거래소별 분리

### 4. LIVE 중단 유지
- ❌ V2에서도 실거래 기본 금지
- ✅ PAPER/READ_ONLY 모드 기본
- ✅ Smoke 테스트는 Mock/Stub만 사용

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

### Phase 0: 공존 (현재)
- V1 코드 유지
- V2 코드 신규 작성 (v2 네임스페이스)
- 인터페이스 호환 계층 구축

### Phase 1: 점진적 전환
- V2 Engine을 V1 LiveRunner에서 호출
- Adapter별 검증 (Upbit → Binance → ...)
- PAPER 모드 100% 검증 후 진행

### Phase 2: V1 Deprecation
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
- **포맷:** SSOT = `docs/v2/design/EVIDENCE_FORMAT.md` (또는 EVIDENCE_SPEC.md)
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

**이 규칙은 V2 개발 전반에 걸쳐 강제 적용되며, 위반 시 작업이 차단됩니다.**
