# D84-0: Fill Model v1 – Design Document

**Date:** 2025-12-06  
**Status:** 📋 DESIGN  
**Author:** AI Assistant (Automated)

---

## 📋 Executive Summary

D82-12까지의 Threshold 튜닝 접근법이 실패한 근본 원인은 **고정값 Fill Ratio (26.15%)**에 있습니다. D84-0은 실제 PAPER 데이터를 기반으로 Fill Model v1을 보정하는 첫 Infrastructure 개선 단계입니다.

**목표:**
- 현재 고정값 26.15% → 실측 데이터 기반 Zone별 Fill Ratio로 보정
- D82-11/12 기존 실행 로그에서 Fill Event 데이터 수집
- 10분 스모크 테스트로 Fill Model v1 동작 검증

**비스코프:**
- L2 Orderbook 통합 (이건 D83-x)
- 장기 1시간+ PAPER (이건 D84-1)
- D77-4 완전 재현 (이건 D82-13)

---

## 🎯 요구사항

### R1: Fill Event 데이터 구조

기존 KPI JSON에서 Fill 관련 정보를 추출:

```python
@dataclass
class FillEvent:
    """Fill Event 데이터"""
    # 식별 정보
    timestamp: datetime
    session_id: str
    trade_id: str
    symbol: str
    
    # 거래 파라미터
    side: Literal["BUY", "SELL"]
    entry_bps: float
    tp_bps: float
    order_quantity: float
    
    # Fill 결과
    filled: bool  # 체결 성공 여부
    filled_quantity: float
    fill_ratio: float  # 0.0 ~ 1.0
    slippage_bps: float
    
    # 시장 조건
    available_volume: float  # 호가 잔량 (추정치)
    spread_bps: float  # 진입/퇴출 시 스프레드
    
    # 퇴출 이유
    exit_reason: Literal["take_profit", "stop_loss", "time_limit", "spread_reversal"]
    latency_ms: float | None  # 체결 소요 시간
```

### R2: Zone별 Fill Ratio 집계

Entry/TP Threshold 구간별로 Fill Ratio 통계 계산:

```python
zones = [
    {"entry_min": 5.0, "entry_max": 7.0, "tp_min": 7.0, "tp_max": 10.0},
    {"entry_min": 7.0, "entry_max": 10.0, "tp_min": 10.0, "tp_max": 12.0},
    {"entry_min": 10.0, "entry_max": 14.0, "tp_min": 12.0, "tp_max": 16.0},
    {"entry_min": 14.0, "entry_max": 16.0, "tp_min": 16.0, "tp_max": 18.0},
]

for zone in zones:
    zone_stats = {
        "buy_fill_ratio_avg": ...,
        "buy_fill_ratio_median": ...,
        "buy_fill_ratio_p25": ...,  # pessimistic
        "buy_fill_ratio_p75": ...,  # optimistic
        "sell_fill_ratio_avg": ...,
        "count": ...,  # sample size
    }
```

### R3: Fill Model v1 보정

기존 SimpleFillModel을 확장하여 Zone별 Fill Ratio 적용:

```python
class CalibratedFillModel(SimpleFillModel):
    """실측 데이터 기반 Fill Model v1"""
    
    def __init__(self, calibration_data: Dict[str, Any]):
        super().__init__()
        self.zones = calibration_data["zones"]
        self.default_buy_fill_ratio = calibration_data["default_buy_fill_ratio"]
    
    def execute(self, context: FillContext) -> FillResult:
        # 1. Entry/TP에 해당하는 Zone 찾기
        zone = self._find_zone(context.entry_bps, context.tp_bps)
        
        # 2. Zone별 Fill Ratio 적용
        if zone:
            custom_fill_ratio = zone["buy_fill_ratio_avg"]
        else:
            custom_fill_ratio = self.default_buy_fill_ratio
        
        # 3. Fill Model 실행
        # ... (기존 로직 + custom_fill_ratio 적용)
```

### R4: 짧은 PAPER 스모크 테스트

