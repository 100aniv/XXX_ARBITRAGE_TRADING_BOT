"""
D106-2: Live Preflight Dry-run (M6 Live Ramp 준비) - 결정론화 + 401 분해

목표:
- .env.live 로딩 및 필수 키 검증
- 환경변수 충돌 감지 + 강제 override (D106-2 신규)
- 환경변수 placeholder(${...}) 검출 → FAIL
- 업비트/바이낸스 API 연결 dry-run (주문 없이 읽기만)
- Binance apiRestrictions 강제 검증 (출금 OFF, Futures ON)
- PostgreSQL/Redis 연결 확인
- 에러 원인 6대 분류 (Invalid key, IP 제한, Clock skew, Rate limit, Futures 권한, Network)
- 401 분해: HTTP status + exchange error code + 공인 IP 진단 (D106-2 신규)
- 결과를 evidence에 저장 (민감정보 마스킹)

ROADMAP:
- M6 (Live Ramp): D106 소액 LIVE 스모크 준비
- D99-20 완료 (Full Regression 0 FAIL) 기반으로 LIVE 진입

주의:
- 실제 주문 절대 금지 (READ_ONLY_ENFORCED=true 강제)
- Dry-run 목적: 연결 검증만 (잔고, 서버시간, 심볼 조회)
- API 키/시크릿은 로그에 절대 평문 저장 금지
"""

import json
import os
import sys
import re
import hmac
import hashlib
import time
import requests
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, List, Optional
from enum import Enum
from urllib.parse import urlencode

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Load .env.live file
from dotenv import load_dotenv
project_root = Path(__file__).parent.parent
env_file = project_root / ".env.live"

if not env_file.exists():
    print(f"[FAIL] .env.live not found at {env_file}")
    print("   Create .env.live from .env.live.example")
    sys.exit(1)

print(f"[Loading] {env_file.name}")

# D106-2: Env 충돌 감지 + 강제 override
from dotenv import dotenv_values

env_file_values = dotenv_values(env_file)
conflicts_detected = False
conflict_keys = []

for key, value in env_file_values.items():
    if key in os.environ and os.environ[key] != value:
        conflicts_detected = True
        conflict_keys.append(key)

# 강제 override (기본 True)
load_dotenv(env_file, override=True)

# D106-0: READ_ONLY_ENFORCED 강제 설정 (실주문 0건 보장)
os.environ["READ_ONLY_ENFORCED"] = "true"

# D106-2: Env 충돌 정보 저장 (나중에 evidence에 포함)
ENV_CONFLICTS = {
    "detected": conflicts_detected,
    "conflict_keys": conflict_keys
}

# Imports
from arbitrage.config.settings import get_settings
from arbitrage.config.readonly_guard import is_readonly_mode


class APIErrorType(Enum):
    """API 연결 실패 원인 분류 (6대 유형)"""
    INVALID_KEY = "invalid_key"  # API 키/시크릿 오류, 권한 부족
    IP_RESTRICTION = "ip_restriction"  # IP 화이트리스트 불일치
    CLOCK_SKEW = "clock_skew"  # Timestamp/nonce 오류 (시간 동기화)
    RATE_LIMIT = "rate_limit"  # 429 Too Many Requests
    PERMISSION_DENIED = "permission_denied"  # Futures 미활성화, 출금 권한 등
    NETWORK_ERROR = "network_error"  # SSL, DNS, Timeout
    UNKNOWN = "unknown"  # 기타


def mask_sensitive(text: str, key_length: int = 8) -> str:
    """민감정보 마스킹 (API 키, 시크릿)
    
    Args:
        text: 원본 텍스트
        key_length: 앞/뒤로 보여줄 길이
    
    Returns:
        마스킹된 텍스트 (예: AbCd...XyZ0)
    """
    if not text or len(text) <= key_length * 2:
        return "***MASKED***"
    
    return f"{text[:key_length]}...{text[-key_length:]}"


