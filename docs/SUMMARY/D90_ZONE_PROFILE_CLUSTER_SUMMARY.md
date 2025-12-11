# D90 Zone Profile Cluster 요약 (D90-0 ~ D90-5)

## 1. 목적

- **Entry BPS(진입 스프레드 bps) 영역을 Zone 개념(Z1~Z4)으로 나누고,  
  Zone 분포를 Profile로 관리하는 인프라를 구축**하는 것.
- 이 Profile을 기반으로:
  - **Strict 모드:** 비교적 보수적인 Zone 분포 (수익률 안정성, 리스크 관리)
  - **Advisory 모드:** Z2 중심의 공격적/효율적 진입 분포
- 최종 목표:  
  **코드 하드코딩이 아닌 YAML Config 기반 Zone Profile 체계**를 만들고,  
  실전 L2 + FillModel 환경에서 **1h/3h LONGRUN 검증**까지 끝낸 “프로덕션 기준선” 확보.

---

## 2. 단계별 요약

### D90-0: Zone Random Baseline
- 단순 `zone_random` 엔트리 로직 및 기본 Zone 개념 도입.
- 하드코딩된 분포 기반, 구조 검증용 스모크 수준.

### D90-2: Zone Profile Config
- 하드코딩된 여러 Zone Profile을 도입:
  - `strict_uniform`, `advisory_z2_focus` 등.
- 단일 심볼(BTC) 기준으로,  
  “어떤 Zone 분포가 PnL/FillModel 상 유리한지”를 파악하는 실험 단계.

### D90-3: Zone Profile Tuning
- Zone별 weight를 튜닝해서:
  - Strict/Advisory 각각의 “목표 Zone 분포”를 정교하게 맞춤.
- 20m PAPER를 통해,  
  “Z2 비중, PnL 안정성, Duration 정확도”를 Acceptance Criteria로 사용하는 구조 확립.

### D90-4: Zone Profile YAML Externalization
- 기존 하드코딩 Profile을 **YAML 파일(`zone_profiles.yaml`)**로 외부화.
- `zone_profiles_loader.py` 도입:
  - 스키마 검증,
  - dict-like 인터페이스,
  - backward compatibility.
- 20m Strict/Advisory A/B 비교 결과:
  - Advisory는 거의 동일,
  - Strict PnL -5.9% 차이 → **CONDITIONAL PASS**로 보류.

### D90-5: YAML Zone Profile LONGRUN Validation
- D90-4의 CONDITIONAL PASS를 해소하기 위한 결정적인 검증 단계.
- 실시간 Upbit L2 + CalibratedFillModel 환경에서:
  - **Strict 1h / Advisory 1h / Strict 3h LONGRUN 실행**
- 핵심 결과:
  - Strict 1h PnL: **$11.98**, Z2: **21.4%**
  - Advisory 1h PnL: **$15.71**, Z2: **50.7%**
  - Strict 3h PnL: **$37.35**, Z2: **24.6%**
  - 3h/1h PnL 비율 ≈ **3.12배** (선형 이상 스케일링)
- 결론:
  - 20m 수준의 -5.9% PnL 차이는 **시장 노이즈**로 판정.
  - YAML 기반 Profile이 구조/성능 면에서 하드코딩 버전과 동등 이상.
  - **D90-4 상태를 “GO(Production)”로 승격.**

---

## 3. 현재 기준선(AS-IS) 정의

- Zone Profile은 **YAML Config + `zone_profiles_loader.py` + `EntryBPSProfile`** 3개 축으로 관리.
- `EntryBPSProfile(mode=zone_random, zone_profile=…)`은:
  - `zone_profiles_loader`에서 Profile을 가져와,
  - 난수 시드 기반으로 Zone을 샘플링.
- D90-5 LONGRUN 검증 기준으로,
  - 이 구조는 **BTC 단일 심볼 기준 Production Grade**.
- 이 상태에서의 TO-BE:
  - D91 이후 단계에서 **Symbol/Market별 Zone Profile 매핑**,
  - 멀티 심볼 TopN 환경으로의 확장을 설계/구현.

---

## 4. 향후 확장 방향(TO-BE 스냅샷)

- D91-0: Symbol-Specific Zone Profile TO-BE Design (이번에 정의할 단계)
- D91-1+: 실제 Symbol/Market 매핑 구현 및 부분 튜닝.
- 이후:
  - TopN Arbitrage에서 심볼별/마켓별 Zone Profile 적용,
  - Zone Profile 튜닝을 Random/Bayesian/Grid 튜닝 파이프라인과 연결,
  - RiskGuard/FillModel/Alerting과 연동해 **엔드투엔드 상용 구조** 완성.
