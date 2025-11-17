# MODULE D15 – 머신러닝 기반 최적화 + 포트폴리오 관리 + 정량적 리스크 + 대시보드

## 개요

MODULE D15는 D14의 기반 위에서 **머신러닝 기반 변동성 예측**, **포트폴리오 최적화**, **정량적 리스크 관리**, **실시간 웹 대시보드**를 추가하는 최종 엔터프라이즈급 모듈입니다.

### 핵심 기능

1. **머신러닝 기반 변동성 모델** (`ml/volatility_model.py`)
   - LSTM 신경망 기반 변동성 예측
   - PyTorch 구현
   - 모델 저장/로드 지원

2. **포트폴리오 최적화** (`arbitrage/portfolio_optimizer.py`)
   - 상관관계 행렬 계산
   - 리스크 패리티 가중치
   - 평균-분산 최적화 (Markowitz)

3. **정량적 리스크 관리** (`arbitrage/risk_quant.py`)
   - Historical VaR (95%, 99%)
   - Expected Shortfall (CVaR)
   - 스트레스 테스트 (변동성, 스프레드, 장애)
   - 유동성 조정 리스크

4. **실시간 웹 대시보드** (`dashboard/server.py`)
   - FastAPI + WebSocket
   - 실시간 메트릭 스트리밍
   - Grafana 호환성

---

## 설정 가이드

### config/live.yml 확장

```yaml
# D15: 머신러닝 기반 변동성 모델
ml:
  enabled: true
  volatility_model:
    enabled: true
    model_path: "models/volatility_lstm.pt"
    sequence_length: 20
    device: "cpu"  # cpu 또는 cuda

# D15: 포트폴리오 최적화
portfolio:
  enabled: true
  window_size: 60
  optimization_method: "risk_parity"  # risk_parity 또는 mean_variance

# D15: 정량적 리스크 관리
risk_quant:
  enabled: true
  window_size: 100
  var_confidence_levels: [0.95, 0.99]

# D15: 대시보드
dashboard:
  enabled: true
  host: "0.0.0.0"
  port: 8001
  update_interval_ms: 1000
```

---

## 모듈 설명

### 1. ml/volatility_model.py

**LSTM 기반 변동성 예측**

```python
from ml.volatility_model import VolatilityPredictor

predictor = VolatilityPredictor(
    model_path="models/volatility_lstm.pt",
    sequence_length=20
)

# 변동성 기록
predictor.record_volatility(0.25)

# 다음 변동성 예측
predicted_vol = predictor.predict()  # 0.0~1.0

# 모델 저장
predictor.save_model()
```

**특징:**
- LSTM 신경망 (2 레이어, 64 숨겨진 상태)
- 입력: 최근 20개 변동성
- 출력: 다음 변동성 (0.0~1.0)
- PyTorch 없으면 현재 변동성 반환 (graceful fallback)

### 2. arbitrage/portfolio_optimizer.py

**포트폴리오 최적화**

```python
from arbitrage.portfolio_optimizer import PortfolioOptimizer

optimizer = PortfolioOptimizer(window_size=60)

# 수익률 추가
optimizer.add_returns('BTC', 0.5)
optimizer.add_returns('ETH', 0.4)

# 상관관계 행렬
corr_matrix = optimizer.calculate_correlation_matrix()

# 리스크 패리티 가중치
rp_weights = optimizer.get_risk_parity_weights()
# {'BTC': 0.5, 'ETH': 0.5}

# 평균-분산 최적화
mv_weights = optimizer.get_mean_variance_weights()

# 최적 가중치
optimal = optimizer.get_optimal_weights(['BTC', 'ETH'], method='risk_parity')
```

**알고리즘:**
- **리스크 패리티**: 각 자산의 역변동성 기반 가중치
- **평균-분산**: 수익률과 상관관계 기반 최적화

### 3. arbitrage/risk_quant.py

**정량적 리스크 관리**

```python
from arbitrage.risk_quant import QuantitativeRiskManager

manager = QuantitativeRiskManager(window_size=100)

# 수익률 기록
manager.record_return(0.5)
manager.record_pnl(100000)
manager.record_volatility(0.25)

# VaR 계산
var_95 = manager.calculate_var(0.95)  # 95% VaR
var_99 = manager.calculate_var(0.99)  # 99% VaR

# Expected Shortfall
es = manager.calculate_expected_shortfall(0.95)

# 최대 낙폭
max_dd = manager.calculate_max_drawdown()

# 샤프 지수
sharpe = manager.calculate_sharpe_ratio()

# 스트레스 테스트
vol_loss = manager.stress_test_volatility_spike(1000000, multiplier=2.0)
spread_loss = manager.stress_test_spread_widening(1000000, multiplier=3.0)
outage_loss = manager.stress_test_exchange_outage(1000000, hours=1.0)

# 유동성 조정 리스크
penalty = manager.get_liquidity_adjusted_risk(500000, daily_volume=10000000)

# 전체 메트릭
metrics = manager.get_risk_metrics()
```

**메트릭:**
- **VaR 95%**: 95% 신뢰도에서 최대 손실
- **VaR 99%**: 99% 신뢰도에서 최대 손실
- **Expected Shortfall**: VaR 초과 손실의 평균
- **Max Drawdown**: 누적 수익에서 최대 낙폭
- **Sharpe Ratio**: 위험 조정 수익률