def classify_api_error(error: Exception, error_message: str, status_code: Optional[int] = None) -> APIErrorType:
    """API 에러를 6대 유형으로 분류 (D106-2: 401 분해 강화)
    
    Args:
        error: 예외 객체
        error_message: 에러 메시지 (소문자 변환)
        status_code: HTTP status code (선택)
    
    Returns:
        APIErrorType
    """
    msg_lower = error_message.lower()
    
    # (0) HTTP status 기반 우선 분류
    if status_code == 429:
        return APIErrorType.RATE_LIMIT
    
    # (a) Clock skew (Binance -1021)
    if "-1021" in error_message or any(keyword in msg_lower for keyword in [
        "timestamp", "recvwindow", "nonce", "clock", "time sync"
    ]):
        return APIErrorType.CLOCK_SKEW
    
    # (b) IP 제한 (키워드 우선)
    if any(keyword in msg_lower for keyword in [
        "ip", "whitelist", "restricted", "access denied from", "forbidden"
    ]):
        return APIErrorType.IP_RESTRICTION
    
    # (c) Invalid key/permission (401/403)
    if any(keyword in msg_lower for keyword in [
        "invalid api", "invalid key", "invalid signature", 
        "unauthorized", "authentication failed", "api key",
        "permission denied", "not authorized", "401", "403"
    ]):
        return APIErrorType.INVALID_KEY
    
    # (d) Futures/권한 부족
    if any(keyword in msg_lower for keyword in [
        "futures", "margin", "trading not enabled", "account not enabled"
    ]):
        return APIErrorType.PERMISSION_DENIED
    
    # (e) Rate limit (메시지 기반)
    if any(keyword in msg_lower for keyword in [
        "rate limit", "too many", "weight", "request limit"
    ]):
        return APIErrorType.RATE_LIMIT
    
    # (f) Network/SSL/DNS
    if any(keyword in msg_lower for keyword in [
        "ssl", "dns", "timeout", "connection", "network", "unreachable"
    ]):
        return APIErrorType.NETWORK_ERROR
    
    return APIErrorType.UNKNOWN


def get_public_ip() -> Optional[str]:
    """공인 IP 조회 (D106-2: WARN only, FAIL 아님)
    
    Returns:
        공인 IP 또는 None (실패 시)
    """
    try:
        response = requests.get("https://api.ipify.org", timeout=3)
        if response.status_code == 200:
            return response.text.strip()
    except Exception as e:
        pass
    return None


def get_error_hint(error_type: APIErrorType, exchange: str) -> str:
    """에러 유형별 해결 힌트 (사람이 바로 고칠 수 있게)
    
    Args:
        error_type: 에러 유형
        exchange: 거래소 (upbit, binance)
    
    Returns:
        해결 가이드 문자열
    """
    hints = {
        APIErrorType.INVALID_KEY: {
            "upbit": "[해결] Upbit Open API 관리 > API 키 재확인\n  - 자산조회: ON\n  - 주문조회: ON\n  - 주문하기: ON\n  - 출금하기: OFF (필수)\n  - IP 화이트리스트: 현재 IP 추가",
            "binance": "[해결] Binance API Management > 키 재확인\n  - Enable Reading: ON\n  - Enable Futures: ON\n  - Enable Withdrawals: OFF (필수)\n  - IP Restrict: 현재 IP 추가"
        },
        APIErrorType.IP_RESTRICTION: {
            "upbit": "[해결] Upbit Open API > IP 화이트리스트 확인\n  - VPN 사용 중이면 해제\n  - 공용 IP 확인: curl ifconfig.me\n  - Upbit에 해당 IP 등록",
            "binance": "[해결] Binance API Management > IP Restrictions 확인\n  - Unrestrict access to trusted IPs only 활성화 시 IP 추가\n  - VPN 사용 중이면 해제"
        },
        APIErrorType.CLOCK_SKEW: {
            "upbit": "[해결] 시스템 시간 동기화\n  - Windows: w32tm /resync\n  - 서버 시간과 5초 이상 차이 시 API 호출 실패",
            "binance": "[해결] Binance recvWindow 오류\n  - 시스템 시간 동기화: w32tm /resync\n  - Binance 서버 시간: GET /fapi/v1/time 확인"
        },
        APIErrorType.RATE_LIMIT: {
            "upbit": "[해결] Upbit Rate Limit 초과\n  - 1초에 최대 10회 요청\n  - 재시도 대기: 1초 후",
            "binance": "[해결] Binance Rate Limit 초과 (429)\n  - Weight limit 초과 시 1분 대기\n  - Order rate limit 초과 시 재시도 간격 증가"
        },
        APIErrorType.PERMISSION_DENIED: {
            "upbit": "[해결] Upbit API 권한 부족\n  - Open API 관리 > 권한 재설정\n  - 최소 권한: 자산조회, 주문조회, 주문하기",
            "binance": "[해결] Binance Futures 미활성화\n  - Wallet > Futures > Open Now\n  - Futures 계좌 활성화 후 API 재발급"
        },
        APIErrorType.NETWORK_ERROR: {
            "upbit": "[해결] 네트워크/SSL 오류\n  - 인터넷 연결 확인\n  - 방화벽/보안 소프트웨어 확인\n  - DNS: 8.8.8.8 (Google) 사용",
            "binance": "[해결] 네트워크/SSL 오류\n  - 인터넷 연결 확인\n  - VPN/Proxy 확인\n  - Binance 서버 상태: status.binance.com"
        },
        APIErrorType.UNKNOWN: {
            "upbit": "[해결] 원인 불명 오류\n  - 에러 메시지를 Upbit 고객센터에 문의\n  - API 키 재발급 시도",
            "binance": "[해결] 원인 불명 오류\n  - 에러 메시지를 Binance Support에 문의\n  - API 키 재발급 시도"
        }
    }
    
    return hints.get(error_type, {}).get(exchange, "[해결] 에러 로그 확인 필요")