```bash
# D84-0 스모크 테스트 (10분)
python scripts/run_d84_0_fill_model_smoke.py \
    --duration 600 \
    --topn 10 \
    --calibration-data logs/d84/d84_0_calibration.json \
    --output logs/d84/d84_0_smoke_kpi.json
```

**Acceptance Criteria:**
- Fill Ratio가 26.15% 고정값에서 벗어남
- Zone별로 다른 Fill Ratio 관측
- 기존 테스트 99/99 PASS 유지

---

## 🏗️ 아키텍처 변경 포인트

### 계층별 변경 사항

#### 1️⃣ Fill Model 계층 (`arbitrage/execution/fill_model.py`)

```python
# 새 클래스 추가
class CalibratedFillModel(SimpleFillModel):
    """D84-0: 실측 데이터 기반 Fill Model v1"""
    pass
```

**변경 원칙:**
- DO-NOT-TOUCH: SimpleFillModel, AdvancedFillModel 기존 로직
- 새 클래스만 추가 (상속 활용)
- 기존 테스트 깨지지 않도록 보장

#### 2️⃣ Fill Event Collector (`arbitrage/metrics/fill_stats.py` 새 파일)

```python
class FillEventCollector:
    """Fill Event 수집 및 저장"""
    
    def __init__(self, output_path: Path):
        self.events: List[FillEvent] = []
        self.output_path = output_path
    
    def record_fill_attempt(self, context: FillContext, result: FillResult):
        """Fill 시도 기록"""
        event = FillEvent(
            timestamp=datetime.utcnow(),
            side=context.side,
            order_quantity=context.order_quantity,
            filled_quantity=result.filled_quantity,
            fill_ratio=result.fill_ratio,
            ...
        )
        self.events.append(event)
    
    def save_to_jsonl(self):
        """JSONL로 저장"""
        with open(self.output_path, "w") as f:
            for event in self.events:
                f.write(json.dumps(asdict(event)) + "\n")
```

#### 3️⃣ Executor 확장 (최소 침습)

```python
# arbitrage/execution/executor.py

class PaperExecutor(BaseExecutor):
    def __init__(
        self,
        fill_model: BaseFillModel = None,
        fill_event_collector: FillEventCollector = None,  # 새 파라미터
    ):
        self.fill_model = fill_model or create_default_fill_model()
        self.fill_event_collector = fill_event_collector  # 선택적
    
    def _execute_single_trade(self, trade):
        buy_fill_result = self.fill_model.execute(buy_context)
        sell_fill_result = self.fill_model.execute(sell_context)
        
        # Fill Event 기록 (선택적)
        if self.fill_event_collector:
            self.fill_event_collector.record_fill_attempt(buy_context, buy_fill_result)
            self.fill_event_collector.record_fill_attempt(sell_context, sell_fill_result)
        
        return result
```

#### 4️⃣ Calibration 데이터 로더 (`arbitrage/analysis/fill_calibrator.py` 새 파일)

```python
class FillModelCalibrator:
    """Fill Model 보정 데이터 생성"""
    
    @staticmethod
    def load_fill_events(jsonl_path: Path) -> List[FillEvent]:
        """JSONL에서 Fill Event 로드"""
        pass
    
    @staticmethod
    def compute_zone_stats(events: List[FillEvent], zones: List[Dict]) -> Dict:
        """Zone별 Fill Ratio 통계 계산"""
        pass
    
    @staticmethod
    def create_calibration_data(events: List[FillEvent]) -> Dict:
        """Calibration 데이터 생성"""
        pass
```

---

## 🔬 구현 계획

### Phase 1: Fill Event 데이터 수집 (기존 로그 활용)

**목표:** D82-11/12 KPI JSON에서 Fill Event 추출

**작업:**
1. `scripts/extract_d82_fill_events.py` 작성
   - D82-11/12 KPI JSON 파일 파싱
   - Fill Event 형식으로 변환
   - `logs/d84/d84_0_fill_events_d82.jsonl` 저장

2. 수집할 데이터:
   - D82-11: 3 runs (Entry 14-16, TP 18)
   - D82-12: 3 runs (Entry 5-10, TP 7-12)
   - 총 6 runs, 약 18 round trips

