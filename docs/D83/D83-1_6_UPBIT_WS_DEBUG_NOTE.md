# D83-1.6: Upbit WebSocket 디버그 노트

**작성일:** 2025-12-07  
**상태:** ✅ **RESOLVED**  
**작성자:** Windsurf AI

---

## 📋 개요

D83-1.5에서 Real L2 WebSocket Provider가 메시지를 수신하지 못하는 문제를 해결하기 위해 Upbit WebSocket API를 독립적으로 디버깅하고, 근본 원인을 식별하여 수정하였습니다.

---

## 🐛 문제 증상

### D83-1.5 Real L2 PAPER 테스트 (실패)
- **증상:** WebSocket 연결 및 구독 성공, 하지만 orderbook 메시지 수신 없음
- **로그:** `[WARNING] [D83-0_L2] No snapshot for BTC, using fallback` (지속)
- **결과:** available_volume std/mean = 0.0 (constant fallback volume)

### 추가 조사 결과
- D83-1.5에서 `receive_loop()` 통합 및 symbol mapping 수정 적용
- 그럼에도 메시지 수신 실패
- 근본 원인 불명확 → 독립 디버그 필요

---

## 🔍 디버그 프로세스

### STEP 1: 디버그 스크립트 작성
**파일:** `scripts/debug/d83_1_6_upbit_ws_debug.py`

**목적:**
- Upbit WebSocket을 Executor/Runner와 분리하여 독립 테스트
- Raw 메시지 수신, 파싱, 스냅샷 생성 각 단계 상세 로깅
- 문제 지점 정확히 식별

**주요 기능:**
- 30~60초 동안 KRW-BTC orderbook 구독
- 수신 메시지 통계 수집 (개수, 속도, 타입)
- 첫 5개 메시지 상세 로그, 이후 10개마다 요약
- 진단 결과 자동 분류 (A: 성공, B: 파싱 실패, C: 메시지 없음)

### STEP 2: DEBUG 로그 추가
**파일:** `arbitrage/exchanges/ws_client.py`
- 연결 성공 시 WebSocket 객체 타입 로깅
- 메시지 수신 시 raw 데이터 타입 및 길이 로깅
- JSON 파싱 후 메시지 키 목록 로깅

**파일:** `arbitrage/exchanges/upbit_ws_adapter.py`
- 구독 메시지 전송 전 payload 로깅
- on_message 호출 시 메시지 타입 로깅
- 스냅샷 파싱 성공 시 top bid/ask 로깅

### STEP 3: 1차 실행 - 문제 발견
**실행:** `python scripts/debug/d83_1_6_upbit_ws_debug.py --duration 30`

**관찰 결과:**
```
[2025-12-07 14:11:15] [DEBUG] [websockets.client] < BINARY 7b 22 65 72 72 6f 72 22 3a 7b 22 6d 65 73 73 61 67 ... [77 bytes]
[2025-12-07 14:11:15] [DEBUG] [ws_client] Received message: type=<class 'bytes'>, len=77
```

**발견 1: Binary 메시지**
- Upbit은 **bytes (binary)** 형태로 메시지 전송
- 기존 코드는 JSON 문자열만 처리
- bytes → str 디코딩 누락

**발견 2: 에러 메시지**
```json
{"error":{"message":"Format 이 맞지 않습니다.","name":"WRONG_FORMAT"}}
```
- Upbit 서버가 구독 메시지 포맷 오류 응답
- 현재 구독 메시지: `{"type":"orderbook","codes":["KRW-BTC"]}`
- Upbit API 요구 포맷: **배열 + ticket 필요**

**결과:** 메시지 수신 0개, 파싱 성공 0개 ❌

---

## 🔧 해결 방법

### FIX 1: bytes 디코딩 처리 (ws_client.py)

**문제:** Upbit WebSocket은 binary (bytes) 형태로 메시지 전송  
**해결:** UTF-8 디코딩 추가

**수정 위치:** `arbitrage/exchanges/ws_client.py`, `receive_loop()` 메서드

