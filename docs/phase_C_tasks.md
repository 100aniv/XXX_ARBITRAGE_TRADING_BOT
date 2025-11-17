# PHASE C – 작업 분해표 (Task Decomposition)

## 개요
PHASE C는 단일 심볼(BTC) 기반 시스템을 다중 심볼(BTC, ETH, ...) 지원으로 확장하고,
FX 정규화 및 리스크 티어링을 도입하는 단계입니다.

---

## C1: Multi-Symbol 구조 개편

### 목표
- 현재 BTC 전제 코드를 n개 심볼 병렬 처리 구조로 변경
- 심볼별 독립적인 포지션/신호 관리
- 심볼별 설정 오버라이드 지원

### 세부 작업
1. **config/base.yml 확장**
   - `symbols: [BTC, ETH]` 배열 지원
   - 심볼별 override 섹션 추가
   - 예: `symbols.BTC.sizing.max_notional_krw: 100000`

2. **collector.py 수정**
   - 심볼 루프 추가
   - 심볼별 Ticker 수집 병렬화

3. **engine.py 수정**
   - `compute_spread_opportunity()` → 심볼 파라미터 추가
   - 심볼별 스프레드 계산 분리

4. **executor.py 수정**
   - `self.positions` → 심볼별 dict 구조로 변경
   - 심볼별 포지션 추적

5. **risk.py 수정**
   - `can_open_new_position()` → 심볼 파라미터 추가
   - 심볼별 max_open_positions 체크

### 수정 포인트 (기존 코드 분석)
```
현재 구조 (BTC 전제):
  collector → Ticker(symbol='BTC') → engine.compute_spread_opportunity()
           → SpreadOpportunity(symbol='BTC') → risk.can_open_new_position()
           → executor.on_opportunity() → Position(symbol='BTC')

변경 후 구조 (n개 심볼):
  collector → for symbol in symbols:
              → Ticker(symbol) → engine.compute_spread_opportunity(symbol)
              → SpreadOpportunity(symbol) → risk.can_open_new_position(symbol)
              → executor.on_opportunity(symbol) → Position(symbol)
```

### 영향 범위
- config/base.yml
- scripts/run_paper.py (심볼 루프)
- arbitrage/engine.py
- arbitrage/risk.py
- arbitrage/executor.py

---

## C2: KRW ↔ USDT FX Normalization

### 목표
- 실시간 환율 업데이트 메커니즘 도입
- 바이낸스 USDT 가격 → KRW 변환 정규화
- 환율 소스 추상화 (고정값 → API)

### 세부 작업
1. **normalizer.py 강화**
   - `to_krw_price()` → FX 소스 파라미터 추가
   - 환율 캐싱 메커니즘
   - 환율 업데이트 주기 설정

2. **config/base.yml 확장**
   - `fx.source: "fixed" | "api" | "binance"` 선택
   - `fx.update_interval_seconds: 60`
   - `fx.fallback_usdkrw: 1350.0`

3. **engine.py 수정**
   - `compute_spread_opportunity()` → FX 파라미터 전달
   - 심볼별 환율 적용

4. **storage.py 수정**
   - 환율 변동 로깅 (선택사항, PHASE D로 미룰 수 있음)

### 수정 포인트
```
현재:
  normalizer.to_krw_price(binance_ticker, config)
  → binance_price * config['fx']['usdkrw']

변경 후:
  normalizer.to_krw_price(binance_ticker, config, fx_manager)
  → binance_price * fx_manager.get_rate('USDT/KRW')
```

### 영향 범위
- arbitrage/normalizer.py
- arbitrage/engine.py
- config/base.yml

---

## C3: Risk Tiering & Portfolio Constraints

### 목표
- 심볼별 리스크 한도 독립 관리
- 포트폴리오 레벨 제약 도입
- Tier 기반 포지션 크기 결정

### 세부 작업
1. **config/base.yml 확장**
   - 글로벌 `sizing.max_total_notional_krw` (포트폴리오 전체)
   - 심볼별 `sizing.max_notional_krw` (심볼별)
   - Tier 정의: `sizing.tiers: [{name: "tier1", max_notional: 50000}, ...]`

