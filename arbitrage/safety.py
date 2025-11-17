#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Real Trading Safety Layer (PHASE D8)
=====================================

실거래 모드에서 필수적인 안전장치 및 리스크 가드레일.
fail-closed design: 모든 검증 실패 시 거래 차단.
"""

import logging
import time
from typing import Dict, Any, Optional, Tuple
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class SafetyContext:
    """안전 검증 컨텍스트"""
    
    def __init__(self, config: Dict[str, Any] = None):
        """
        Args:
            config: 안전 설정
        """
        self.config = config or {}
        
        # 안전 임계값
        self.max_slippage_pct = self.config.get("max_slippage_pct", 0.30)
        self.max_order_delay_ms = self.config.get("max_order_delay_ms", 2500)
        self.max_position_size_krw = self.config.get("max_position_size_krw", 300000)
        self.max_daily_loss_krw = self.config.get("max_daily_loss_krw", 150000)
        self.min_liquidity_krw = self.config.get("min_liquidity_krw", 20000000)
        self.require_ws_freshness = self.config.get("require_ws_freshness", True)
        self.require_redis_heartbeat = self.config.get("require_redis_heartbeat", True)
        
        # 상태 추적
        self.daily_loss_krw = 0.0
        self.current_position_exposure_krw = 0.0
        self.last_ws_update_time = datetime.now()
        self.last_redis_heartbeat_time = datetime.now()
        self.safety_rejections_count = 0
        self.slippage_excess_count = 0
        self.health_fail_count = 0
    
    def reset_daily_loss(self):
        """일일 손실 리셋 (자정)"""
        self.daily_loss_krw = 0.0
        logger.info("[Safety] Daily loss reset")
    
    def update_daily_loss(self, loss_krw: float):
        """일일 손실 업데이트"""
        self.daily_loss_krw += loss_krw
        logger.debug(f"[Safety] Daily loss updated: {self.daily_loss_krw:.0f}₩")
    
    def update_position_exposure(self, exposure_krw: float):
        """포지션 노출도 업데이트"""
        self.current_position_exposure_krw = exposure_krw
    
    def update_ws_freshness(self):
        """WebSocket 신선도 업데이트"""
        self.last_ws_update_time = datetime.now()
    
    def update_redis_heartbeat(self):
        """Redis heartbeat 업데이트"""
        self.last_redis_heartbeat_time = datetime.now()


class SafetyValidator:
    """안전 검증기"""
    
    def __init__(self, context: SafetyContext):
        """
        Args:
            context: SafetyContext 객체
        """
        self.context = context
    
    def validate_signal(self, signal: Any) -> Tuple[bool, Optional[str]]:
        """
        신호 검증
        
        Args:
            signal: ArbitrageSignal 객체
        
        Returns:
            (통과 여부, 거부 사유)
        """
        try:
            # 1. 신뢰도 확인
            if signal.confidence < 0.3:
                reason = f"Low confidence: {signal.confidence:.2f} < 0.3"
                self.context.safety_rejections_count += 1
                logger.warning(f"[Safety] Signal rejected: {reason}")
                return False, reason
            
            # 2. 최소 수익 확인
            if signal.profit_pct < 0.05:
                reason = f"Insufficient profit: {signal.profit_pct:.3f}% < 0.05%"
                self.context.safety_rejections_count += 1
                logger.warning(f"[Safety] Signal rejected: {reason}")
                return False, reason
            
            # 3. 스프레드 건전성 확인
            if signal.spread_pct < 0.0:
                reason = f"Invalid spread: {signal.spread_pct:.3f}%"
                self.context.safety_rejections_count += 1
                logger.warning(f"[Safety] Signal rejected: {reason}")
                return False, reason
            
            logger.debug(f"[Safety] Signal validated: profit={signal.profit_pct:.3f}%")
            return True, None
        
        except Exception as e:
            reason = f"Signal validation error: {e}"
            self.context.safety_rejections_count += 1
            logger.error(f"[Safety] {reason}")
            return False, reason
    
    def validate_execution(self, execution_request: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
        """
        실행 요청 검증
        
        Args:
            execution_request: {
                "buy_exchange": str,
                "buy_price": float,
                "sell_exchange": str,
                "sell_price": float,
                "quantity": float,
                "estimated_slippage_pct": float
            }
        
        Returns:
            (통과 여부, 거부 사유)
        """
        try:
            # 1. 슬리피지 확인
            estimated_slippage = execution_request.get("estimated_slippage_pct", 0.0)
            if estimated_slippage > self.context.max_slippage_pct:
                reason = f"Slippage too high: {estimated_slippage:.3f}% > {self.context.max_slippage_pct:.3f}%"
                self.context.slippage_excess_count += 1
                self.context.safety_rejections_count += 1
                logger.warning(f"[Safety] Execution rejected: {reason}")
                return False, reason
            
            # 2. 포지션 사이즈 확인
            buy_price = execution_request.get("buy_price", 0)
            quantity = execution_request.get("quantity", 0)
            position_size_krw = buy_price * quantity
            
            if position_size_krw > self.context.max_position_size_krw:
                reason = f"Position too large: {position_size_krw:.0f}₩ > {self.context.max_position_size_krw:.0f}₩"
                self.context.safety_rejections_count += 1
                logger.warning(f"[Safety] Execution rejected: {reason}")
                return False, reason
            
            # 3. 일일 손실 확인
            if self.context.daily_loss_krw > self.context.max_daily_loss_krw:
                reason = f"Daily loss exceeded: {self.context.daily_loss_krw:.0f}₩ > {self.context.max_daily_loss_krw:.0f}₩"
                self.context.safety_rejections_count += 1
                logger.warning(f"[Safety] Execution rejected: {reason}")
                return False, reason
            
            # 4. 유동성 확인
            min_liquidity = execution_request.get("min_liquidity_krw", 0)
            if min_liquidity < self.context.min_liquidity_krw:
                reason = f"Insufficient liquidity: {min_liquidity:.0f}₩ < {self.context.min_liquidity_krw:.0f}₩"
                self.context.safety_rejections_count += 1
                logger.warning(f"[Safety] Execution rejected: {reason}")
                return False, reason
            
            logger.debug(f"[Safety] Execution validated: size={position_size_krw:.0f}₩, slippage={estimated_slippage:.3f}%")
            return True, None
        
        except Exception as e:
            reason = f"Execution validation error: {e}"
            self.context.safety_rejections_count += 1
            logger.error(f"[Safety] {reason}")
            return False, reason
    
    def validate_system_health(self) -> Tuple[bool, Optional[str]]:
        """
        시스템 건강도 검증
        
        Returns:
            (통과 여부, 거부 사유)
        """
        try:
            failures = []
            
            # 1. WebSocket 신선도 확인
            if self.context.require_ws_freshness:
                ws_age_sec = (datetime.now() - self.context.last_ws_update_time).total_seconds()
                if ws_age_sec > 30:  # 30초 이상 업데이트 없음
                    failures.append(f"WebSocket stale: {ws_age_sec:.0f}s old")
            
            # 2. Redis heartbeat 확인
            if self.context.require_redis_heartbeat:
                hb_age_sec = (datetime.now() - self.context.last_redis_heartbeat_time).total_seconds()
                if hb_age_sec > 60:  # 60초 이상 heartbeat 없음
                    failures.append(f"Redis heartbeat stale: {hb_age_sec:.0f}s old")
            
            if failures:
                reason = "; ".join(failures)
                self.context.health_fail_count += 1
                self.context.safety_rejections_count += 1
                logger.warning(f"[Safety] System health check failed: {reason}")
                return False, reason
            
            logger.debug("[Safety] System health check passed")
            return True, None
        
        except Exception as e:
            reason = f"Health check error: {e}"
            self.context.health_fail_count += 1
            self.context.safety_rejections_count += 1
            logger.error(f"[Safety] {reason}")
            return False, reason
    
    def validate_order_latency(self, latency_ms: float) -> Tuple[bool, Optional[str]]:
        """
        주문 지연 검증
        
        Args:
            latency_ms: 지연 시간 (ms)
        
        Returns:
            (통과 여부, 거부 사유)
        """
        if latency_ms > self.context.max_order_delay_ms:
            reason = f"Order latency too high: {latency_ms:.0f}ms > {self.context.max_order_delay_ms}ms"
            self.context.safety_rejections_count += 1
            logger.warning(f"[Safety] Latency check failed: {reason}")
            return False, reason
        
        logger.debug(f"[Safety] Latency check passed: {latency_ms:.0f}ms")
        return True, None
    
    def validate_api_key(self, api_key: str) -> Tuple[bool, Optional[str]]:
        """
        API 키 검증
        
        Args:
            api_key: API 키
        
        Returns:
            (통과 여부, 거부 사유)
        """
        if not api_key or len(api_key) < 10:
            reason = "Invalid or missing API key"
            self.context.safety_rejections_count += 1
            logger.warning(f"[Safety] API key check failed: {reason}")
            return False, reason
        
        logger.debug("[Safety] API key check passed")
        return True, None
    
    def get_safety_stats(self) -> Dict[str, Any]:
        """안전 통계 조회"""
        return {
            "safety_rejections_count": self.context.safety_rejections_count,
            "slippage_excess_count": self.context.slippage_excess_count,
            "health_fail_count": self.context.health_fail_count,
            "daily_loss_krw": self.context.daily_loss_krw,
            "current_position_exposure_krw": self.context.current_position_exposure_krw,
            "ws_freshness_sec": (datetime.now() - self.context.last_ws_update_time).total_seconds(),
            "redis_heartbeat_sec": (datetime.now() - self.context.last_redis_heartbeat_time).total_seconds()
        }
