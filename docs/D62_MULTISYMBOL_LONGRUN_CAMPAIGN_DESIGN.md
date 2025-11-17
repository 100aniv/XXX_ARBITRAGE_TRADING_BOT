# D62 설계 문서: Multi-Symbol Long-run Campaign (Phase 4)

**작성일:** 2025-11-18  
**상태:** ✅ 설계 완료

---

## 📋 Executive Summary

D62는 **D51/D52 Long-run Test Plan을 멀티심볼 기준으로 확장**하여, **12시간 이상 Multi-Symbol Paper Long-run Campaign 파이프라인**을 구축합니다.

**핵심 목표:**
- ✅ 멀티심볼 엔진(D56~D61) 장시간 안정성 검증
- ✅ 최소 2개 이상 심볼 동시 Paper 실행
- ✅ 자동 환경 초기화 및 모니터링
- ✅ 실시간 이상 징후 감지 및 자동 중단/재실행
- ✅ 상용급 엔진 대비 안정성/성능 평가

---

## 🎯 아키텍처 개요

### 1. D51/D52 → D62 확장 구조

**D51 (단일심볼 롱런):**
```
Config (단일 심볼)
  ↓
ArbitrageLiveRunner (단일)
  ├─ market_data_provider (단일 스냅샷)
  ├─ executor (단일)
  ├─ risk_guard (전역 한도)
  └─ portfolio_state (전역 포지션)
    ↓
run_forever() 루프
  ├─ get_latest_snapshot()
  ├─ process_snapshot()
  ├─ execute_trades()
  └─ update_metrics()
    ↓
longrun_analyzer.py (단일심볼 분석)
```

**D62 (멀티심볼 롱런):**
```
Config (멀티심볼 리스트)
  ↓
ArbitrageLiveRunner (멀티심볼)
  ├─ market_data_provider (멀티심볼 스냅샷)
  ├─ executor_factory (심볼별 executor)
  ├─ executors: Dict[str, Executor]
  ├─ risk_guard (멀티심볼 한도)
  └─ portfolio_state (멀티심볼 포지션)
    ↓
arun_multisymbol_loop() 루프 (asyncio.gather)
  ├─ Symbol 1: arun_once_for_symbol()
  ├─ Symbol 2: arun_once_for_symbol()
  └─ ...
    ↓
longrun_analyzer.py (멀티심볼 분석)
```

### 2. ABSOLUTE RULES 적용

**환경 초기화 (자동):**
```python
def cleanup_environment():
    # 1. 기존 Python 프로세스 kill (Paper/Live 엔진)
    # 2. Redis FLUSHALL (쿨다운/포지션/가드 키)
    # 3. 로그 파일 백업 및 초기화
    # 4. 가상환경 활성화 확인
    # 5. 설정 파일 로드
```

**실시간 모니터링:**
```python
def monitor_longrun_logs():
    # 1. logs/application.log, logs/trading.log tail
    # 2. 이상 패턴 감시:
    #    - Entry 0 (5분 이상)
    #    - Guard BLOCK (3분 이상)
    #    - ERROR / Traceback
    # 3. 이상 시 즉시 중단 → 분석 → 재실행
```

---

## 📊 시나리오 정의

### S0: Mini Multi-Symbol Dry-run (3~5분)

**목적:** 멀티심볼 엔진 기본 동작 검증

**설정:**
```yaml
symbols: ["KRW-BTC", "KRW-ETH"]  # 2개 심볼
duration_minutes: 3
data_source: "rest"
mode: "paper"
```

**예상 결과:**
```
Duration: 3.0s
Loops: 3 (심볼당 3회)
Symbols: 2
Trades Opened: 2~4
Avg Loop Time: 1000±100ms
Errors: 0
```

### S1: 1시간 멀티심볼 롱런

**목적:** 개발·버그 재현용 (D51 S1 확장)

**설정:**
```yaml
symbols: ["KRW-BTC", "KRW-ETH"]
duration_minutes: 60
data_source: "rest"
mode: "paper"
```

### S2: 6시간 멀티심볼 롱런

**목적:** 장시간 안정성 검증 (D51 S2 확장)

**설정:**
```yaml
symbols: ["KRW-BTC", "KRW-ETH", "BTCUSDT"]  # 3개 심볼
duration_minutes: 360
data_source: "rest"
mode: "paper"
```

### S3: 12시간+ 멀티심볼 롱런

**목적:** 준-운영 검증 (D51 S3 확장)

