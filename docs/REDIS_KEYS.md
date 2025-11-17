# Redis Key Naming Convention (PHASE D – MODULE D2)

## 개요

이 문서는 Arbitrage-Lite에서 사용하는 Redis 키 네이밍 컨벤션을 정의합니다.

**프리픽스**: `arb` (config.redis.prefix로 변경 가능)

---

## 키 구조

### 1. FX 환율 캐시

**패턴**: `{prefix}:fx:{symbol}`

**예시**:
```
arb:fx:usdkrw
arb:fx:eurkrw
```

**값**: 환율 (float, 문자열로 저장)

**TTL**: config.redis.health_ttl_seconds (기본값: 60초)

**사용처**:
- arbitrage/fx.py: get_usdkrw() 함수에서 Redis에 발행
- 향후 다른 모듈에서 읽기 가능

**예시 명령어**:
```bash
# Redis CLI에서 확인
docker-compose -f infra/docker-compose.yml exec redis redis-cli
> KEYS "arb:fx:*"
> GET "arb:fx:usdkrw"
```

---

### 2. 헬스 체크 Heartbeat

**패턴**: `{prefix}:heartbeat:{component}`

**예시**:
```
arb:heartbeat:paper_runner
arb:heartbeat:collector
arb:heartbeat:health_monitor
```

**값**: ISO 형식 타임스탬프 (문자열)

**TTL**: config.redis.health_ttl_seconds (기본값: 60초)

**사용처**:
- arbitrage/health.py: 헬스 체크 시 heartbeat 저장/조회
- 모니터링 시스템에서 컴포넌트 상태 확인

**예시 명령어**:
```bash
# Heartbeat 확인
docker-compose -f infra/docker-compose.yml exec redis redis-cli
> GET "arb:heartbeat:paper_runner"
> TTL "arb:heartbeat:paper_runner"
```

---

### 3. 스프레드 스냅샷 (선택적)

**패턴**: `{prefix}:spread:{symbol}`

**예시**:
```
arb:spread:BTC
arb:spread:ETH
```

**값**: JSON 형식 스냅샷 (dict)

**TTL**: 60초 (기본값)

**사용처**:
- arbitrage/redis_client.py: set_spread_snapshot() / get_spread_snapshot()
- 향후 실시간 모니터링 대시보드에서 사용

**예시 JSON**:
```json
{
  "symbol": "BTC",
  "upbit_price": 50000000,
  "binance_price": 45000,
  "spread_pct": 2.5,
  "is_opportunity": true,
  "timestamp": 1700000000000
}
```

---

## 키 생성 헬퍼

### arbitrage/redis_client.py

```python
def _make_key(self, *parts: str) -> str:
    """키 생성 (프리픽스 포함)
    
    예:
        _make_key("fx", "usdkrw") → "arb:fx:usdkrw"
        _make_key("heartbeat", "paper_runner") → "arb:heartbeat:paper_runner"
    """
    return f"{self.prefix}:{':'.join(parts)}"
```

---

## 키 관리 정책

### TTL (Time To Live)

- **FX 환율**: config.redis.health_ttl_seconds (기본값: 60초)
- **Heartbeat**: config.redis.health_ttl_seconds (기본값: 60초)
- **스프레드 스냅샷**: 60초 (고정)

TTL 만료 후 키는 자동으로 삭제됩니다.

### 키 네이밍 규칙

1. **소문자만 사용**: `arb:fx:usdkrw` (O), `arb:fx:USDKRW` (X)
2. **콜론으로 구분**: `arb:fx:usdkrw` (O), `arb_fx_usdkrw` (X)
3. **프리픽스 필수**: 모든 키는 `{prefix}:` 로 시작
4. **심볼은 대문자**: `arb:spread:BTC` (O), `arb:spread:btc` (X)

---

## 모니터링 명령어

### Redis CLI 접속

```bash
docker-compose -f infra/docker-compose.yml exec redis redis-cli
```

### 모든 키 확인

```bash
> KEYS "arb:*"
```

### 특정 카테고리 확인

```bash
# FX 환율
> KEYS "arb:fx:*"

# Heartbeat
> KEYS "arb:heartbeat:*"

# 스프레드
> KEYS "arb:spread:*"
```

### 키 상세 정보

```bash
# 값 확인
> GET "arb:fx:usdkrw"

# TTL 확인 (초)
> TTL "arb:fx:usdkrw"

# 타입 확인
> TYPE "arb:fx:usdkrw"

# 모든 정보
> INFO "arb:fx:usdkrw"
```

### 키 삭제

```bash
# 특정 키 삭제
> DEL "arb:fx:usdkrw"

# 패턴 기반 삭제
> DEL $(KEYS "arb:fx:*")
```

---

## 향후 확장 (MODULE D3+)

### 메트릭 집계

**패턴**: `{prefix}:metrics:{date}:{metric}`

**예시**:
```
arb:metrics:2025-11-15:daily_pnl
arb:metrics:2025-11-15:trade_count
arb:metrics:2025-11-15:win_rate
```

### 포지션 추적

**패턴**: `{prefix}:position:{position_id}`

**예시**:
```
arb:position:pos_001
arb:position:pos_002
```

### 주문 추적

**패턴**: `{prefix}:order:{order_id}`

**예시**:
```
arb:order:order_001
arb:order:order_002
```

---

## 참고

- **arbitrage/redis_client.py**: Redis 클라이언트 구현
- **arbitrage/health.py**: 헬스 체크 모듈
- **arbitrage/fx.py**: FX 환율 모듈
- **config/base.yml**: Redis 설정
