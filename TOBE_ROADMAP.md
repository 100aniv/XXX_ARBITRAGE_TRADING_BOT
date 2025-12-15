# arbitrage-lite TO-BE 로드맵 (최종 단계 정의)

**Last Updated:** 2025-12-15
**Purpose:** D 단계별 "큰 줄기" 정의 (상세는 각 D문서로)

---

## 원칙

1. **D_ROADMAP.md와 D 번호 1:1 일치**
2. **각 D 단계 정의 필수 항목**: Purpose, Done Criteria, Evidence
3. **상세 내용은 D 문서로**

---

## D82: TopN Multi-Symbol & Threshold Recalibration

### Purpose
- TopN Multi-Symbol 실행 환경 구축

### Done Criteria
- [ ] TopN Runner 구현 완료

### Evidence
- docs/D82/D82_*.md

---

## D83: L2 Orderbook Fill Model Integration

### Purpose
- L2 Orderbook 데이터 통합

### Done Criteria
- [ ] L2 Orderbook Adapter 구현

### Evidence
- docs/D83/D83_0_L2_ORDERBOOK_DESIGN.md

---

## D84: Fill Model Refactor & Validation

### Purpose
- Fill Model AS-IS 분석 및 재설계

### Done Criteria
- [ ] Fill Model AS-IS 분석 완료

### Evidence
- docs/D84/D84-0_FILL_MODEL_ASIS.md

---

## D85: Multi L2 Available Volume & Runtime Hotfix

### Purpose
- Multi L2 Available Volume 계산 로직 구현

### Done Criteria
- [ ] L2 Available Volume 설계 완료

### Evidence
- docs/D85/D85-0_L2_AVAILABLE_VOLUME_DESIGN.md

---

## D86: Fill Model 20m PAPER Validation & Recalibration

### Purpose
- Fill Model 20분 PAPER 검증

### Done Criteria
- [ ] Fill Model 20m PAPER 검증 완료

### Evidence
- docs/D86/D86-1_FILL_MODEL_20M_PAPER_VALIDATION_REPORT.md

---

## D87: Multi-Exchange Execution & Zone Selection

### Purpose
- Multi-Exchange 실행 엔진 설계

### Done Criteria
- [ ] Multi-Exchange Execution 설계 완료

### Evidence
- docs/D87/D87_0_MULTI_EXCHANGE_EXECUTION_DESIGN.md

---

## D88: Entry BPS Diversification

### Purpose
- Entry BPS 다양화 전략 구현

### Done Criteria
- [ ] Entry BPS Diversification 설계 완료

### Evidence
- docs/D88/D88_0_ENTRY_BPS_DIVERSIFICATION.md

---

## D89: Zone Preference Weight Tuning

### Purpose
- Zone Preference Weight 조정 로직 구현

### Done Criteria
- [ ] Zone Preference Weight 설계 완료

### Evidence
- docs/D89/D89_0_ZONE_PREFERENCE_DESIGN.md

---

## D90: Entry BPS Zone-Weighted Random & YAML Externalization

### Purpose
- Entry BPS Zone-Weighted Random 전략 구현

### Done Criteria
- [ ] Zone-Weighted Random 설계 완료

### Evidence
- docs/D90/D90_0_ENTRY_BPS_ZONE_RANDOM_DESIGN.md

---

## D91: Symbol-Specific Zone Profile

### Purpose
- Symbol별 Zone Profile TO-BE 설계

### Done Criteria
- [ ] Symbol-Specific Zone Profile 설계 완료

### Evidence
- docs/D91/D91_0_SYMBOL_ZONE_PROFILE_TOBE_DESIGN.md

---

## D92: POST-MOVE HARDEN (SSOT/Gate/증거 완결)

### Purpose
- C:\work 이관 후 환경 안정화

### Done Criteria (v3.2)
- [x] Fast Gate 4종 PASS
- [x] Core Regression 43/43 PASS
- [x] Gate 10m: 600초+Exit0+KPI JSON 생성

### Evidence
- docs/D92/D92_POST_MOVE_HARDEN_V3_2_REPORT.md

---

## SSOT 규칙

**ROADMAP SSOT 2종**:
1. /D_ROADMAP.md: 실행 상태 및 상세 변경 이력
2. /TOBE_ROADMAP.md: 큰 줄기 정의

**검증**: scripts/check_roadmap_sync.py
