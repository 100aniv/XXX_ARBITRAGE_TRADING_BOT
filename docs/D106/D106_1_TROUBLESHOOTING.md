# D106-1: Live Preflight 트러블슈팅 가이드

**버전:** D106-1  
**일시:** 2025-12-27  
**목적:** Preflight 실패 시 원인별 해결 방법 (사람이 바로 고칠 수 있게)

---

## API 에러 6대 분류

### 1. INVALID_KEY (API 키/시크릿 오류)

**원인:**
- API 키/시크릿이 잘못됨
- API 키 권한 부족
- API 키 만료

**Upbit 해결:**
```
[해결] Upbit Open API 관리 > API 키 재확인
  - 자산조회: ON
  - 주문조회: ON
  - 주문하기: ON
  - 출금하기: OFF (필수)
  - IP 화이트리스트: 현재 IP 추가
```

**Binance 해결:**
```
[해결] Binance API Management > 키 재확인
  - Enable Reading: ON
  - Enable Futures: ON
  - Enable Withdrawals: OFF (필수)
  - IP Restrict: 현재 IP 추가
```

**확인 명령어:**
```powershell
# 현재 IP 확인
curl ifconfig.me

# .env.live에서 키 확인 (마스킹)
python -c "import os; from dotenv import load_dotenv; load_dotenv('.env.live'); print('Upbit:', os.getenv('UPBIT_ACCESS_KEY', '')[:8] + '...')"
```

---

### 2. IP_RESTRICTION (IP 화이트리스트 불일치)

**원인:**
- VPN 사용 중
- IP 화이트리스트에 현재 IP 미등록
- 공용 IP 변경됨

**Upbit 해결:**
```
[해결] Upbit Open API > IP 화이트리스트 확인
  - VPN 사용 중이면 해제
  - 공용 IP 확인: curl ifconfig.me
  - Upbit에 해당 IP 등록
```

**Binance 해결:**
```
[해결] Binance API Management > IP Restrictions 확인
  - Unrestrict access to trusted IPs only 활성화 시 IP 추가
  - VPN 사용 중이면 해제
```

**확인 명령어:**
```powershell
# 현재 공용 IP 확인
curl ifconfig.me

# VPN 확인
Get-NetAdapter | Where-Object {$_.InterfaceDescription -like "*VPN*"}
```

---

### 3. CLOCK_SKEW (시간 동기화 오류)

**원인:**
- 시스템 시간과 API 서버 시간 차이가 5초 이상
- NTP 동기화 실패

**Upbit 해결:**
```
[해결] 시스템 시간 동기화
  - Windows: w32tm /resync
  - 서버 시간과 5초 이상 차이 시 API 호출 실패
```

**Binance 해결:**
```
[해결] Binance recvWindow 오류
  - 시스템 시간 동기화: w32tm /resync
  - Binance 서버 시간: GET /fapi/v1/time 확인
```

**확인 명령어:**
```powershell
# Windows 시간 동기화
w32tm /resync

# 시간 확인
Get-Date

# Binance 서버 시간 확인
curl https://fapi.binance.com/fapi/v1/time
```

---

### 4. RATE_LIMIT (429 Too Many Requests)

**원인:**
- API 호출 빈도 초과
- Binance Weight Limit 초과

**Upbit 해결:**
```
[해결] Upbit Rate Limit 초과
  - 1초에 최대 10회 요청
  - 재시도 대기: 1초 후
```

**Binance 해결:**
```
[해결] Binance Rate Limit 초과 (429)
  - Weight limit 초과 시 1분 대기
  - Order rate limit 초과 시 재시도 간격 증가
```

**확인 명령어:**
```powershell
# Preflight 재실행 (1분 대기 후)
Start-Sleep -Seconds 60
python scripts/d106_0_live_preflight.py
```

---

### 5. PERMISSION_DENIED (권한 부족)

**원인:**
- Binance Futures 계좌 미활성화
- API 키 권한 부족

**Upbit 해결:**
```
[해결] Upbit API 권한 부족
  - Open API 관리 > 권한 재설정
  - 최소 권한: 자산조회, 주문조회, 주문하기
```

**Binance 해결:**
```
[해결] Binance Futures 미활성화
  - Wallet > Futures > Open Now
  - Futures 계좌 활성화 후 API 재발급
```

**확인 명령어:**
```powershell
# Binance apiRestrictions 직접 확인
curl -H "X-MBX-APIKEY: YOUR_API_KEY" "https://api.binance.com/sapi/v1/account/apiRestrictions?timestamp=..."
```

---

### 6. NETWORK_ERROR (네트워크/SSL 오류)

**원인:**
- 인터넷 연결 끊김
- 방화벽/보안 소프트웨어 차단
- DNS 오류

**Upbit 해결:**
```
[해결] 네트워크/SSL 오류
  - 인터넷 연결 확인
  - 방화벽/보안 소프트웨어 확인
  - DNS: 8.8.8.8 (Google) 사용
```

**Binance 해결:**
```
[해결] 네트워크/SSL 오류
  - 인터넷 연결 확인
  - VPN/Proxy 확인
  - Binance 서버 상태: status.binance.com
```