2. **risk.py 수정**
   - `can_open_new_position()` → 포트폴리오 레벨 체크 추가
   - `compute_position_size_krw()` → Tier 기반 계산
   - `get_symbol_risk_limit()` → 심볼별 한도 조회

3. **executor.py 수정**
   - `execute_entry()` → Tier 기반 포지션 크기 결정

### 수정 포인트
```
현재:
  risk.compute_position_size_krw(config, price)
  → max_notional / price

변경 후:
  risk.compute_position_size_krw(config, symbol, price, portfolio_state)
  → min(symbol_limit, portfolio_available, tier_limit) / price
```

### 영향 범위
- arbitrage/risk.py
- arbitrage/executor.py
- config/base.yml

---

## C4: Storage/Schema 확장

### 목표
- 심볼별 포지션 기록 구조 확장
- FX 변동 추적 (선택사항)
- 포트폴리오 스냅샷 로깅

### 세부 작업
1. **storage.py 수정**
   - positions.csv → symbol 컬럼 추가 (이미 있음, 확인)
   - trades.csv → symbol 컬럼 추가 (이미 있음, 확인)
   - fx_rates.csv 신규 생성 (선택사항)

2. **positions.csv 스키마**
   - 기존: timestamp_open, symbol, direction, size, ...
   - 변경 없음 (이미 symbol 포함)

3. **trades.csv 스키마**
   - 기존: timestamp, symbol, direction, size, ...
   - 변경 없음 (이미 symbol 포함)

### 수정 포인트
- 최소 수정 (이미 심볼 컬럼 존재)
- PHASE D에서 DB 마이그레이션 시 확장

### 영향 범위
- arbitrage/storage.py (최소 수정)

---

## C5: Config 확장 (symbols[], fx_source, size_tiers 등)

### 목표
- 다중 심볼 설정 지원
- FX 소스 선택 가능
- Tier 기반 리스크 설정

### 세부 작업
1. **config/base.yml 전체 구조**
   ```yaml
   symbols:
     - name: BTC
       sizing:
         max_notional_krw: 100000
       spread:
         min_net_spread_pct: 0.5
         exit_net_spread_pct: 0.1
     - name: ETH
       sizing:
         max_notional_krw: 50000
       spread:
         min_net_spread_pct: 0.5
   
   sizing:
     max_total_notional_krw: 500000
     tiers:
       - name: tier1
         max_notional_krw: 100000
       - name: tier2
         max_notional_krw: 50000
   
   fx:
     source: "fixed"  # or "api", "binance"
     update_interval_seconds: 60
     usdkrw: 1350.0
   ```

2. **config loader 수정**
   - 심볼별 override 병합 로직
   - Tier 설정 파싱

### 영향 범위
- config/base.yml
- arbitrage/config.py (또는 config 로더)

---

## C6: Test Coverage 계획

### 목표
- Multi-symbol 시나리오 테스트
- FX 업데이트 테스트
- Risk Tier 적용 테스트

### 세부 작업
1. **test/test_multi_symbol.py**
   - 2개 심볼 동시 진입/청산
   - 심볼별 포지션 독립성 확인

2. **test/test_fx_normalization.py**
   - 환율 변동 시 스프레드 재계산
   - 환율 캐싱 동작 확인

3. **test/test_risk_tiering.py**
   - Tier 기반 포지션 크기 결정
   - 포트폴리오 한도 체크

4. **test/test_config_override.py**
   - 심볼별 설정 오버라이드 확인
   - 글로벌 설정 병합 확인

### 산출물
- test/ 디렉토리 내 테스트 파일들
- 테스트 실행 로그

---

## 작업 순서 (권장)
1. **C5** → Config 확장 (다른 작업의 기반)
2. **C1** → Multi-Symbol 구조 개편
3. **C2** → FX Normalization
4. **C3** → Risk Tiering
5. **C4** → Storage 확장 (최소 수정)
6. **C6** → Test Coverage

---

## PHASE C 완료 기준
- [ ] 모든 C1~C5 작업 완료
- [ ] 2개 이상 심볼 동시 거래 가능
- [ ] 환율 정규화 정상 작동
- [ ] Risk Tier 적용 확인
- [ ] 테스트 커버리지 80% 이상
- [ ] CHANGELOG 업데이트