```python
# D83-1.6 FIX: bytes를 str로 변환 (Upbit은 binary로 메시지 전송)
if isinstance(raw_message, bytes):
    try:
        message_str = raw_message.decode('utf-8')
        logger.debug(f"[D49_WS_DEBUG] Decoded bytes to UTF-8: {message_str[:100]}...")
    except UnicodeDecodeError as e:
        logger.error(f"[D49_WS] Failed to decode bytes message: {e}")
        continue
else:
    message_str = raw_message
```

**효과:** Binary 메시지를 JSON으로 정상 파싱 가능

### FIX 2: Upbit 구독 포맷 수정 (upbit_ws_adapter.py)

**문제:** Upbit WebSocket API는 배열 형태 + ticket 필요  
**해결:** 구독 메시지를 Upbit 공식 포맷으로 변경

**수정 위치:** `arbitrage/exchanges/upbit_ws_adapter.py`, `subscribe()` 메서드

**변경 전 (D83-1.5):**
```json
{"type": "orderbook", "codes": ["KRW-BTC"]}
```

**변경 후 (D83-1.6):**
```json
[
  {"ticket": "UUID"},
  {"type": "orderbook", "codes": ["KRW-BTC"]}
]
```

**코드:**
```python
import uuid

# D83-1.6 FIX: Upbit API 정식 포맷 (배열 + ticket)
message = [
    {"ticket": str(uuid.uuid4())},
    {"type": "orderbook", "codes": channels}
]

# send_message는 dict만 받으므로, 직접 JSON 전송
import json
message_str = json.dumps(message)
await self.ws.send(message_str)
```

**효과:** Upbit 서버가 구독 요청을 정상 수락하고 orderbook 메시지 전송 시작

---

## ✅ 검증 결과

### STEP 4: 2차 실행 - 성공 확인
**실행:** `python scripts/debug/d83_1_6_upbit_ws_debug.py --duration 30`

**결과:**
```
[2025-12-07 14:13:26] [INFO] 수신 메시지 수: 219
[2025-12-07 14:13:26] [INFO] 파싱 성공 스냅샷: 219
[2025-12-07 14:13:26] [INFO] 파싱 실패: 0
[2025-12-07 14:13:26] [INFO] 평균 수신 속도: 7.35 msg/s
[2025-12-07 14:13:26] [INFO] 수신된 심볼: ['KRW-BTC']
[2025-12-07 14:13:26] [INFO] ✅ 성공! 219개 메시지 수신, 219개 스냅샷 파싱
```

**메시지 샘플:**
```json
{
  "type": "orderbook",
  "code": "KRW-BTC",
  "timestamp": 1765084406964,
  "total_ask_size": 7.06342145,
  "total_bid_size": 6.91234567,
  "orderbook_units": [
    {"ask_price": 133929000.00, "bid_price": 133920000.00, "ask_size": 0.3819, "bid_size": 0.0495},
    ...
  ],
  "stream_type": "SNAPSHOT",
  "level": 0
}
```

**Top bid/ask 샘플:**
- Top bid: 133,920,000 KRW x 0.0495 BTC
- Top ask: 133,929,000 KRW x 0.3819 BTC

**✅ 판정:** Upbit WebSocket 자체는 정상 작동 확인

### STEP 5: Real L2 PAPER 재실행
**실행:** `python scripts/run_d84_2_calibrated_fill_paper.py --smoke --l2-source real`

**결과:**
- Duration: 300.2초 ✅
- Fill Events: 60개 ✅
- BUY std/mean: 1.891 (189.1%) ✅
- SELL std/mean: 1.245 (124.5%) ✅
- WebSocket Reconnect: 0회 ✅
- Fatal Exceptions: 0개 ✅

**✅ ALL ACCEPTANCE CRITERIA PASS**

---

## 📊 Upbit WebSocket 메시지 특징 (실제 관찰)

### 메시지 포맷
- **전송 형태:** Binary (bytes), UTF-8 인코딩
- **구조:** JSON 객체 (배열 아님)
- **주요 필드:**
  - `type`: "orderbook"
  - `code`: "KRW-BTC" (Upbit 심볼 형식)
  - `timestamp`: Unix timestamp (ms)
  - `orderbook_units`: 배열 (최대 15개 호가)
  - `stream_type`: "SNAPSHOT" (초기) / "REALTIME" (이후)
  - `level`: 0 (전체 호가)