**예상 결과:**
```jsonl
{"timestamp": "2025-12-06T00:40:25", "side": "BUY", "entry_bps": 10.0, "tp_bps": 12.0, "fill_ratio": 0.2615, ...}
{"timestamp": "2025-12-06T00:40:25", "side": "SELL", "entry_bps": 10.0, "tp_bps": 12.0, "fill_ratio": 1.0, ...}
...
```

### Phase 2: Fill Model v1 구현

**목표:** Zone별 Fill Ratio를 적용하는 CalibratedFillModel 구현

**작업:**
1. `arbitrage/execution/fill_model.py`에 `CalibratedFillModel` 추가
2. Zone matching 로직 구현
3. Fill Ratio override 로직 구현

**테스트:**
- `tests/test_d84_0_calibrated_fill_model.py` 작성
- Zone matching 정확도 검증
- 기존 SimpleFillModel 동작 유지 확인

### Phase 3: Calibration 데이터 생성

**목표:** Zone별 Fill Ratio 통계 계산

**작업:**
1. `scripts/generate_d84_0_calibration.py` 작성
   - Fill Events JSONL 로드
   - Zone별 집계
   - `logs/d84/d84_0_calibration.json` 저장

2. Calibration 데이터 구조:
```json
{
  "created_at": "2025-12-06T10:30:00",
  "source": "D82-11/12 실행 로그",
  "total_events": 36,
  "zones": [
    {
      "entry_min": 5.0, "entry_max": 7.0,
      "tp_min": 7.0, "tp_max": 12.0,
      "buy_fill_ratio_avg": 0.2615,
      "buy_fill_ratio_median": 0.2615,
      "count": 6
    },
    ...
  ],
  "default_buy_fill_ratio": 0.2615,
  "default_sell_fill_ratio": 1.0
}
```

### Phase 4: 10분 스모크 테스트

**목표:** Fill Model v1이 실제로 동작하는지 검증

**작업:**
1. `scripts/run_d84_0_fill_model_smoke.py` 작성
   - 기존 D77 PAPER 러너 재사용
   - Calibration 데이터 로드
   - CalibratedFillModel 주입
   - 10분 실행

2. 검증 항목:
   - Fill Ratio가 Zone별로 다른지
   - KPI가 D82-12와 다른 패턴인지
   - 기존 모니터링 정상 동작

**Acceptance Criteria:**
- ✅ Fill Ratio ≠ 0.2615 (Zone별 분산)
- ✅ RT ≥ 3 (최소한 D82-12와 동등)
- ✅ 에러/크래시 없음
- ✅ 기존 테스트 99/99 PASS

---

## 📊 예상 결과 시나리오

### Scenario A: Fill Ratio 개선 (Optimistic)

**조건:**
- Zone별 Fill Ratio 차이 존재 (예: Entry 5-7 → 35%, Entry 14-16 → 20%)
- 낮은 Entry Zone에서 Fill 기회 증가

**예상 결과:**
- RT: 3 → 5~7 (60%+ 증가)
- Fill Ratio (평균): 26% → 30~35%
- PnL: 개선 가능성

**판단:** ✅ CONDITIONAL GO → D84-1 (장기 검증)

### Scenario B: Zone 차이 없음 (Realistic)

**조건:**
- 모든 Zone에서 26% 유지 (시장 조건 일정)
- Fill Model 보정 효과 미미

**예상 결과:**
- RT: 3 (변화 없음)
- Fill Ratio: 26% (동일)
- PnL: 동일

**판단:** ⚠️ PENDING → D83-x (L2 Orderbook) 우선 진행

### Scenario C: 데이터 부족 (Pessimistic)

**조건:**
- D82-11/12 데이터 18 RTs로는 불충분
- Zone별 샘플 사이즈 < 3

**예상 결과:**
- 통계적 유의성 없음
- Calibration 데이터 신뢰도 낮음

**판단:** ⚠️ DATA COLLECTION → 추가 PAPER 실행 필요

---

## 🧪 테스트 계획

### 유닛 테스트

