---
trigger: always_on
---

# Arbitrage V2 Workspace Rules (SSOT 2-기둥 구조)

**Version:** 2.0 (SSOT 2-기둥 기반)  
**Effective Date:** 2026-01-05  
**Status:** ENFORCED

---

## 기둥 1: D_ROADMAP.md (상태 데이터베이스)

**역할:** "우리는 지금 어디에 있고, 목표가 무엇이며, 어떤 AC를 완료했는가?"

**성격:** 수정이 극도로 제한된 계약서

**강제 규칙:**
- ✅ D_ROADMAP.md가 유일 SSOT (다른 문서는 참조/동기화 대상)
- ❌ D_ROADMAP_V2.md, D_ROADMAP_V3.md 같은 분기 금지
- ✅ D 번호 의미 불변 (변경 금지)
- ✅ AC 추가만 허용 (삭제/축소 금지)
- ✅ 증거 경로 명시 필수 (logs/evidence/ 고정)

---

## 기둥 2: docs/v2/SSOT_RULES.md (운영 헌법 + SOP)

**역할:** "작업은 어떤 순서로 하고, 테스트는 무엇을 하며, 문서는 어떻게 검증하는가?"

**성격:** 모든 방법론이 집대성된 유일한 법전

**포함 내용:**
- 핵심 원칙 (SSOT 단일화, D 번호 불변, Report 파일명 규칙)
- 강제 금지 사항 (파괴적 이동/삭제, 오버리팩토링, 스크립트 중심 실험)
- Scan-First → Reuse-First 강제 규칙
- Profit Loop 강제 규칙 (D205-4~12 필수)
- **프롬프트 템플릿** (반복 작업 표준화)
- **테스트 템플릿** (Gate 검증 표준화)
- **DocOps 검증** (문서 일관성 검증)

---

## 참고 파일 (메인은 아니지만 반영 필수)

1. **docs/v2/V2_ARCHITECTURE.md**
   - Engine-Centric 설계 계약
   - OrderIntent, Adapter, Engine 플로우

2. **docs/v2/design/** (설계 문서)
   - SSOT_MAP.md: 전체 SSOT 목록 및 규칙
   - EVIDENCE_FORMAT.md: 실행 증거 저장 포맷
   - NAMING_POLICY.md: 네이밍 정책
   - INFRA_REUSE_INVENTORY.md: V1 인프라 재사용 전략

3. **README.md**
   - 프로젝트 소개 및 SSOT 문서 7종 목록
   - 금지 사항 (SSOT 분기, 환경별 설정 중복)

---

## 강제 규칙 (항상 동일, 생략 금지)

### SSOT 원칙
- ✅ D_ROADMAP.md 단 1개 (유일한 원천)
- ✅ D번호 의미 불변 (확장은 브랜치 Dxxx-y-z만)
- ✅ 기존 목표 / AC / 증거 요구사항 절대 삭제 금지
- ✅ 새 문제 발견 시 "추가(additive)"만 허용 (덮어쓰기 / 축소 / 무효화 금지)

### 개발 원칙
- ✅ 돈 버는 아비트라지 로직 / 알고리즘 우선
- ✅ 엔진 중심 구조 (arbitrage/v2/**)
- ✅ scan-first → reuse-first
- ✅ 중복 / 반복 금지

### 검증 원칙
- ✅ Gate 3단 강제 (Doctor / Fast / Regression)
- ✅ 증거(Evidence) 없으면 PASS 주장 금지
- ✅ Wallclock Verification (장기/대기/모니터링 작업 필수)
- ✅ watch_summary.json 자동 생성 필수

### 운영 원칙
- ✅ 작업 종료 시 반드시 Git commit (+ push)
- ✅ 필요 시 DB / Redis / 프로세스 / 캐시 정리 강제
- ✅ 실패 시 오염 방지 (Rollback 원칙)

---

## 경로 규칙 (SSOT)

### 코드 네임스페이스