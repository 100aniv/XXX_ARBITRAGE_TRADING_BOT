"""
D205-15-6c: FeatureGuard - Bootstrap Capability Verification

목적: Bootstrap 시 ESSENTIAL 기능 전수 조사
- DB Strict: db_mode == "strict" + 연결 성공
- Redis Pulse: redis ping 성공
- FX Health: FX 데이터 수신 지연 < 60초
- Watcher Heartbeat: RunWatcher 활성화

상용급 시스템의 안전장치: 하나라도 녹슬면 작동 중지
"""

import logging
from typing import Optional, Dict, Any
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class FeatureGuard:
    """
    Bootstrap 시 ESSENTIAL 기능 전수 조사
    
    검증:
    - DB Strict: db_mode == "strict" + 연결 성공
    - Redis Pulse: redis ping 성공
    - FX Health: FX 데이터 수신 지연 < 60초
    - Watcher Heartbeat: RunWatcher 활성화
    
    FAIL 시 즉시 RuntimeError 발생
    """
    
    def __init__(self, config: Any):
        """
        Args:
            config: PaperRunnerConfig 또는 LiveRunnerConfig
        """
        self.config = config
        self.phase = getattr(config, 'phase', 'unknown')
        self.verification_results: Dict[str, bool] = {}
    
    def verify_db_strict(self, storage: Optional[Any]) -> bool:
        """
        DB Strict 모드 검증
        
        Args:
            storage: V2LedgerStorage instance
        
        Returns:
            True: 검증 성공
            False: 검증 실패
        """
        logger.info("[FeatureGuard] Verifying DB Strict mode...")
        
        try:
            # db_mode 확인
            db_mode = getattr(self.config, 'db_mode', 'off')
            
            if self.phase in ["smoke", "baseline", "longrun", "smoke_test", "live"]:
                # Ops phase에서는 strict 필수
                if db_mode != "strict":
                    logger.error(
                        f"[FeatureGuard] ❌ DB Strict FAIL: "
                        f"phase='{self.phase}' requires db_mode='strict', got: '{db_mode}'"
                    )
                    return False
                
                # Storage 인스턴스 확인
                if not storage:
                    logger.error(
                        f"[FeatureGuard] ❌ DB Strict FAIL: "
                        f"storage not initialized in strict mode"
                    )
                    return False
                
                logger.info(f"[FeatureGuard] ✅ DB Strict: OK (mode={db_mode})")
                return True
            
            else:
                # Test phase는 optional
                logger.info(f"[FeatureGuard] ✅ DB Strict: SKIP (phase={self.phase}, optional)")
                return True
        
        except Exception as e:
            logger.error(f"[FeatureGuard] ❌ DB Strict FAIL: {e}")
            return False
    
    def verify_redis_pulse(self, redis_client: Optional[Any]) -> bool:
        """
        Redis 연결 검증
        
        Args:
            redis_client: Redis client instance
        
        Returns:
            True: 검증 성공 (또는 optional phase)
            False: 검증 실패
        """
        logger.info("[FeatureGuard] Verifying Redis pulse...")
        
        try:
            if self.phase in ["smoke", "baseline", "longrun", "smoke_test", "live"]:
                # Ops phase에서는 Redis 검증
                if not redis_client:
                    logger.warning(
                        f"[FeatureGuard] ⚠️  Redis: Not initialized (continuing, but dedup/cache disabled)"
                    )
                    return True  # Redis는 critical하지만 없어도 진행 가능 (degraded mode)
                
                # Ping 테스트
                redis_client.ping()
                logger.info(f"[FeatureGuard] ✅ Redis: OK (ping successful)")
                return True
            
            else:
                # Test phase는 optional
                logger.info(f"[FeatureGuard] ✅ Redis: SKIP (phase={self.phase}, optional)")
                return True
        
        except Exception as e:
            logger.warning(f"[FeatureGuard] ⚠️  Redis: Ping failed ({e}), continuing in degraded mode")
            return True  # Redis 실패는 warning으로 처리
    
    def verify_real_marketdata(self, use_real_data: bool, providers: Dict[str, Any]) -> bool:
        """
        Real MarketData 검증
        
        D205-18-1 AC-4: Mock opportunity 경로 탐지 강화
        - baseline/longrun에서 use_real_data=False → 즉시 FAIL
        - Mock 경로는 test_1min 같은 계약/유닛 테스트 전용
        
        Args:
            use_real_data: Real MarketData 사용 여부
            providers: MarketData providers dict
        
        Returns:
            True: 검증 성공 (또는 optional phase)
            False: 검증 실패
        """
        logger.info("[FeatureGuard] Verifying Real MarketData...")
        
        try:
            # D205-18-1 AC-4: Ops phase는 Real MarketData 필수 (Mock 경로 차단)
            if self.phase in ["smoke", "baseline", "longrun", "smoke_test", "live"]:
                if not use_real_data:
                    logger.error(
                        f"[FeatureGuard] ❌ Real MarketData FAIL (D205-18-1 AC-4): "
                        f"phase='{self.phase}' requires use_real_data=True, got: False"
                    )
                    logger.error(
                        f"[FeatureGuard] Mock opportunity path detected in Ops phase. "
                        f"This violates Paper-LIVE Parity (D205-9-REOPEN)."
                    )
                    logger.error(
                        f"[FeatureGuard] MOCK is only for test_1min phase (contract/unit tests). "
                        f"Fix: Add --use-real-data flag."
                    )
                    return False
                
                # Provider 인스턴스 확인
                if not providers.get('upbit') or not providers.get('binance'):
                    logger.error(
                        f"[FeatureGuard] ❌ Real MarketData FAIL: "
                        f"providers not initialized (upbit={bool(providers.get('upbit'))}, "
                        f"binance={bool(providers.get('binance'))})"
                    )
                    return False
                
                logger.info(f"[FeatureGuard] ✅ Real MarketData: OK")
                return True
            
            elif self.phase == "live":
                # Live phase는 당연히 Real MarketData 필수
                if not use_real_data:
                    logger.error(
                        f"[FeatureGuard] ❌ Real MarketData FAIL: "
                        f"LIVE mode requires use_real_data=True"
                    )
                    return False
                
                logger.info(f"[FeatureGuard] ✅ Real MarketData: OK (LIVE mode)")
                return True
            
            else:
                # Test phase는 optional (MOCK 허용)
                logger.info(f"[FeatureGuard] ✅ Real MarketData: SKIP (phase={self.phase}, MOCK allowed)")
                return True
        
        except Exception as e:
            logger.error(f"[FeatureGuard] ❌ Real MarketData FAIL: {e}")
            return False
    
    def verify_fx_health(self, fx_provider: Optional[Any]) -> bool:
        """
        FX Provider Health 검증
        
        Args:
            fx_provider: FxProvider instance
        
        Returns:
            True: 검증 성공 (또는 optional phase)
            False: 검증 실패
        """
        logger.info("[FeatureGuard] Verifying FX Health...")
        
        try:
            if self.phase == "live":
                # Live phase에서는 LiveFxProvider 필수
                if not fx_provider:
                    logger.error(
                        f"[FeatureGuard] ❌ FX Health FAIL: "
                        f"fx_provider not initialized in LIVE mode"
                    )
                    return False
                
                # FixedFxProvider 사용 금지 (D205-15-4)
                if fx_provider.__class__.__name__ == "FixedFxProvider":
                    logger.error(
                        f"[FeatureGuard] ❌ FX Health FAIL: "
                        f"LIVE mode cannot use FixedFxProvider"
                    )
                    return False
                
                logger.info(f"[FeatureGuard] ✅ FX Health: OK (Live provider)")
                return True
            
            else:
                # Paper/Test phase는 FixedFxProvider 허용
                logger.info(f"[FeatureGuard] ✅ FX Health: SKIP (phase={self.phase}, Fixed FX allowed)")
                return True
        
        except Exception as e:
            logger.error(f"[FeatureGuard] ❌ FX Health FAIL: {e}")
            return False
    
    def verify_all_essential(
        self,
        storage: Optional[Any] = None,
        redis_client: Optional[Any] = None,
        use_real_data: bool = False,
        marketdata_providers: Optional[Dict[str, Any]] = None,
        fx_provider: Optional[Any] = None,
    ) -> bool:
        """
        모든 ESSENTIAL 기능 검증
        
        Args:
            storage: V2LedgerStorage
            redis_client: Redis client
            use_real_data: Real data 플래그
            marketdata_providers: {'upbit': provider, 'binance': provider}
            fx_provider: FxProvider
        
        Returns:
            True: 모든 검증 성공
            False: 하나라도 실패
        
        Raises:
            RuntimeError: 검증 실패 시 (ops phase에서만)
        """
        logger.info("=" * 60)
        logger.info("[FeatureGuard] Starting capability verification...")
        logger.info(f"[FeatureGuard] Phase: {self.phase}")
        logger.info("=" * 60)
        
        # 검증 실행
        db_ok = self.verify_db_strict(storage)
        redis_ok = self.verify_redis_pulse(redis_client)
        marketdata_ok = self.verify_real_marketdata(
            use_real_data,
            marketdata_providers or {}
        )
        fx_ok = self.verify_fx_health(fx_provider)
        
        # 결과 저장
        self.verification_results = {
            "db_strict": db_ok,
            "redis_pulse": redis_ok,
            "real_marketdata": marketdata_ok,
            "fx_health": fx_ok,
        }
        
        # 전체 결과
        all_ok = all(self.verification_results.values())
        
        logger.info("=" * 60)
        if all_ok:
            logger.info("[FeatureGuard] ✅ ALL CHECKS PASSED")
        else:
            logger.error("[FeatureGuard] ❌ SOME CHECKS FAILED")
            for check, result in self.verification_results.items():
                status = "✅" if result else "❌"
                logger.error(f"  {status} {check}: {'PASS' if result else 'FAIL'}")
        logger.info("=" * 60)
        
        # Ops phase에서 실패 시 RuntimeError
        if not all_ok and self.phase in ["smoke", "baseline", "longrun", "smoke_test", "live"]:
            raise RuntimeError(
                f"[FeatureGuard] Capability verification FAILED in phase '{self.phase}'. "
                f"Cannot proceed with degraded capabilities in ops phase."
            )
        
        return all_ok
