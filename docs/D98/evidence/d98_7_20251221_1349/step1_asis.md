# STEP 1: AS-IS 파악 (D98-7 Open Positions Real-Check)

## 목표
기존 Preflight/Positions 조회 흐름을 파악하고, D98-7에서 추가할 최소 변경 범위를 확정

---

## 1. 기존 Preflight 구조 (scripts/d98_live_preflight.py)

### 현재 체크 항목 (7개)
1. `check_environment()` - 환경변수 점검
2. `check_secrets()` - API 키 점검
3. `check_live_safety()` - LIVE 안전장치 점검
4. `check_database_connection()` - Redis/Postgres Real-Check (D98-5)
5. `check_exchange_health()` - 거래소 Health (D98-5)
6. **`check_open_positions()`** - **현재 mock 처리** ⚠️
7. `check_git_safety()` - Git 안전 점검

### check_open_positions() 현재 상태 (Line 382-405)
```python
def check_open_positions(self):
    """오픈 포지션 점검 (mock)"""
    print("[6/7] 오픈 포지션 점검...")
    
    # TODO: 실제 포지션 조회 로직 필요
    # - 거래소/포트폴리오에서 미청산 포지션 확인
    # - 정책 적용 (FAIL or Safe Mode)
    
    if self.dry_run:
        self.result.add_check(
            "Open Positions",
            "PASS",
            "포지션 점검 (dry-run, 실제 조회 안 함)",
            {"dry_run": True}
        )
    else:
        # 실제 실행 시에도 아직 구현 없음
        self.result.add_check(
            "Open Positions",
            "WARN",
            "포지션 점검 미구현 (mock)",
            {"dry_run": False}
        )
```

**문제:** 실제 조회 로직이 없고, mock PASS 처리만 됨

---

## 2. 기존 Positions 조회 모듈 (재사용 가능)

### A) CrossExchangePositionManager (arbitrage/cross_exchange/position_manager.py)
**메서드:** `list_open_positions() -> List[CrossExchangePosition]`
- Redis scan으로 모든 position 조회
- `state == PositionState.OPEN`인 것만 필터링
- 이미 구현 완료 ✅

**장점:**
- Redis 기반이라 빠름
- 이미 테스트 존재 (`test_d79_strategy.py::test_list_open_positions`)
- 실제 production 코드에서 사용 중

**단점:**
- Redis에 저장된 position만 조회 (거래소 실제 상태와 동기화 이슈 가능)

### B) Exchange Adapters (arbitrage/exchanges/*.py)
**메서드:** `get_open_positions() -> List[Position]`
- 구현체:
  - `UpbitSpotExchange`: 현물이라 빈 리스트 반환
  - `BinanceFuturesExchange`: 실제 API 호출 (선물)
  - `PaperExchange`: 메모리 `_positions` dict 반환

**장점:**
- 거래소 실제 상태 확인 가능 (BinanceFutures)

**단점:**
- Upbit Spot은 포지션 개념 없음 (현물)
- API 호출 레이트리밋 고려 필요

---

## 3. D98-7 설계 결정

### 3.1. Open Positions Provider 우선순위
```
[1순위] CrossExchangePositionManager.list_open_positions()
- Redis 기반, 빠름, 이미 검증됨
- Preflight는 빠른 실행이 중요 (30초 이내 목표)

[2순위] Exchange Adapters (보조 검증, 선택적)
- Binance Futures만 해당
- Upbit Spot은 skip (현물 포지션 없음)
```

### 3.2. 정책 (Policy A vs B)
**제안:** **Policy A - FAIL (Exit != 0)**
- 근거: Preflight의 목적은 "안전하지 않으면 실행 불가"
- Open Positions가 있다 = 이전 실행이 완전히 종료되지 않음 = 위험
- Safe Mode 전환보다는 명확한 FAIL이 운영상 안전

**Policy A 구현:**
```python
if len(open_positions) > 0:
    self.result.add_check(
        "Open Positions",
        "FAIL",
        f"미청산 포지션 감지: {len(open_positions)}개",
        {
            "count": len(open_positions),
            "positions": [p.to_dict() for p in open_positions[:5]]  # 최대 5개만
        }
    )
    # Telegram P0 알림 발송
    if self.alert_manager:
        self.alert_manager.send_alert(
            AlertRecord(
                severity=AlertSeverity.P0,
                source=AlertSource.PREFLIGHT,
                title="Preflight FAIL: Open Positions 감지",
                message=f"{len(open_positions)}개 미청산 포지션 존재"
            )
        )
```