| 모듈 | 테스트 파일 | 테스트 항목 |
|------|-------------|-------------|
| **CalibratedFillModel** | `test_d84_0_calibrated_fill_model.py` | Zone matching, Fill Ratio override, fallback |
| **FillEventCollector** | `test_d84_0_fill_event_collector.py` | 이벤트 기록, JSONL 저장 |
| **FillModelCalibrator** | `test_d84_0_fill_calibrator.py` | 통계 집계, Calibration 생성 |

### 통합 테스트

| 시나리오 | 테스트 내용 | 기대 결과 |
|---------|-------------|-----------|
| **Mock PAPER 실행** | CalibratedFillModel + FillEventCollector | Fill Events 생성 확인 |
| **Zone별 Fill Ratio** | 서로 다른 Entry/TP로 여러 번 실행 | Zone별 다른 Fill Ratio |
| **기존 테스트 회귀** | D80-4, D81-1 테스트 재실행 | 99/99 PASS 유지 |

---

## 🚀 Acceptance Criteria

### D84-0 완료 조건

✅ **문서:**
- AS-IS 분석 완료 (`D84-0_FILL_MODEL_ASIS.md`)
- 설계 문서 완료 (`D84-0_FILL_MODEL_DESIGN.md`)
- 최종 보고서 (`D84-0_FILL_MODEL_REPORT.md`)

✅ **구현:**
- `CalibratedFillModel` 구현
- `FillEventCollector` 구현
- `FillModelCalibrator` 구현

✅ **데이터:**
- Fill Events JSONL 생성 (`logs/d84/d84_0_fill_events_d82.jsonl`)
- Calibration 데이터 생성 (`logs/d84/d84_0_calibration.json`)

✅ **검증:**
- 유닛 테스트 15+ tests 추가
- 10분 스모크 테스트 실행 완료
- 기존 테스트 99/99 PASS 유지

✅ **문서화:**
- D_ROADMAP.md에 D84-0 섹션 추가
- Git commit with meaningful message

---

## 📁 Deliverables

### 새 파일 (최소한으로)

```
arbitrage/
  execution/
    fill_model.py (CalibratedFillModel 추가)
  metrics/
    fill_stats.py (FillEventCollector 새 파일)
  analysis/
    fill_calibrator.py (FillModelCalibrator 새 파일)

scripts/
  extract_d82_fill_events.py (새 파일)
  generate_d84_0_calibration.py (새 파일)
  run_d84_0_fill_model_smoke.py (새 파일)

tests/
  test_d84_0_calibrated_fill_model.py (새 파일)
  test_d84_0_fill_event_collector.py (새 파일)
  test_d84_0_fill_calibrator.py (새 파일)

docs/D84/
  D84-0_FILL_MODEL_ASIS.md (완료)
  D84-0_FILL_MODEL_DESIGN.md (이 문서)
  D84-0_FILL_MODEL_REPORT.md (예정)

logs/d84/
  d84_0_fill_events_d82.jsonl (예정)
  d84_0_calibration.json (예정)
  d84_0_smoke_kpi.json (예정)
```

---

## 🎓 Lessons from D82 시리즈

### ✅ D82에서 배운 것

1. **Threshold 튜닝만으로는 안 됨**
   - Entry/TP를 D77-4 수준으로 낮춰도 성능 동일
   - 문제는 Fill Model에 있었음

2. **고정값 Fill Ratio의 위험성**
   - 26.15% 고정값 → 74% 기회 차단
   - 시장 조건 변화 미반영

3. **L2 Orderbook의 필요성**
   - L1만으로는 Fill 판단 불가
   - D83-x가 최종 목표

### 🔧 D84-0 설계 원칙

1. **DO-NOT-TOUCH 기존 코어**
   - SimpleFillModel, AdvancedFillModel 그대로
   - 상속으로 확장

2. **최소 침습 + 선택적 활성화**
   - FillEventCollector는 선택적
   - 기존 실행에 영향 없음

3. **단계적 검증**
   - 먼저 기존 데이터 활용
   - 10분 스모크만 실행
   - 장기 검증은 D84-1

---

**Generated by:** D84-0 Design Phase  
**Date:** 2025-12-06  
**Next Step:** Fill Event 데이터 수집 구현