### 구독 메시지 포맷 (필수)
```json
[
  {"ticket": "고유 UUID 문자열"},
  {"type": "orderbook", "codes": ["KRW-BTC", "KRW-ETH", ...]},
  {"format": "DEFAULT"}  // 선택적, 기본값 사용 가능
]
```

**주의사항:**
1. 배열 형태 필수 (객체만 전송 시 WRONG_FORMAT 에러)
2. 첫 번째 요소는 ticket (세션 식별자)
3. codes는 배열 형태로 여러 심볼 동시 구독 가능

### 메시지 수신 속도
- 평균: ~7 msg/s (KRW-BTC 기준)
- 초기 SNAPSHOT 1회 + 이후 REALTIME 스트림
- 호가 변동 시 즉시 업데이트

---

## 🏁 결론

### 근본 원인
1. **Binary 메시지 처리 누락:** Upbit은 bytes로 메시지 전송, UTF-8 디코딩 필요
2. **구독 포맷 불일치:** Upbit API는 배열 + ticket 필수, 단순 객체로는 구독 거부

### 해결 방법
1. `ws_client.py`: bytes → str 디코딩 로직 추가
2. `upbit_ws_adapter.py`: 구독 메시지를 Upbit 공식 포맷으로 수정

### 검증 결과
- ✅ 독립 디버그 스크립트: 219개 메시지 수신 (30초)
- ✅ Real L2 PAPER 스모크: ALL ACCEPTANCE CRITERIA PASS

### 교훈
- **공식 문서 준수:** WebSocket API는 거래소마다 포맷이 다름, 공식 문서 확인 필수
- **Binary 처리:** 일부 거래소는 binary로 메시지 전송, 범용 처리 필요
- **독립 테스트:** 복잡한 시스템에서 문제 발생 시 최소 단위로 분리하여 디버깅

---

## 📝 관련 파일

### 수정된 코드
1. `arbitrage/exchanges/ws_client.py`
   - bytes 디코딩 로직 (Lines 196-217)
   - DEBUG 로깅 추가 (Lines 161, 203-206, 222, 274)

2. `arbitrage/exchanges/upbit_ws_adapter.py`
   - Upbit 구독 포맷 수정 (Lines 67-97)
   - DEBUG 로깅 추가 (Lines 79, 84, 98, 103, 107, 170-174)

### 새로 생성된 파일
1. `scripts/debug/d83_1_6_upbit_ws_debug.py` (~240 lines)
   - Upbit WebSocket 독립 디버그 스크립트
   - 통계 수집 및 진단 자동화

### 업데이트된 문서
1. `docs/D83/D83-1_5_REAL_L2_SMOKE_REPORT.md`
   - Real L2 섹션 업데이트 (D83-1.6 결과 반영)
2. `docs/D83/D83-1_REAL_L2_WEBSOCKET_REPORT.md`
   - Validation 상태 CONDITIONAL → PASS 업데이트

---

## 🚀 다음 단계

### D83-1.6 완료 후
- ✅ Upbit L2 WebSocket 정상 작동 확인
- ✅ Real L2 PAPER 스모크 테스트 PASS
- ✅ 문서 및 로드맵 정리 (D83-1.6_C)

### 향후 개선 사항
1. **다른 거래소 L2 Provider 구현:**
   - D83-2: Binance L2 WebSocket Provider
   - D83-3: Bybit L2 WebSocket Provider

2. **장기 PAPER 테스트:**
   - 20분 이상 long-run 테스트
   - 100+ fill events 수집
   - Mock vs Real L2 분포 비교

3. **WebSocket 안정성 강화:**
   - Reconnect 시 subscribe 자동 재실행
   - Heartbeat/ping-pong 로직 강화
   - Binary/JSON 자동 감지 처리

---

**디버그 완료:** 2025-12-07 14:13 KST  
**디버그 시간:** ~30분 (3회 실행)  
**최종 상태:** ✅ RESOLVED
