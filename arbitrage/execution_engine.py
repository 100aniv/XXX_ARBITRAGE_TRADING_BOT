#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Execution Engine (PHASE D7)
============================

시그널 기반 주문 실행 및 체결 추적.

PHASE D8: 안전 검증 통합
"""

import logging
import time
from typing import Dict, Any, Optional, Tuple
from datetime import datetime

logger = logging.getLogger(__name__)


class ExecutionEngine:
    """실행 엔진"""
    
    def __init__(self, config: Dict[str, Any] = None):
        """
        Args:
            config: 설정 딕셔너리
        """
        self.config = config or {}
        
        # 포지션 사이즈
        self.position_size_krw = self.config.get("position_size_krw", 100000)
        self.position_size_btc = self.config.get("position_size_btc", 0.01)
        
        # 실행 설정
        self.max_retries = self.config.get("max_retries", 3)
        self.retry_delay = self.config.get("retry_delay", 1)
        
        # 통계
        self.total_signals = 0
        self.total_executions = 0
        self.successful_executions = 0
        self.failed_executions = 0
        self.total_slippage = 0.0
        self.total_latency_ms = 0.0
    
    def execute_signal(
        self,
        signal: Any,  # ArbitrageSignal
        upbit_api: Any,
        binance_api: Any,
        order_manager: Any,
        safety_validator: Any = None  # SafetyValidator (D8)
    ) -> Tuple[bool, Optional[Tuple[str, str]]]:
        """
        신호 기반 주문 실행 (안전 검증 포함)
        
        Args:
            signal: ArbitrageSignal 객체
            upbit_api: Upbit API
            binance_api: Binance API
            order_manager: OrderManager
            safety_validator: SafetyValidator (D8)
        
        Returns:
            (성공 여부, (매수 주문 ID, 매도 주문 ID))
        """
        try:
            self.total_signals += 1
            
            logger.info(
                f"[EXEC] Executing signal: {signal.opportunity_type}, "
                f"profit={signal.profit_pct:.2f}%"
            )
            
            # D8: 신호 검증
            if safety_validator:
                is_valid, reason = safety_validator.validate_signal(signal)
                if not is_valid:
                    logger.warning(f"[EXEC] Signal validation failed: {reason}")
                    self.failed_executions += 1
                    return False, None
            
            # D8: 시스템 건강도 검증
            if safety_validator:
                is_healthy, reason = safety_validator.validate_system_health()
                if not is_healthy:
                    logger.warning(f"[EXEC] System health check failed: {reason}")
                    self.failed_executions += 1
                    return False, None
            
            # 매수 주문
            buy_order_id = self._place_buy_order(
                signal=signal,
                upbit_api=upbit_api,
                binance_api=binance_api,
                order_manager=order_manager,
                safety_validator=safety_validator
            )
            
            if not buy_order_id:
                logger.error("[EXEC] Buy order failed")
                self.failed_executions += 1
                return False, None
            
            # 매도 주문
            sell_order_id = self._place_sell_order(
                signal=signal,
                upbit_api=upbit_api,
                binance_api=binance_api,
                order_manager=order_manager,
                safety_validator=safety_validator
            )
            
            if not sell_order_id:
                logger.error("[EXEC] Sell order failed")
                self.failed_executions += 1
                return False, None
            
            self.total_executions += 1
            self.successful_executions += 1
            
            logger.info(
                f"[EXEC] Orders placed: buy={buy_order_id}, sell={sell_order_id}"
            )
            
            return True, (buy_order_id, sell_order_id)
        
        except Exception as e:
            logger.error(f"[EXEC] Execution error: {e}")
            self.failed_executions += 1
            return False, None
    
    def _place_buy_order(
        self,
        signal: Any,
        upbit_api: Any,
        binance_api: Any,
        order_manager: Any,
        safety_validator: Any = None
    ) -> Optional[str]:
        """매수 주문 실행 (안전 검증 포함)"""
        try:
            api = upbit_api if signal.buy_exchange == "upbit" else binance_api
            symbol = "BTC-KRW" if signal.buy_exchange == "upbit" else "BTCUSDT"
            
            # 주문 생성
            order = order_manager.create_order(
                exchange=signal.buy_exchange,
                symbol=symbol,
                side="BUY",
                quantity=self.position_size_btc,
                price=signal.buy_price,
                order_type="LIMIT"
            )
            
            # API 호출
            start_time = time.time()
            from arbitrage.live_api import OrderRequest
            
            order_req = OrderRequest(
                symbol=symbol,
                side="BUY",
                quantity=self.position_size_btc,
                price=signal.buy_price,
                order_type="LIMIT"
            )
            
            response = api.place_order(order_req)
            latency_ms = (time.time() - start_time) * 1000
            
            # D8: 지연 검증
            if safety_validator:
                is_valid, reason = safety_validator.validate_order_latency(latency_ms)
                if not is_valid:
                    logger.warning(f"[EXEC] Buy order latency check failed: {reason}")
                    return None
            
            if response:
                order_manager.update_order_status(
                    order.order_id,
                    status=__import__('arbitrage.order_manager', fromlist=['OrderStatus']).OrderStatus.FILLED,
                    filled_quantity=self.position_size_btc,
                    average_fill_price=signal.buy_price,
                    latency_ms=latency_ms
                )
                self.total_latency_ms += latency_ms
                logger.info(f"[EXEC] Buy order filled: {order.order_id}, latency={latency_ms:.1f}ms")
                return order.order_id
            
            return None
        except Exception as e:
            logger.error(f"[EXEC] Buy order error: {e}")
            return None
    
    def _place_sell_order(
        self,
        signal: Any,
        upbit_api: Any,
        binance_api: Any,
        order_manager: Any,
        safety_validator: Any = None
    ) -> Optional[str]:
        """매도 주문 실행 (안전 검증 포함)"""
        try:
            api = upbit_api if signal.sell_exchange == "upbit" else binance_api
            symbol = "BTC-KRW" if signal.sell_exchange == "upbit" else "BTCUSDT"
            
            # 주문 생성
            order = order_manager.create_order(
                exchange=signal.sell_exchange,
                symbol=symbol,
                side="SELL",
                quantity=self.position_size_btc,
                price=signal.sell_price,
                order_type="LIMIT"
            )
            
            # API 호출
            start_time = time.time()
            from arbitrage.live_api import OrderRequest
            
            order_req = OrderRequest(
                symbol=symbol,
                side="SELL",
                quantity=self.position_size_btc,
                price=signal.sell_price,
                order_type="LIMIT"
            )
            
            response = api.place_order(order_req)
            latency_ms = (time.time() - start_time) * 1000
            
            # D8: 지연 검증
            if safety_validator:
                is_valid, reason = safety_validator.validate_order_latency(latency_ms)
                if not is_valid:
                    logger.warning(f"[EXEC] Sell order latency check failed: {reason}")
                    return None
            
            if response:
                order_manager.update_order_status(
                    order.order_id,
                    status=__import__('arbitrage.order_manager', fromlist=['OrderStatus']).OrderStatus.FILLED,
                    filled_quantity=self.position_size_btc,
                    average_fill_price=signal.sell_price,
                    latency_ms=latency_ms
                )
                self.total_latency_ms += latency_ms
                logger.info(f"[EXEC] Sell order filled: {order.order_id}, latency={latency_ms:.1f}ms")
                return order.order_id
            
            return None
        except Exception as e:
            logger.error(f"[EXEC] Sell order error: {e}")
            return None
    
    def get_stats(self) -> Dict[str, Any]:
        """통계 조회"""
        success_rate = (
            self.successful_executions / self.total_signals * 100
            if self.total_signals > 0 else 0
        )
        avg_latency = (
            self.total_latency_ms / self.total_executions
            if self.total_executions > 0 else 0
        )
        
        return {
            "total_signals": self.total_signals,
            "total_executions": self.total_executions,
            "successful_executions": self.successful_executions,
            "failed_executions": self.failed_executions,
            "success_rate": success_rate,
            "avg_latency_ms": avg_latency
        }