### 4. dashboard/server.py

**실시간 웹 대시보드**

```python
from dashboard.server import init_dashboard

# 대시보드 초기화
dashboard = init_dashboard(host="0.0.0.0", port=8001)

# 메트릭 업데이트
dashboard.update_metrics({
    'volatility_smoothed': 0.25,
    'exposure_drift_rate': 0.05,
    'trend_regime': 1,
    'live_event_count': 42,
    'risk_mode_current': 0,
    'failclosed_events': 2,
    'ws_freshness_seconds': 5,
    'var_95': -2.5,
    'var_99': -3.5,
    'expected_shortfall': -4.0
})

# 서버 시작
dashboard.start()
```

**엔드포인트:**
- `GET /health`: 헬스 체크
- `GET /metrics/live`: 현재 메트릭
- `GET /risk/summary`: 리스크 요약
- `GET /logs/events`: 이벤트 로그
- `WS /ws/metrics`: 실시간 메트릭 스트림

---

## 새로운 메트릭

### D15 추가 메트릭 (9개)

| 메트릭 | 설명 | 범위 |
|--------|------|------|
| `volatility_predicted` | ML 예측 변동성 | 0.0~1.0 |
| `portfolio_weights` | 최적 포트폴리오 가중치 | 0.0~1.0 |
| `correlation_matrix` | 자산 간 상관관계 | -1.0~1.0 |
| `var_95` | 95% VaR | -∞~0 |
| `var_99` | 99% VaR | -∞~0 |
| `expected_shortfall` | Expected Shortfall | -∞~0 |
| `max_drawdown` | 최대 낙폭 | -∞~0 |
| `sharpe_ratio` | 샤프 지수 | -∞~∞ |
| `liquidity_penalty` | 유동성 조정 페널티 | 0.0~100.0 |

---

## 실행 방법

### 머신러닝 모델 학습

```bash
python scripts/train_volatility_model.py \
  --data-path data/ohlcv.csv \
  --epochs 50 \
  --batch-size 32 \
  --output models/volatility_lstm.pt
```

### 대시보드 실행

```bash
# 직접 실행
python -m dashboard.server

# Docker 실행
docker build -f Dockerfile.dashboard -t arbitrage-dashboard .
docker run -p 8001:8001 arbitrage-dashboard
```

### 통합 실행

```bash
python scripts/run_live.py --mode live --enable-ml --enable-dashboard
```

---

## 테스트 시나리오

### T1: 변동성 예측 테스트

```bash
python tests/test_d15_volatility.py
```

**기대:**
- ✅ 모델 초기화
- ✅ 변동성 기록 및 예측
- ✅ 데이터 부족 시 graceful fallback

### T2: 포트폴리오 최적화 테스트

```bash
python tests/test_d15_portfolio.py
```

**기대:**
- ✅ 상관관계 행렬 계산
- ✅ 리스크 패리티 가중치
- ✅ 평균-분산 최적화

### T3: 정량적 리스크 테스트

```bash
python tests/test_d15_risk_quant.py
```

**기대:**
- ✅ VaR 계산
- ✅ Expected Shortfall
- ✅ 스트레스 테스트
- ✅ 유동성 조정 리스크

---

## 대시보드 설정 (Grafana)

### Prometheus 메트릭 추가

```yaml
# prometheus.yml
scrape_configs:
  - job_name: 'arbitrage-lite'
    static_configs:
      - targets: ['localhost:8001']
```

### Grafana 대시보드 쿼리

```promql
# 예측 변동성
volatility_predicted

# 포트폴리오 가중치
portfolio_weights

# VaR
var_95
var_99

# Expected Shortfall
expected_shortfall

# 최대 낙폭
max_drawdown

# 샤프 지수
sharpe_ratio
```

---

## 의존성

### 필수
- Python 3.9+
- FastAPI (대시보드)
- Uvicorn (대시보드)

### 선택적
- PyTorch (머신러닝)
- NumPy (포트폴리오, 리스크)
- Pandas (데이터 처리)

### 설치

```bash
# 기본
pip install fastapi uvicorn

# ML 지원
pip install torch numpy

# 전체
pip install -r requirements.txt
```

---

## 다음 단계 (MODULE D16 예정)

1. **자동 모델 재학습**
   - 주기적 모델 업데이트
   - 온라인 학습

2. **고급 포트폴리오 관리**
   - 동적 리밸런싱
   - 제약 조건 최적화

3. **실시간 알림**
   - VaR 초과 알림
   - 포지션 한계 알림
   - 리스크 모드 변경 알림

4. **성능 분석**
   - 백테스팅
   - 성과 귀인 분석

---

## 요약

**MODULE D15는 D14 기반에서 머신러닝, 포트폴리오 최적화, 정량적 리스크 관리, 실시간 대시보드를 추가하여 완전한 엔터프라이즈급 자동 거래 시스템을 완성합니다.**

- ✅ 머신러닝 기반 변동성 예측 완성
- ✅ 포트폴리오 최적화 완성
- ✅ 정량적 리스크 관리 완성
- ✅ 실시간 웹 대시보드 완성
- ✅ 프로덕션 준비 완료
