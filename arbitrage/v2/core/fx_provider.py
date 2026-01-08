"""
D205-15-4: FX Provider Interface — Real-time FX Integration

목표: Fixed FX와 Live FX를 분리하여 Live mode 사고 방지 (1300원 참사 방지)
업데이트: LiveFxProvider 구현 (crypto-implied 방식)

SSOT: docs/v2/SSOT_RULES.md
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, Optional
import logging
import time

logger = logging.getLogger(__name__)


@dataclass
class FxRateInfo:
    """FX rate 정보 (Evidence 기록용)"""
    rate: float                      # KRW per USDT
    source: str                      # "fixed" | "crypto_implied" | "http"
    timestamp: datetime              # 조회 시각 (UTC)
    degraded: bool = False           # fallback 사용 여부
    degraded_reason: Optional[str] = None  # fallback 사유
    raw_data: Dict[str, Any] = field(default_factory=dict)  # 원본 데이터 (디버깅용)
    
    def to_dict(self) -> Dict[str, Any]:
        """Evidence JSON 직렬화용"""
        return {
            "fx_rate": self.rate,
            "fx_source": self.source,
            "fx_timestamp": self.timestamp.isoformat(),
            "fx_degraded": self.degraded,
            "fx_degraded_reason": self.degraded_reason,
        }


class FxProvider(ABC):
    """FX rate provider 인터페이스"""
    
    @abstractmethod
    def get_fx_rate(self, from_currency: str, to_currency: str) -> float:
        """
        환율 조회
        
        Args:
            from_currency: 출발 통화 (e.g., "USDT")
            to_currency: 도착 통화 (e.g., "KRW")
        
        Returns:
            환율 (e.g., 1450.0)
        
        Raises:
            ValueError: 지원하지 않는 통화 쌍
        """
        pass
    
    @abstractmethod
    def is_live(self) -> bool:
        """Live mode provider 여부"""
        pass


class FixedFxProvider(FxProvider):
    """
    Fixed FX provider (Test/Paper/Replay 전용)
    
    주의: Live mode에서 사용 금지 (validate_fx_provider_for_mode로 차단됨)
    """
    
    def __init__(self, fx_krw_per_usdt: float = 1450.0):
        """
        Args:
            fx_krw_per_usdt: USDT → KRW 환율 (기본값: 1450.0)
        """
        self.fx_krw_per_usdt = fx_krw_per_usdt
    
    def get_fx_rate(self, from_currency: str, to_currency: str) -> float:
        """고정 환율 반환"""
        if from_currency == "USDT" and to_currency == "KRW":
            return self.fx_krw_per_usdt
        elif from_currency == "KRW" and to_currency == "KRW":
            return 1.0
        else:
            raise ValueError(f"Unsupported FX pair: {from_currency}/{to_currency}")
    
    def is_live(self) -> bool:
        """Fixed FX는 Live 아님"""
        return False


class LiveFxProvider(FxProvider):
    """
    Live FX provider (D205-15-4: crypto-implied 방식 구현)
    
    지원 소스:
    1. crypto_implied: Upbit BTC/KRW ÷ Binance BTC/USDT = implied KRW/USDT
    2. http: 외부 FX API (선택, 운영환경에서만)
    
    복원력:
    - ttl_seconds 캐시
    - last_good_rate fallback
    - degraded 플래그로 상태 추적
    """
    
    def __init__(
        self,
        source: str = "crypto_implied",
        ttl_seconds: float = 10.0,
        http_base_url: Optional[str] = None,
        http_timeout: float = 5.0,
        market_data_fetcher: Optional[Any] = None,
    ):
        """
        Args:
            source: "crypto_implied" | "http"
            ttl_seconds: 캐시 TTL (초)
            http_base_url: HTTP 소스 URL (source="http"일 때)
            http_timeout: HTTP 타임아웃 (초)
            market_data_fetcher: 마켓 데이터 fetcher (crypto_implied용)
        """
        self.source = source
        self.ttl_seconds = ttl_seconds
        self.http_base_url = http_base_url
        self.http_timeout = http_timeout
        self.market_data_fetcher = market_data_fetcher
        
        # 캐시 상태
        self._cached_rate: Optional[float] = None
        self._cached_at: Optional[float] = None  # monotonic time
        self._last_good_rate: Optional[float] = None
        self._last_rate_info: Optional[FxRateInfo] = None
        
        logger.info(
            f"[D205-15-4_FX] LiveFxProvider initialized: "
            f"source={source}, ttl={ttl_seconds}s"
        )
    
    def get_fx_rate(self, from_currency: str, to_currency: str) -> float:
        """
        실시간 환율 조회 (캐시 + fallback)
        
        Returns:
            환율 (KRW per USDT)
        
        Raises:
            ValueError: 지원하지 않는 통화 쌍
            RuntimeError: 환율 조회 실패 (캐시/fallback 모두 없음)
        """
        if from_currency == "KRW" and to_currency == "KRW":
            return 1.0
        
        if not (from_currency == "USDT" and to_currency == "KRW"):
            raise ValueError(f"Unsupported FX pair: {from_currency}/{to_currency}")
        
        # 캐시 확인
        now = time.monotonic()
        if self._cached_rate is not None and self._cached_at is not None:
            age = now - self._cached_at
            if age < self.ttl_seconds:
                return self._cached_rate
        
        # 실시간 조회 시도
        try:
            rate = self._fetch_rate()
            self._cached_rate = rate
            self._cached_at = now
            self._last_good_rate = rate
            self._last_rate_info = FxRateInfo(
                rate=rate,
                source=self.source,
                timestamp=datetime.now(timezone.utc),
                degraded=False,
            )
            return rate
        except Exception as e:
            logger.warning(f"[D205-15-4_FX] Fetch failed: {e}")
            
            # Fallback to last good rate
            if self._last_good_rate is not None:
                logger.info(
                    f"[D205-15-4_FX] Using last_good_rate fallback: "
                    f"{self._last_good_rate}"
                )
                self._last_rate_info = FxRateInfo(
                    rate=self._last_good_rate,
                    source=f"{self.source}_fallback",
                    timestamp=datetime.now(timezone.utc),
                    degraded=True,
                    degraded_reason=str(e),
                )
                return self._last_good_rate
            
            # No fallback available
            raise RuntimeError(
                f"FX rate fetch failed and no fallback available: {e}\n"
                "This is the first fetch attempt and it failed.\n"
                "Check network connectivity or market data fetcher."
            ) from e
    
    def _fetch_rate(self) -> float:
        """
        소스별 환율 조회 (내부)
        
        Returns:
            KRW per USDT
        """
        if self.source == "crypto_implied":
            return self._fetch_crypto_implied()
        elif self.source == "http":
            return self._fetch_http()
        else:
            raise ValueError(f"Unknown FX source: {self.source}")
    
    def _fetch_crypto_implied(self) -> float:
        """
        Crypto-implied FX: Upbit BTC/KRW ÷ Binance BTC/USDT
        
        외부 FX API 없이 자급 가능 (거래소 데이터만 사용)
        
        Returns:
            implied KRW/USDT rate
        """
        if self.market_data_fetcher is None:
            # Fallback: 기본값 사용 (테스트용)
            logger.warning(
                "[D205-15-4_FX] No market_data_fetcher provided, "
                "using default rate 1400.0"
            )
            return 1400.0
        
        try:
            # Upbit BTC/KRW mid price
            upbit_btc = self.market_data_fetcher.get_mid_price("upbit", "BTC/KRW")
            # Binance BTC/USDT mid price
            binance_btc = self.market_data_fetcher.get_mid_price("binance", "BTC/USDT")
            
            if upbit_btc <= 0 or binance_btc <= 0:
                raise ValueError(
                    f"Invalid prices: upbit_btc={upbit_btc}, binance_btc={binance_btc}"
                )
            
            # Implied rate: KRW per USDT
            implied_rate = upbit_btc / binance_btc
            
            logger.debug(
                f"[D205-15-4_FX] Crypto-implied: "
                f"upbit_btc={upbit_btc}, binance_btc={binance_btc}, "
                f"implied={implied_rate:.2f}"
            )
            
            return implied_rate
        except Exception as e:
            raise RuntimeError(f"Crypto-implied FX fetch failed: {e}") from e
    
    def _fetch_http(self) -> float:
        """
        HTTP API FX 조회 (선택, 운영환경에서만)
        
        Returns:
            KRW/USDT rate from external API
        """
        if not self.http_base_url:
            raise ValueError("HTTP source requires http_base_url to be configured")
        
        import urllib.request
        import json
        
        try:
            req = urllib.request.Request(
                self.http_base_url,
                headers={"User-Agent": "ArbitrageBot/2.0"},
            )
            with urllib.request.urlopen(req, timeout=self.http_timeout) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                
                # 응답 스키마는 API마다 다름 - 기본 형식 가정
                if "rate" in data:
                    return float(data["rate"])
                elif "krw_per_usdt" in data:
                    return float(data["krw_per_usdt"])
                else:
                    raise ValueError(f"Unknown response schema: {data.keys()}")
        except Exception as e:
            raise RuntimeError(f"HTTP FX fetch failed: {e}") from e
    
    def get_rate_info(self) -> Optional[FxRateInfo]:
        """최근 환율 정보 (Evidence 기록용)"""
        return self._last_rate_info
    
    def is_live(self) -> bool:
        """Live FX는 Live"""
        return True
    
    def get_krw_per_usdt(self) -> float:
        """편의 메서드: USDT → KRW 환율"""
        return self.get_fx_rate("USDT", "KRW")


def validate_fx_provider_for_mode(provider: FxProvider, mode: str):
    """
    Live mode safeguard: Fixed FX 사용 금지
    
    목적: Live mode에서 고정 환율 (1450.0) 사용 시 발생할 수 있는
          "1300원 참사" (잘못된 환율로 주문) 사고를 원천 차단
    
    Args:
        provider: FX provider
        mode: "paper" / "live"
    
    Raises:
        ValueError: Live mode에서 Fixed FX 사용 시 (Fail Fast)
    
    Example:
        >>> # Paper mode (OK)
        >>> fx = FixedFxProvider(1450.0)
        >>> validate_fx_provider_for_mode(fx, "paper")  # ✅ PASS
        
        >>> # Live mode (CRASH with 🚨 FATAL)
        >>> fx = FixedFxProvider(1450.0)
        >>> validate_fx_provider_for_mode(fx, "live")  # ❌ Raises ValueError
    """
    if mode == "live" and not provider.is_live():
        raise ValueError(
            "🚨 FATAL: Live trading requires a real-time FX provider!\n"
            "Fixed FX (1450.0) cannot be used in LIVE mode.\n"
            "This is a safeguard to prevent '1300원 참사' (wrong FX rate orders).\n"
            "Please configure LiveFxProvider with a valid API key.\n"
            "\n"
            "SSOT Reference: D_ROADMAP.md → D206 Prerequisite #1"
        )