**확인 명령어:**
```powershell
# 인터넷 연결 확인
Test-NetConnection google.com -Port 443

# DNS 확인
nslookup api.upbit.com
nslookup fapi.binance.com

# Binance 서버 상태 확인
curl https://status.binance.com
```

---

## Binance apiRestrictions 검증 실패

### 문제: enableWithdrawals=true (출금 권한 ON)

**위험도:** 🔴 CRITICAL  
**원인:** API 키에 출금 권한이 활성화되어 있음  
**결과:** 봇 해킹 시 자산 출금 가능 (자산 손실 위험)

**해결 (필수):**
1. Binance > API Management
2. 해당 API 키 선택 > Edit Restrictions
3. **Enable Withdrawals: OFF** (체크 해제)
4. Save

**확인:**
```powershell
python scripts/d106_0_live_preflight.py
# 예상: ✅ enableWithdrawals=false (안전)
```

---

### 문제: enableFutures=false (Futures 권한 OFF)

**위험도:** 🟡 HIGH  
**원인:** Futures 트레이딩 권한이 비활성화됨  
**결과:** 봇이 Futures 시장에서 거래 불가

**해결:**
1. Binance > Wallet > Futures
2. **Open Now** (Futures 계좌 활성화)
3. API Management > Edit Restrictions
4. **Enable Futures: ON** (체크)
5. Save

**확인:**
```powershell
python scripts/d106_0_live_preflight.py
# 예상: ✅ enableFutures=true (Futures 트레이딩 가능)
```

---

### 문제: enableReading=false (읽기 권한 OFF)

**위험도:** 🟡 HIGH  
**원인:** 계좌 조회 권한이 비활성화됨  
**결과:** 봇이 잔고, 포지션 조회 불가

**해결:**
1. Binance > API Management
2. 해당 API 키 선택 > Edit Restrictions
3. **Enable Reading: ON** (체크)
4. Save

**확인:**
```powershell
python scripts/d106_0_live_preflight.py
# 예상: ✅ enableReading=true (계좌 조회 가능)
```

---

### 문제: ipRestrict=false (IP 제한 없음)

**위험도:** 🟠 MEDIUM  
**원인:** IP 화이트리스트가 비활성화됨  
**결과:** 모든 IP에서 API 키 사용 가능 (보안 취약)

**해결 (권장):**
1. Binance > API Management
2. 해당 API 키 선택 > Edit Restrictions
3. **Restrict access to trusted IPs only** (체크)
4. 현재 IP 추가: `curl ifconfig.me`
5. Save

**확인:**
```powershell
python scripts/d106_0_live_preflight.py
# 예상: ✅ ipRestrict=true (IP 화이트리스트 활성화)
```

---

## 전체 점검 플로우

### 1. Preflight 실행
```powershell
python scripts/d106_0_live_preflight.py
```

### 2. 실패 시 원인 확인
```
[Binance 연결 실패]
원인 유형: invalid_key

[해결] Binance API Management > 키 재확인
  - Enable Reading: ON
  - Enable Futures: ON
  - Enable Withdrawals: OFF (필수)
  - IP Restrict: 현재 IP 추가
```

### 3. 문제 해결 후 재실행
```powershell
# API 설정 변경 후 1분 대기 (전파 시간)
Start-Sleep -Seconds 60

# Preflight 재실행
python scripts/d106_0_live_preflight.py
```

### 4. 7/7 PASS 확인
```
======================================================================
[D106-1] Preflight Results Summary
======================================================================

Total Checks:  7
Passed:        7 [OK]
Failed:        0 [FAIL]
Warnings:      0 [WARN]

[READY] All checks passed. Ready for LIVE.
```

---

## 민감정보 확인 (안전하게)

### API 키 마스킹 확인
```powershell
# .env.live 파일에서 키 일부만 확인 (마스킹)
python -c "
import os
from dotenv import load_dotenv
load_dotenv('.env.live')

def mask(key):
    val = os.getenv(key, '')
    if len(val) > 16:
        return val[:8] + '...' + val[-8:]
    return '***'

print('UPBIT_ACCESS_KEY:', mask('UPBIT_ACCESS_KEY'))
print('BINANCE_API_KEY:', mask('BINANCE_API_KEY'))
"
```

### 로그에서 민감정보 누출 확인
```powershell
# Evidence 로그에서 평문 API 키 검색 (없어야 정상)
Select-String -Path "logs\evidence\d106_*\*.json" -Pattern "ZtDaFp|KFpspsy" -CaseSensitive
# 예상: 검색 결과 없음 (마스킹 정상)
```

---

## 추가 자원

**Upbit API 문서:**
- https://docs.upbit.com/reference

**Binance Futures API 문서:**
- https://binance-docs.github.io/apidocs/futures/en/

**Binance SAPI (apiRestrictions):**
- https://binance-docs.github.io/apidocs/spot/en/#get-api-key-permission-user_data

**Binance 서버 상태:**
- https://status.binance.com