**설정:**
```yaml
symbols: ["KRW-BTC", "KRW-ETH", "BTCUSDT", "ETHUSDT"]  # 4개 심볼
duration_minutes: 720
data_source: "rest"
mode: "paper"
```

---

## 📁 파일 구조

### 신규 파일

```
scripts/
├─ run_multisymbol_longrun.py (신규)
│  ├─ 환경 초기화 자동화
│  ├─ 멀티심볼 실행 관리
│  ├─ 실시간 모니터링
│  └─ longrun_analyzer 호출

configs/live/
├─ arbitrage_multisymbol_longrun.yaml (신규)
│  ├─ S0/S1/S2/S3 예시 설정
│  └─ 심볼별 리스크 한도 (D60)

tests/
├─ test_d62_multisymbol_longrun_runner.py (신규)
│  ├─ 10~15개 테스트
│  └─ 짧은 duration 기준

docs/
├─ D62_MULTISYMBOL_LONGRUN_CAMPAIGN_DESIGN.md (신규)
├─ D62_FINAL_REPORT.md (신규)
└─ D62_MULTISYMBOL_LONGRUN_EXECUTION_GUIDE.md (신규)
```

---

## 🔄 실행 흐름

### 1. 환경 초기화

```python
# 1. 기존 프로세스 kill
ps aux | grep python | grep -E "(paper|live|arbitrage)" | kill -9

# 2. Redis flush
redis-cli FLUSHALL

# 3. 로그 초기화
rm -f logs/*.log
mkdir -p logs

# 4. 가상환경 활성화
source venv/bin/activate  # Linux/Mac
.\venv\Scripts\activate   # Windows
```

### 2. 멀티심볼 롱런 실행

```python
python -m scripts.run_multisymbol_longrun \
  --config configs/live/arbitrage_multisymbol_longrun.yaml \
  --symbols KRW-BTC,KRW-ETH \
  --scenario S0 \
  --duration-minutes 3
```

### 3. 실시간 모니터링

```python
# 로그 tail + 패턴 감시
tail -f logs/application.log | grep -E "(ERROR|Guard|Entry)"

# longrun_analyzer 호출
python -m arbitrage.monitoring.longrun_analyzer \
  --log-file logs/application.log \
  --symbols KRW-BTC,KRW-ETH
```

### 4. 결과 분석 및 리포트

```python
# longrun_analyzer 결과 요약
# → D62_FINAL_REPORT.md 생성
```

---

## 🏢 상용급 엔진 비교

### 현재 (D62)

```
멀티심볼 롱런 캠페인
├── 심볼 수: 2~4개
├── 루프 시간: ~1000ms
├── 처리량: 2~4 심볼/루프
├── 메모리: ~100MB
├── 모니터링: 기본 (로그 기반)
└── 자동 복구: 기본 (재시작)
```

### 상용 (예: Binance, Kraken)

```
멀티심볼 롱런 캠페인
├── 심볼 수: 수십~수백개
├── 루프 시간: 10~50ms
├── 처리량: 수백~수천 심볼/루프
├── 메모리: 1~10GB
├── 모니터링: 고급 (메트릭 기반)
└── 자동 복구: 고급 (동적 조정)
```

---

## ✅ 체크리스트

### 구현

- ⏳ scripts/run_multisymbol_longrun.py 작성
- ⏳ configs/live/arbitrage_multisymbol_longrun.yaml 작성
- ⏳ 환경 초기화 함수 구현
- ⏳ 실시간 모니터링 함수 구현
- ⏳ longrun_analyzer 멀티심볼 확장

### 테스트

- ⏳ 10~15개 D62 테스트
- ⏳ S0 Mini Dry-run 실행
- ⏳ 회귀 테스트 (D51~D61)
- ⏳ 스모크 테스트

### 문서

- ⏳ D62_MULTISYMBOL_LONGRUN_CAMPAIGN_DESIGN.md
- ⏳ D62_FINAL_REPORT.md
- ⏳ D62_MULTISYMBOL_LONGRUN_EXECUTION_GUIDE.md

---

## 🎯 결론

D62는 **멀티심볼 롱런 캠페인 파이프라인**을 구축하여, D56~D61 멀티심볼 엔진의 **장시간 안정성을 검증**합니다.

**다음 단계:**
- D63: WebSocket 병렬화 및 지연 시간 개선
- D64: Live Execution 통합
- D70+: 성능 튜닝 및 확장성

---

**D62 설계 완료.** ✅

**작성자:** Cascade AI  
**작성일:** 2025-11-18  
**상태:** ✅ 완료
