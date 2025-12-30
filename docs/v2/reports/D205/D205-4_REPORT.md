# D205-4: Reality Wiring — Real Market Data → Detector → Paper Intent + Latency/KPI Evidence

**작성일:** 2025-12-31 ## Status

**Current:** DONE ✅  
**Last Updated:** 2025-12-31  
**Commit:** f7f9fd2 (버그 수정 포함)리얼 마켓 데이터 → Opportunity Detection → Paper OrderIntent 플로우 완성 + DecisionTrace/Latency 증거

- **Market Data Provider:** `arbitrage/v2/marketdata/rest/upbit.py`, `arbitrage/v2/marketdata/rest/binance.py`
  - Ticker/Orderbook/Trades 조회 인터페이스 완성
  - Rate limit 준수 (Upbit 30req/s, Binance 20req/s)
  
- **Opportunity Detector:** `arbitrage/v2/opportunity/detector.py`
  - `detect_candidates()` 함수로 spread/edge/direction 계산
  - `detect_multi_candidates()` 함수로 여러 심볼 필터링
  
- **Break-even 모델:** `arbitrage/v2/domain/break_even.py`
  - `BreakEvenParams` + `compute_break_even_bps()` 재사용
  - FeeModel (V1) 재사용
  
- **Paper Runner 기반:** `arbitrage/v2/harness/paper_runner.py`
  - PaperRunner 클래스 구조 참조
  - KPI 수집 패턴 참조
  
- **Evidence 저장:** `scripts/run_d202_2_market_sampler.py`
  - Evidence 디렉토리 구조 (manifest.json, kpi.json, errors.ndjson)
  - KPI 저장 패턴 참조

### 🆕 신규 모듈 (D205-4 전용)
- **D205-4 Runner:** `scripts/run_d205_4_reality_wiring.py`
  - 리얼 마켓 데이터 수집 + Detector 연결
  - DecisionTrace 기록 (gate breakdown)
  - Latency 계측 (tick→decision, decision→intent, tick→intent)
  
- **DecisionTrace 수집:** `arbitrage/v2/core/decision_trace.py` (신규)
  - `gate_spread_insufficient_count`
  - `gate_liquidity_insufficient_count`
  - `gate_cooldown_count`
  - `gate_ratelimit_count`
  - `evaluated_ticks_total`
  - `opportunities_total`
  - `is_optimistic_warning` (winrate 100% 감지)

---

## 🎯 구현 범위

### 목표
1. **리얼 마켓 데이터 연결:** Upbit/Binance 공개 데이터 → V2 harness
2. **Opportunity Detection:** 실시간 평가 (spread → edge → profitable 필터)
3. **Paper OrderIntent:** 기회 → OrderIntent 생성 (실거래 없음)
4. **DecisionTrace:** "왜 0 trades인가?" 숫자로 설명
5. **Latency 계측:** tick→decision, decision→intent, tick→intent (ms)

### 안전장치
- ✅ LIVE 주문 호출 금지 (public data만)
- ✅ 실제 API 키 불필요 (mock/paper만)
- ✅ 0 trades도 PASS 가능 (gate breakdown으로 원인 설명)

---

## 📊 Evidence 요구사항

```
logs/evidence/d205_4_reality_wiring_<timestamp>/
├── manifest.json                    # 실행 메타 정보
├── kpi.json                         # KPI 요약
├── decision_trace.json              # Gate breakdown + opportunities
├── latency.json                     # p50/p95 latency
├── sample_ticks.ndjson              # 최근 100개 tick 샘플
├── errors.ndjson                    # 에러 로그
└── README.md                        # 재현 방법
```

### KPI 필드
- `opportunities_count`: 탐지된 기회 수
- `opportunities_profitable`: 수익 가능한 기회 수
- `latency_p50_ms`: 중앙값 레이턴시
- `latency_p95_ms`: 95 퍼센타일 레이턴시
- `edge_mean`: 평균 edge (bps)
- `edge_std`: edge 표준편차
- `is_optimistic_warning`: winrate 100% 경고 플래그

### DecisionTrace 필드
- `evaluated_ticks_total`: 평가한 tick 수
- `opportunities_total`: 스프레드 조건만 만족한 수
- `gate_spread_insufficient_count`: spread < break_even
- `gate_liquidity_insufficient_count`: 호가 잔량 부족
- `gate_cooldown_count`: 쿨다운 중
- `gate_ratelimit_count`: API 호출 제한

---

## ✅ AC (Acceptance Criteria)

- [ ] 플로우 완성: tick → detector → intent (연결됨)
- [ ] latency 기준 충족: p95 < 100ms
- [ ] 기회 발생률 > 0 (또는 gate breakdown으로 원인 설명)
- [ ] DecisionTrace 기록: evaluated_ticks_total > 0
- [ ] 가짜 낙관 방지: winrate 100% → 경고 + is_optimistic_warning=true
- [ ] Evidence 파일 생성: manifest.json, kpi.json, decision_trace.json, latency.json
- [ ] Gate Doctor/Fast/Regression: 0 FAIL

---

## 🔧 구현 계획

### Phase 1: Market Data Provider 연결
- UpbitRestProvider + BinanceRestProvider 사용
- 심볼 목록: BTC/KRW, ETH/KRW, XRP/KRW (기본)
- 폴링 간격: 5초 (D202-2 참조)

### Phase 2: Opportunity Detection 연결
- detect_candidates() 호출
- spread → break_even → edge → profitable 필터
- edge_after_cost 계산 (spread - break_even)

### Phase 3: DecisionTrace 수집
- gate_* 카운터 추적
- opportunities_total 계산
- winrate 100% 감지 로직

### Phase 4: Latency 계측
- tick_received_ts 기록
- decision_ts 기록
- intent_created_ts 기록
- p50/p95 계산

### Phase 5: Evidence 저장
- manifest.json (실행 메타)
- kpi.json (KPI 요약)
- decision_trace.json (gate breakdown)
- latency.json (p50/p95)
- sample_ticks.ndjson (최근 100개)

---

## 🚀 실행 명령어

### 2~5분 스모크 테스트
```bash
python scripts/run_d205_4_reality_wiring.py \
  --symbols BTC/KRW ETH/KRW XRP/KRW \
  --duration-sec 120 \
  --sample-interval-sec 5.0 \
  --env test
```

### 1시간 본 실행
```bash
python scripts/run_d205_4_reality_wiring.py \
  --symbols BTC/KRW ETH/KRW XRP/KRW \
  --duration-sec 3600 \
  --sample-interval-sec 5.0 \
  --env test
```

---

## 📝 다음 단계

- **D205-5:** Record/Replay SSOT (market.ndjson + decisions.ndjson)
- **D205-6:** ExecutionQuality v1 (slippage/partial_fill/edge_after_cost)
- **D205-7:** Parameter Sweep (리플레이 기반 튜닝)

---

## 참고 자료

- SSOT: `docs/v2/SSOT_RULES.md`, `docs/v2/design/SSOT_MAP.md`
- Evidence 포맷: `docs/v2/design/EVIDENCE_FORMAT.md`
- Architecture: `docs/v2/V2_ARCHITECTURE.md`