### 3.3. Prometheus 메트릭 추가
```python
arbitrage_preflight_open_positions_count{env="paper|live"} = N
```

---

## 4. D98-7 변경 범위 (최소)

### Modified (1개)
**1. scripts/d98_live_preflight.py**
- `check_open_positions()` 메서드 실제 구현
- `CrossExchangePositionManager` import 및 초기화
- Redis 연결 재사용 (이미 `check_database_connection()`에서 연결됨)
- Policy A (FAIL) 적용
- Telegram P0 알림 발송 (이미 `self.alert_manager` 존재)
- Prometheus 메트릭 추가 (이미 `self.prometheus` 존재)

**예상 변경량:** ~40 lines (import 5 + 구현 30 + 메트릭 5)

### Added (1개)
**2. tests/test_d98_7_open_positions_check.py**
- Unit tests:
  - `test_check_open_positions_empty` (0개)
  - `test_check_open_positions_detected` (1개 이상)
  - `test_check_open_positions_fail_policy` (FAIL 확인)
  - `test_check_open_positions_alert` (Telegram P0 발송)
  - `test_check_open_positions_metric` (Prometheus 메트릭)
- Integration test:
  - `test_preflight_with_open_positions` (전체 Preflight 실행)

**예상 변경량:** ~150 lines

---

## 5. 기존 모듈 재사용 계획

| 모듈 | 용도 | 재사용 여부 |
|------|------|------------|
| `CrossExchangePositionManager` | Open Positions 조회 | ✅ 100% 재사용 |
| `AlertManager` | Telegram P0 알림 | ✅ 100% 재사용 (이미 초기화됨) |
| `PrometheusClientBackend` | 메트릭 저장 | ✅ 100% 재사용 (이미 초기화됨) |
| `PreflightResult` | 결과 저장 | ✅ 100% 재사용 |
| Redis 연결 | Position 조회용 | ✅ 재사용 (check_database_connection에서 이미 연결) |

**중복 구현 없음:** 모든 필요 모듈이 이미 존재하고 작동 중 ✅

---

## 6. D98-6 Preflight와의 연결

```
D98-6: Prometheus Metrics + Telegram Alerting 기반 구축
  ↓
D98-7: Open Positions Real-Check 추가
  ↓ (사용)
  - Prometheus: arbitrage_preflight_open_positions_count
  - Telegram: P0 알림 (FAIL 시)
  - Evidence: JSON에 positions 목록 포함
```

**의존성:** D98-6 완료됨 ✅ (Prometheus/Telegram 모두 작동 중)

---

## 7. Hang/Timeout 리스크

**Risk Level:** 🟢 LOW
- Redis scan은 빠름 (< 1초, position 수백 개 기준)
- 네트워크 타임아웃: Redis 5초 (이미 설정됨)
- 전체 Preflight 목표: 30초 이내 (현재 ~10초)

**Hang 방지:**
- Redis 연결 실패 시 즉시 FAIL 처리 (이미 구현됨)
- `list_open_positions()` 자체에 try-except (이미 구현됨)

---

## 8. 다음 단계 (STEP 2)

**구현 작업:**
1. `scripts/d98_live_preflight.py` 수정
   - Import: `CrossExchangePositionManager`
   - `check_open_positions()` 실제 구현
   - Policy A (FAIL) 적용
   - Telegram P0 알림
   - Prometheus 메트릭

2. `tests/test_d98_7_open_positions_check.py` 생성
   - Unit tests 5개
   - Integration test 1개

**예상 소요 시간:** 30분 (구현 15분 + 테스트 15분)
**Hang Risk:** 없음 (Redis 기반, 빠른 조회)

---

**STEP 1 완료 조건 충족:**
- ✅ 기존 모듈 재사용 계획 명확 (중복 구현 0개)
- ✅ 변경 범위 확정 (2개 파일, ~190 lines)
- ✅ Hang/Timeout 리스크 분석 완료 (LOW)
- ✅ D98-6 의존성 확인 완료