class D106PreflightResult:
    """D106 Preflight 점검 결과"""
    
    def __init__(self):
        self.checks: List[Dict[str, Any]] = []
        self.passed = 0
        self.failed = 0
        self.warnings = 0
    
    def add_check(self, name: str, status: str, message: str, details: Dict[str, Any] = None):
        """점검 항목 추가"""
        self.checks.append({
            "name": name,
            "status": status,  # PASS, FAIL, WARN
            "message": message,
            "details": details or {},
            "timestamp": datetime.now(timezone.utc).isoformat()
        })
        
        if status == "PASS":
            self.passed += 1
        elif status == "FAIL":
            self.failed += 1
        elif status == "WARN":
            self.warnings += 1
    
    def is_ready(self) -> bool:
        """LIVE 실행 준비 완료 여부"""
        return self.failed == 0
    
    def to_dict(self) -> Dict[str, Any]:
        """결과를 dict로 변환"""
        return {
            "summary": {
                "total_checks": len(self.checks),
                "passed": self.passed,
                "failed": self.failed,
                "warnings": self.warnings,
                "ready_for_live": self.is_ready()
            },
            "checks": self.checks,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }


class D106LivePreflightChecker:
    """D106 LIVE 모드 사전 점검기 (Dry-run)"""
    
    def __init__(self):
        self.result = D106PreflightResult()
    
    def check_env_file_loaded(self) -> None:
        """1. .env.live 로딩 확인 (D106-2: 충돌 감지 포함)"""
        try:
            arbitrage_env = os.getenv("ARBITRAGE_ENV", "")
            
            if arbitrage_env != "live":
                self.result.add_check(
                    name="ENV_FILE_LOAD",
                    status="FAIL",
                    message=f"ARBITRAGE_ENV is '{arbitrage_env}', expected 'live'",
                    details={"arbitrage_env": arbitrage_env}
                )
            else:
                # D106-2: Env 충돌 정보 포함
                details = {
                    "arbitrage_env": arbitrage_env,
                    "env_loaded_from": ".env.live",
                    "conflicts_detected": ENV_CONFLICTS["detected"],
                    "conflict_keys": ENV_CONFLICTS["conflict_keys"]  # 값은 절대 출력 금지
                }
                
                if ENV_CONFLICTS["detected"]:
                    print(f"[D106-2] Env conflict detected: {ENV_CONFLICTS['conflict_keys']}")
                    print(f"[D106-2] Override applied (load_dotenv override=True)")
                
                self.result.add_check(
                    name="ENV_FILE_LOAD",
                    status="PASS",
                    message=".env.live loaded successfully (with override)",
                    details=details
                )
        except Exception as e:
            self.result.add_check(
                name="ENV_FILE_LOAD",
                status="FAIL",
                message=f"Error loading .env.live: {e}",
                details={"error": str(e)}
            )
    
    def check_required_keys(self) -> None:
        """2. 필수 환경변수 존재 확인 (placeholder 검출)"""
        required_keys = {
            "UPBIT_ACCESS_KEY": "Upbit Access Key",
            "UPBIT_SECRET_KEY": "Upbit Secret Key",
            "BINANCE_API_KEY": "Binance API Key",
            "BINANCE_API_SECRET": "Binance API Secret",
            "TELEGRAM_BOT_TOKEN": "Telegram Bot Token",
            "TELEGRAM_CHAT_ID": "Telegram Chat ID",
            "POSTGRES_DSN": "PostgreSQL DSN",
            "REDIS_URL": "Redis URL"
        }
        
        missing = []
        placeholders = []
        
        for key, description in required_keys.items():
            value = os.getenv(key, "")
            
            # 누락 체크
            if not value:
                missing.append(f"{key} ({description})")
                continue
            
            # Placeholder 체크 (${...} 패턴)
            if value.startswith("${") and value.endswith("}"):
                placeholders.append(f"{key} = {value}")
            
            # "your_" 접두사 체크 (example 파일 기본값)
            if value.startswith("your_"):
                placeholders.append(f"{key} = {value} (example default)")
        
        if missing:
            self.result.add_check(
                name="REQUIRED_KEYS",
                status="FAIL",
                message=f"Missing required keys: {', '.join(missing)}",
                details={"missing_keys": missing}
            )
        elif placeholders:
            self.result.add_check(
                name="REQUIRED_KEYS",
                status="FAIL",
                message=f"Placeholder values detected: {', '.join(placeholders)}",
                details={"placeholders": placeholders}
            )
        else:
            self.result.add_check(
                name="REQUIRED_KEYS",
                status="PASS",
                message="All required keys present (no placeholders)",
                details={"checked_keys": list(required_keys.keys())}
            )
    
    def check_readonly_mode(self) -> None:
        """3. READ_ONLY_ENFORCED 확인"""
        try:
            readonly = is_readonly_mode()
            
            if not readonly:
                self.result.add_check(
                    name="READONLY_MODE",
                    status="FAIL",
                    message="READ_ONLY_ENFORCED not activated (unsafe for preflight)",
                    details={"readonly": readonly}
                )
            else:
                self.result.add_check(
                    name="READONLY_MODE",
                    status="PASS",
                    message="READ_ONLY_ENFORCED active (orders blocked)",
                    details={"readonly": readonly}
                )
        except Exception as e:
            self.result.add_check(
                name="READONLY_MODE",
                status="FAIL",
                message=f"Error checking readonly mode: {e}",
                details={"error": str(e)}
            )
    
    def check_upbit_connection(self) -> None:
        """4. 업비트 API 연결 확인 (dry-run) - D106-1: 에러 분류 강화"""
        try:
            from arbitrage.exchanges.upbit_spot import UpbitSpotExchange
            
            # API 키 마스킹 (로그용)
            upbit_key = os.getenv("UPBIT_ACCESS_KEY", "")
            upbit_secret = os.getenv("UPBIT_SECRET_KEY", "")
            upbit_key_masked = mask_sensitive(upbit_key) if upbit_key else "NOT_SET"
            
            # Exchange 초기화 (환경변수에서 API 키 전달)
            upbit = UpbitSpotExchange(config={
                "api_key": upbit_key,
                "api_secret": upbit_secret,
                "live_enabled": False  # Preflight는 dry-run (주문 금지)
            })
            
            # Dry-run: 계좌 조회 (주문 아님)
            balance = upbit.get_balance()
            
            self.result.add_check(
                name="UPBIT_CONNECTION",
                status="PASS",
                message=f"Upbit connection OK (assets: {len(balance)} currencies)",
                details={
                    "asset_count": len(balance),
                    "method": "get_balances (read-only)",
                    "api_key_masked": upbit_key_masked
                }
            )
        except Exception as e:
            # D106-3: Upbit 에러 바디 파싱 강화 (error.name 추출)
            error_msg = str(e)
            status_code = None
            upbit_error_name = None
            upbit_error_message = None
            body_text = None
            
            # HTTP status code + body 추출 (NetworkError 래핑 대응)
            original_exc = e.__cause__ or e.__context__ or e
            
            if hasattr(original_exc, 'response') and hasattr(original_exc.response, 'status_code'):
                status_code = original_exc.response.status_code
                try:
                    body_text = original_exc.response.text[:2048]  # 2KB까지만
                    # Upbit JSON 파싱: {"error":{"name":"...","message":"..."}}
                    resp_json = json.loads(body_text)
                    if "error" in resp_json:
                        upbit_error_name = resp_json["error"].get("name")
                        upbit_error_message = resp_json["error"].get("message")
                except:
                    pass
            elif hasattr(e, 'response') and hasattr(e.response, 'status_code'):
                status_code = e.response.status_code
                try:
                    body_text = e.response.text[:2048]
                    resp_json = json.loads(body_text)
                    if "error" in resp_json:
                        upbit_error_name = resp_json["error"].get("name")
                        upbit_error_message = resp_json["error"].get("message")
                except:
                    pass
            elif "401" in error_msg:
                status_code = 401
            elif "403" in error_msg:
                status_code = 403
            
            # D106-3: Upbit 401 정확 분류
            if status_code == 401 and upbit_error_name:
                if upbit_error_name == "expired_access_key":
                    error_type_str = "expired_access_key"
                    error_hint = "[해결] Upbit API 키 만료\n  - Open API 관리에서 키 재발급\n  - 기존 키 삭제 후 신규 발급 권장"
                elif upbit_error_name == "jwt_verification":
                    error_type_str = "jwt_verification"
                    error_hint = "[해결] Upbit JWT 서명 검증 실패\n  - Secret Key 오류 (복사/붙여넣기 확인)\n  - API 키 재발급 시도"
                elif upbit_error_name == "invalid_query_payload":
                    error_type_str = "invalid_query_payload"
                    error_hint = "[해결] Upbit 요청 파라미터 오류\n  - 쿼리 스트링 포맷 확인\n  - nonce/timestamp 중복 확인"
                else:
                    error_type_str = "unauthorized_unknown"
                    error_hint = f"[해결] Upbit 인증 실패 ({upbit_error_name})\n  - API 키/시크릿/IP/권한 재확인\n  - Upbit 고객센터 문의"
            else:
                error_type = classify_api_error(e, error_msg, status_code)
                error_type_str = error_type.value
                error_hint = get_error_hint(error_type, "upbit")
            
            # D106-2: 공인 IP 정보 포함
            public_ip = get_public_ip()
            
            self.result.add_check(
                name="UPBIT_CONNECTION",
                status="FAIL",
                message=f"Upbit connection failed: {error_msg[:200]}",
                details={
                    "error": error_msg[:500],
                    "error_type": error_type_str,
                    "error_hint": error_hint,
                    "next_action": "위 [해결] 가이드를 따라 Upbit Open API 설정 확인",
                    "http_status_code": status_code,
                    "upbit_error_name": upbit_error_name,
                    "upbit_error_message": upbit_error_message,
                    "body_text": body_text[:500] if body_text else None,
                    "public_ip": public_ip,
                    "env_conflicts": ENV_CONFLICTS["detected"]
                }
            )
            print(f"\n[Upbit 연결 실패]")
            print(f"원인 유형: {error_type_str}")
            if status_code:
                print(f"HTTP Status: {status_code}")
            if upbit_error_name:
                print(f"Upbit Error Name: {upbit_error_name}")
            if public_ip:
                print(f"현재 공인 IP: {public_ip}")
            print(error_hint)
            print()
    
    def check_binance_connection(self) -> None:
        """5. 바이낸스 API 연결 확인 (dry-run) - D106-1: 에러 분류 + apiRestrictions 검증"""
        try:
            from arbitrage.exchanges.binance_futures import BinanceFuturesExchange
            
            # API 키 마스킹 (로그용)
            binance_key = os.getenv("BINANCE_API_KEY", "")
            binance_secret = os.getenv("BINANCE_API_SECRET", "")
            binance_key_masked = mask_sensitive(binance_key) if binance_key else "NOT_SET"
            
            # Exchange 초기화 (환경변수에서 API 키 전달)
            binance = BinanceFuturesExchange(config={
                "api_key": binance_key,
                "api_secret": binance_secret,
                "live_enabled": False  # Preflight는 dry-run (주문 금지)
            })
            
            # Dry-run: 계좌 조회 (주문 아님)
            balance = binance.get_balance()
            
            # D106-1: Binance apiRestrictions 강제 검증 (CRITICAL)
            restrictions = self._check_binance_api_restrictions()
            
            if restrictions["status"] == "FAIL":
                self.result.add_check(
                    name="BINANCE_CONNECTION",
                    status="FAIL",
                    message=f"Binance API restrictions check FAILED: {restrictions['message']}",
                    details={
                        "balance": str(balance),
                        "api_restrictions": restrictions,
                        "api_key_masked": binance_key_masked
                    }
                )
            else:
                self.result.add_check(
                    name="BINANCE_CONNECTION",
                    status="PASS",
                    message=f"Binance connection OK (balance: {balance}, API restrictions: PASS)",
                    details={
                        "balance": str(balance),
                        "method": "get_balance (read-only)",
                        "api_restrictions": restrictions,
                        "api_key_masked": binance_key_masked
                    }
                )
        except Exception as e:
            # D106-2: 에러 원인 분류 + 401 분해 강화
            error_msg = str(e)
            status_code = None
            exchange_error_code = None
            exchange_error_msg = None
            
            # HTTP status code 추출
            if hasattr(e, 'response') and hasattr(e.response, 'status_code'):
                status_code = e.response.status_code
            elif "401" in error_msg:
                status_code = 401
            elif "403" in error_msg:
                status_code = 403
            
            # Binance JSON 에러 코드 추출
            try:
                if hasattr(e, 'response') and hasattr(e.response, 'text'):
                    resp_json = json.loads(e.response.text)
                    exchange_error_code = resp_json.get("code")
                    exchange_error_msg = resp_json.get("msg")
            except:
                pass
            
            error_type = classify_api_error(e, error_msg, status_code)
            error_hint = get_error_hint(error_type, "binance")
            
            # D106-2: 공인 IP 정보 포함
            public_ip = get_public_ip()
            
            self.result.add_check(
                name="BINANCE_CONNECTION",
                status="FAIL",
                message=f"Binance connection failed: {error_msg[:200]}",
                details={
                    "error": error_msg[:500],
                    "error_type": error_type.value,
                    "error_hint": error_hint,
                    "next_action": "위 [해결] 가이드를 따라 Binance API Management 설정 확인",
                    "http_status_code": status_code,
                    "exchange_error_code": exchange_error_code,
                    "exchange_error_msg": exchange_error_msg,
                    "public_ip": public_ip,
                    "env_conflicts": ENV_CONFLICTS["detected"]
                }
            )
            print(f"\n[Binance 연결 실패]")
            print(f"원인 유형: {error_type.value}")
            if status_code:
                print(f"HTTP Status: {status_code}")
            if exchange_error_code:
                print(f"Exchange Error Code: {exchange_error_code}")
            if public_ip:
                print(f"현재 공인 IP: {public_ip}")
            print(error_hint)
            print()
    
    def _check_binance_api_restrictions(self) -> Dict[str, Any]:
        """Binance SAPI: apiRestrictions 검증 (출금 OFF, Futures ON 강제)
        
        Reference: GET /sapi/v1/account/apiRestrictions
        
        Returns:
            Dict with status, message, details
        """
        try:
            api_key = os.getenv("BINANCE_API_KEY", "")
            api_secret = os.getenv("BINANCE_API_SECRET", "")
            
            if not api_key or not api_secret:
                return {
                    "status": "FAIL",
                    "message": "Binance API key/secret not configured",
                    "details": {}
                }
            
            # Binance SAPI endpoint
            base_url = "https://api.binance.com"
            endpoint = "/sapi/v1/account/apiRestrictions"
            
            # Query parameters
            timestamp = int(time.time() * 1000)
            params = {
                "timestamp": timestamp,
                "recvWindow": 5000
            }
            
            # Signature
            query_string = urlencode(params)
            signature = hmac.new(
                api_secret.encode("utf-8"),
                query_string.encode("utf-8"),
                hashlib.sha256
            ).hexdigest()
            params["signature"] = signature
            
            # Request
            headers = {"X-MBX-APIKEY": api_key}
            response = requests.get(
                f"{base_url}{endpoint}",
                headers=headers,
                params=params,
                timeout=10
            )
            
            if response.status_code != 200:
                return {
                    "status": "FAIL",
                    "message": f"API restrictions check failed: HTTP {response.status_code}",
                    "details": {
                        "status_code": response.status_code,
                        "response": response.text[:200]
                    }
                }
            
            data = response.json()
            
            # 필수 검증 항목
            enable_withdrawals = data.get("enableWithdrawals", True)  # Default True (위험)
            enable_reading = data.get("enableReading", False)
            enable_futures = data.get("enableFutures", False)
            ip_restrict = data.get("ipRestrict", False)
            
            # 검증 로직
            checks = []
            
            # CRITICAL: 출금 권한 OFF 필수
            if enable_withdrawals:
                checks.append("❌ enableWithdrawals=true (DANGEROUS! 출금 권한 OFF 필수)")
            else:
                checks.append("✅ enableWithdrawals=false (안전)")
            
            # Reading 권한 ON 필수
            if not enable_reading:
                checks.append("❌ enableReading=false (계좌 조회 불가)")
            else:
                checks.append("✅ enableReading=true (계좌 조회 가능)")
            
            # Futures 권한 ON 필수 (우리 봇은 Futures 사용)
            if not enable_futures:
                checks.append("❌ enableFutures=false (Futures 트레이딩 불가)")
            else:
                checks.append("✅ enableFutures=true (Futures 트레이딩 가능)")
            
            # IP 제한 (권장)
            if ip_restrict:
                checks.append("✅ ipRestrict=true (IP 화이트리스트 활성화)")
            else:
                checks.append("⚠️ ipRestrict=false (IP 제한 없음 - 보안 취약)")
            
            # FAIL 조건: 출금 ON 또는 Reading/Futures OFF
            if enable_withdrawals or not enable_reading or not enable_futures:
                return {
                    "status": "FAIL",
                    "message": "Binance API 권한 설정 오류",
                    "details": {
                        "enableWithdrawals": enable_withdrawals,
                        "enableReading": enable_reading,
                        "enableFutures": enable_futures,
                        "ipRestrict": ip_restrict,
                        "checks": checks,
                        "action_required": [
                            "1. Binance > API Management > Edit Restrictions",
                            "2. Enable Withdrawals: OFF (필수)",
                            "3. Enable Reading: ON",
                            "4. Enable Futures: ON",
                            "5. IP Restrict: 현재 IP 추가 (권장)"
                        ]
                    }
                }
            
            return {
                "status": "PASS",
                "message": "Binance API 권한 설정 정상",
                "details": {
                    "enableWithdrawals": enable_withdrawals,
                    "enableReading": enable_reading,
                    "enableFutures": enable_futures,
                    "ipRestrict": ip_restrict,
                    "checks": checks
                }
            }
            
        except Exception as e:
            return {
                "status": "FAIL",
                "message": f"apiRestrictions 검증 실패: {str(e)[:200]}",
                "details": {
                    "error": str(e)[:500],
                    "note": "Binance SAPI 호출 오류 - API 키 권한 확인 필요"
                }
            }
    
    def check_postgres_connection(self) -> None:
        """6. PostgreSQL 연결 확인"""
        try:
            import psycopg2
            from urllib.parse import urlparse
            
            postgres_dsn = os.getenv("POSTGRES_DSN", "")
            
            if not postgres_dsn:
                self.result.add_check(
                    name="POSTGRES_CONNECTION",
                    status="FAIL",
                    message="POSTGRES_DSN not set",
                    details={}
                )
                return
            
            # Parse DSN
            parsed = urlparse(postgres_dsn)
            
            # Connect (timeout 5s)
            conn = psycopg2.connect(postgres_dsn, connect_timeout=5)
            cursor = conn.cursor()
            cursor.execute("SELECT version();")
            version = cursor.fetchone()[0]
            cursor.close()
            conn.close()
            
            self.result.add_check(
                name="POSTGRES_CONNECTION",
                status="PASS",
                message=f"PostgreSQL connection OK",
                details={
                    "host": parsed.hostname,
                    "port": parsed.port,
                    "database": parsed.path.lstrip("/"),
                    "version": version[:50]  # 처음 50자만
                }
            )
        except Exception as e:
            self.result.add_check(
                name="POSTGRES_CONNECTION",
                status="FAIL",
                message=f"PostgreSQL connection failed: {e}",
                details={"error": str(e)}
            )
    
    def check_redis_connection(self) -> None:
        """7. Redis 연결 확인"""
        try:
            import redis
            from urllib.parse import urlparse
            
            redis_url = os.getenv("REDIS_URL", "")
            
            if not redis_url:
                self.result.add_check(
                    name="REDIS_CONNECTION",
                    status="FAIL",
                    message="REDIS_URL not set",
                    details={}
                )
                return
            
            # Parse URL
            parsed = urlparse(redis_url)
            
            # Connect (timeout 5s)
            r = redis.from_url(redis_url, socket_connect_timeout=5, socket_timeout=5)
            r.ping()
            
            self.result.add_check(
                name="REDIS_CONNECTION",
                status="PASS",
                message=f"Redis connection OK",
                details={
                    "host": parsed.hostname,
                    "port": parsed.port,
                    "db": parsed.path.lstrip("/") or "0"
                }
            )
        except Exception as e:
            self.result.add_check(
                name="REDIS_CONNECTION",
                status="FAIL",
                message=f"Redis connection failed: {e}",
                details={"error": str(e)}
            )
    
    def run_all_checks(self) -> D106PreflightResult:
        """모든 점검 실행"""
        print("\n" + "="*70)
        print("[D106-0] Live Preflight Dry-run - M6 Live Ramp 준비")
        print("="*70)
        print()
        
        # 1. ENV 로딩
        print("[1/7] Checking .env.live load...")
        self.check_env_file_loaded()
        
        # 2. 필수 키
        print("[2/7] Checking required keys (placeholder detection)...")
        self.check_required_keys()
        
        # 3. READ_ONLY 모드
        print("[3/7] Checking READ_ONLY_ENFORCED...")
        self.check_readonly_mode()
        
        # 4. Upbit 연결
        print("[4/7] Checking Upbit API connection (dry-run)...")
        self.check_upbit_connection()
        
        # 5. Binance 연결
        print("[5/7] Checking Binance API connection (dry-run)...")
        self.check_binance_connection()
        
        # 6. PostgreSQL 연결
        print("[6/7] Checking PostgreSQL connection...")
        self.check_postgres_connection()
        
        # 7. Redis 연결
        print("[7/7] Checking Redis connection...")
        self.check_redis_connection()
        
        print()
        return self.result


