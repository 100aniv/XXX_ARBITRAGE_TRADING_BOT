# D20 LIVE ARM System Guide

**Document Version:** 1.0  
**Date:** 2025-11-16  
**Status:** ✅ Complete  

---

## 📋 목차

1. [개요](#개요)
2. [LIVE ARM 개념](#live-arm-개념)
3. [환경 변수](#환경-변수)
4. [ARM 조건](#arm-조건)
5. [운영 가이드](#운영-가이드)
6. [권장 설정](#권장-설정)
7. [문제 해결](#문제-해결)

---

## 개요

D20은 **LIVE ARM System**을 구현합니다. 실거래 모드(Live Mode)에 진입하기 위한 2단계 무장(arming) 시스템으로, 의도적인 "인증/결심" 없이 실거래가 켜지지 않도록 보장합니다.

### 핵심 원칙

- **기본값: Shadow Live Mode** — 실거래는 기본적으로 비활성화
- **2단계 무장 시스템** — ARM 파일 + ARM 토큰 모두 필요
- **명시적 활성화** — 두 조건을 모두 만족할 때만 Live Mode 활성화
- **강제 강등** — ARM 조건 미충족 시 무조건 Shadow Live Mode로 강등

---

## LIVE ARM 개념

### 무장(Arming) 시스템이란?

항공기나 미사일의 "무장" 개념에서 영감을 받았습니다:

- **Disarmed (비무장)**: 실거래 불가능 → Shadow Live Mode
- **Armed (무장)**: 실거래 가능 → Live Mode (다른 조건도 만족 시)

### 왜 필요한가?

D19에서 환경 변수(`LIVE_MODE=true`, `DRY_RUN=false` 등)만으로 Live Mode를 제어했을 때의 문제:

1. **실수로 켜질 수 있음** — 환경 변수 설정 실수로 의도하지 않은 실거래 시작
2. **자동화 배포 위험** — CI/CD 파이프라인에서 실수로 Live Mode 활성화
3. **명시적 의도 부족** — "정말 실거래를 하겠다"는 명확한 신호 없음

**D20 ARM 시스템**은 이를 해결합니다:

- ARM 파일을 **수동으로 생성**해야 함 (자동화 불가)
- ARM 토큰을 **명시적으로 설정**해야 함 (실수 방지)
- 두 조건을 **모두 만족**해야만 Live Mode 활성화

---

## 환경 변수

### D19 플래그 (기존)

| 환경 변수 | 기본값 | 설명 |
|----------|--------|------|
| `LIVE_MODE` | `false` | 실거래 모드 요청 |
| `SAFETY_MODE` | `true` | 안전 모드 활성화 |
| `DRY_RUN` | `true` | 드라이런 모드 |

### D20 ARM 변수 (신규)

| 환경 변수 | 기본값 | 설명 |
|----------|--------|------|
| `LIVE_ARM_FILE` | `configs/LIVE_ARMED` | ARM 파일 경로 |
| `LIVE_ARM_TOKEN` | (빈 문자열) | ARM 토큰 값 |

---

## ARM 조건

### Live Mode 활성화 조건

Live 모드에서 **실제 주문을 날리려면**, 아래 모든 조건을 동시에 만족해야 합니다:

#### 1단계: D19 플래그 조건 (기존)

```
✅ LIVE_MODE == "true"
✅ SAFETY_MODE == "true"
✅ DRY_RUN == "false"
✅ Upbit/Binance API 키 모두 유효
✅ RiskLimits 유효 (max_position_size > 0, max_daily_loss > 0)
```

#### 2단계: D20 ARM 조건 (신규)

```
✅ LIVE_ARM_FILE 경로에 파일이 실제로 존재
✅ LIVE_ARM_TOKEN == "I_UNDERSTAND_LIVE_RISK"
```

### 조건 검증 로직

```python
# D19: 기본 Live 조건
base_live_enabled = (
    LIVE_MODE == "true" and
    SAFETY_MODE == "true" and
    DRY_RUN == "false" and
    API_keys_valid and
    RiskLimits_valid
)

# D20: ARM 조건
live_armed = (
    os.path.isfile(LIVE_ARM_FILE) and
    LIVE_ARM_TOKEN == "I_UNDERSTAND_LIVE_RISK"
)

# 최종 결정
live_enabled = base_live_enabled and live_armed
```

### 조건 불만족 시 동작

어떤 조건 하나라도 빠져 있으면:

```
live_enabled = False
→ Shadow Live Mode로 강등
→ 주문 로그만 기록 ([SHADOW_LIVE] Would place order ...)
→ 실제 API 호출 없음
```

---

## 운영 가이드

### 1. Shadow Live Mode 운영 (기본값)

**목표**: 신호 생성 및 주문 로직 검증 (실거래 없음)

```bash
# 환경 변수 설정 (기본값 사용)
export LIVE_MODE=false
export SAFETY_MODE=true
export DRY_RUN=true

# 또는 설정하지 않음 (기본값 자동 적용)

# 실행
docker-compose up -d arbitrage-live-trader

# 로그 확인
docker-compose logs -f arbitrage-live-trader | grep SHADOW_LIVE
```

**예상 로그:**
```
[SHADOW_LIVE] Would place order: upbit buy 1.0 BTC @ 50000000
[SHADOW_LIVE] Would place order: binance sell 1.0 BTCUSDT @ 50100000
```

### 2. Live Mode 활성화 절차

#### STEP 1: 환경 변수 설정

```bash
# .env 파일에 설정
cat > .env << EOF
LIVE_MODE=true
SAFETY_MODE=true
DRY_RUN=false
UPBIT_API_KEY=your_upbit_key
UPBIT_SECRET_KEY=your_upbit_secret
BINANCE_API_KEY=your_binance_key
BINANCE_SECRET_KEY=your_binance_secret
EOF

# 환경 변수 로드
source .env
```

#### STEP 2: ARM 파일 생성

```bash
# ARM 파일 생성 (내용은 중요하지 않음)
mkdir -p configs
touch configs/LIVE_ARMED

# 또는 특정 메시지 포함
echo "Live trading armed at $(date)" > configs/LIVE_ARMED
```

#### STEP 3: ARM 토큰 설정

```bash
# 환경 변수에 ARM 토큰 설정
export LIVE_ARM_TOKEN="I_UNDERSTAND_LIVE_RISK"

# 또는 .env 파일에 추가
echo 'LIVE_ARM_TOKEN=I_UNDERSTAND_LIVE_RISK' >> .env
```

#### STEP 4: 상태 확인

```bash
# 환경 변수 확인
echo "LIVE_MODE=$LIVE_MODE"
echo "LIVE_ARM_FILE=${LIVE_ARM_FILE:-configs/LIVE_ARMED}"
echo "LIVE_ARM_TOKEN=$LIVE_ARM_TOKEN"

# ARM 파일 확인
ls -la configs/LIVE_ARMED
```

#### STEP 5: 실거래 시작

```bash
# 컨테이너 시작
docker-compose up -d arbitrage-live-trader

# 로그 확인
docker-compose logs -f arbitrage-live-trader

# 예상 로그:
# [LIVE_STATUS] requested_live_mode=true, safety_mode=true, dry_run=false, live_armed=true, live_enabled=true
# [LIVE_ARM] LIVE ARMED. Live trading is fully enabled.
# [LIVE] Order placed: order_id_12345
```

### 3. Live Mode 비활성화 절차

```bash
# 방법 1: ARM 파일 삭제
rm configs/LIVE_ARMED

# 방법 2: ARM 토큰 제거
unset LIVE_ARM_TOKEN

# 방법 3: 환경 변수 변경
export LIVE_MODE=false

# 컨테이너 재시작
docker-compose restart arbitrage-live-trader

# 로그 확인
docker-compose logs -f arbitrage-live-trader | grep SHADOW_LIVE
```

---

## 권장 설정

### Docker 배포 시 기본 설정

```yaml
# docker-compose.yml
arbitrage-live-trader:
  environment:
    # D19: 기본값 (Shadow Live Mode)
    LIVE_MODE: "false"
    SAFETY_MODE: "true"
    DRY_RUN: "true"
    
    # D20: ARM 기본값 (비무장)
    LIVE_ARM_FILE: "configs/LIVE_ARMED"
    LIVE_ARM_TOKEN: ""  # 빈 값 (비무장)
    
    # Redis
    REDIS_HOST: "redis"
    REDIS_PORT: "6379"
```

### 실거래 활성화 체크리스트

- [ ] `.env` 파일에 API 키 설정 확인
- [ ] `configs/LIVE_ARMED` 파일 생성 확인
- [ ] `LIVE_ARM_TOKEN=I_UNDERSTAND_LIVE_RISK` 환경 변수 설정 확인
- [ ] `LIVE_MODE=true` 설정 확인
- [ ] `DRY_RUN=false` 설정 확인
- [ ] RiskLimits 유효성 확인 (max_position_size > 0, max_daily_loss > 0)
- [ ] Shadow Live Mode에서 신호 생성 확인
- [ ] 로그에 `[LIVE_ARM] LIVE ARMED` 메시지 확인
- [ ] 소액으로 테스트 거래 실행

### 중요: Git 관리 규칙

```bash
# .gitignore에 추가 (ARM 파일은 절대 커밋하지 말 것)
echo "configs/LIVE_ARMED" >> .gitignore
echo ".env" >> .gitignore

# 이유:
# - ARM 파일은 운영상 수동 생성
# - 실수로 커밋되면 모든 배포에서 Live Mode 활성화
# - 보안 위험 (API 키 노출 가능)
```

---

## 문제 해결

### 문제 1: Live Mode가 활성화되지 않음

**증상:**
```
[LIVE_ARM] Live arm not satisfied. Falling back to SHADOW_LIVE mode.
[LIVE_ARM] ARM file not found: configs/LIVE_ARMED
```

**해결:**
```bash
# ARM 파일 생성 확인
ls -la configs/LIVE_ARMED

# 파일이 없으면 생성
mkdir -p configs
touch configs/LIVE_ARMED
```

### 문제 2: ARM 토큰 오류

**증상:**
```
[LIVE_ARM] Live arm not satisfied. Falling back to SHADOW_LIVE mode.
[LIVE_ARM] ARM token invalid or not set
```

**해결:**
```bash
# 토큰 확인 (정확히 일치해야 함)
echo $LIVE_ARM_TOKEN

# 정확한 토큰 설정
export LIVE_ARM_TOKEN="I_UNDERSTAND_LIVE_RISK"

# 대소문자 구분 확인
# ❌ i_understand_live_risk (소문자)
# ✅ I_UNDERSTAND_LIVE_RISK (대문자)
```

### 문제 3: 환경 변수 미설정

**증상:**
```
[LIVE_STATUS] requested_live_mode=false, safety_mode=true, dry_run=true, live_armed=false, live_enabled=false
```

**해결:**
```bash
# 환경 변수 확인
env | grep LIVE

# 환경 변수 설정
export LIVE_MODE=true
export SAFETY_MODE=true
export DRY_RUN=false
export LIVE_ARM_TOKEN="I_UNDERSTAND_LIVE_RISK"

# 또는 .env 파일에서 로드
source .env
```

### 문제 4: API 키 오류

**증상:**
```
[LIVE_STATUS] requested_live_mode=true, safety_mode=true, dry_run=false, live_armed=true, live_enabled=false
Live Mode disabled: Missing API keys → Shadow Live Mode
```

**해결:**
```bash
# API 키 확인
echo $UPBIT_API_KEY
echo $BINANCE_API_KEY

# 모든 API 키 설정 필요
export UPBIT_API_KEY="your_key"
export UPBIT_SECRET_KEY="your_secret"
export BINANCE_API_KEY="your_key"
export BINANCE_SECRET_KEY="your_secret"
```

---

## 로그 해석

### Shadow Live Mode 로그

```
[LIVE_STATUS] requested_live_mode=false, safety_mode=true, dry_run=true, live_armed=false, live_enabled=false
[LIVE_ARM] Live arm not satisfied. Falling back to SHADOW_LIVE mode.
[SHADOW_LIVE] Would place order: upbit buy 1.0 BTC @ 50000000
```

**의미:**
- Live Mode 요청 안 함 (또는 ARM 미충족)
- Shadow Live Mode로 동작
- 주문 로그만 기록, 실제 거래 없음

### Live Mode 로그

```
[LIVE_STATUS] requested_live_mode=true, safety_mode=true, dry_run=false, live_armed=true, live_enabled=true
[LIVE_ARM] LIVE ARMED. Live trading is fully enabled.
[LIVE] Order placed: order_id_12345
```

**의미:**
- Live Mode 활성화
- ARM 조건 만족
- 실제 주문 발행

---

## 관련 문서

- [D19 Live Mode Guide](D19_LIVE_MODE_GUIDE.md)
- [D20 Final Report](D20_FINAL_REPORT.md)

---

**문서 작성자:** Cascade AI  
**최종 수정:** 2025-11-16  
**상태:** ✅ Production Ready