def print_summary(result: D106PreflightResult) -> None:
    """결과 요약 출력"""
    print("="*70)
    print("[D106-0] Preflight Results Summary")
    print("="*70)
    print()
    
    summary = result.to_dict()["summary"]
    
    print(f"Total Checks:  {summary['total_checks']}")
    print(f"Passed:        {summary['passed']} [OK]")
    print(f"Failed:        {summary['failed']} [FAIL]")
    print(f"Warnings:      {summary['warnings']} [WARN]")
    print()
    
    if summary["ready_for_live"]:
        print("[READY] All checks passed. Ready for LIVE.")
    else:
        print("[NOT READY] Some checks failed. Fix issues before LIVE.")
    
    print()
    print("="*70)
    print()


def save_results(result: D106PreflightResult, output_path: Path) -> None:
    """결과를 JSON으로 저장"""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(result.to_dict(), f, indent=2, ensure_ascii=False)
    
    print(f"[Saved] Results saved to: {output_path}")


def main():
    """Main entry point"""
    
    # Evidence 디렉토리
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    evidence_dir = project_root / "logs" / "evidence" / f"d106_0_live_preflight_{timestamp}"
    evidence_dir.mkdir(parents=True, exist_ok=True)
    
    # Preflight 실행
    checker = D106LivePreflightChecker()
    result = checker.run_all_checks()
    
    # 결과 출력
    print_summary(result)
    
    # 결과 저장
    output_path = evidence_dir / "d106_0_preflight_result.json"
    save_results(result, output_path)
    
    # 상세 로그 저장
    detail_path = evidence_dir / "d106_0_preflight_detail.txt"
    with open(detail_path, "w", encoding="utf-8") as f:
        f.write("="*70 + "\n")
        f.write("[D106-0] Live Preflight Dry-run - Detailed Results\n")
        f.write("="*70 + "\n\n")
        
        for check in result.checks:
            f.write(f"[{check['status']}] {check['name']}\n")
            f.write(f"   Message: {check['message']}\n")
            if check['details']:
                f.write(f"   Details: {json.dumps(check['details'], indent=6, ensure_ascii=False)}\n")
            f.write(f"   Time: {check['timestamp']}\n")
            f.write("\n")
    
    print(f"[Saved] Details saved to: {detail_path}")
    print()
    
    # Exit code
    if result.is_ready():
        sys.exit(0)
    else:
        sys.exit(1)


if __name__ == "__main__":
    main()
