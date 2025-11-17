#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
D16 Live Trading — Live Arbitrage Trader
=========================================

실거래 차익 거래 루프:
- 실시간 가격 수집
- 차익 신호 생성
- 주문 실행
- 포지션 관리
- D15 모듈 연동 (변동성, 포트폴리오, 리스크)

D19 Live Mode Safety Validation:
- Paper Mode: SimulatedExchange + 시나리오 (D17/D18)
- Shadow Live Mode: 실시간 가격 + 신호 생성 + 주문 로그만 기록 (LIVE_MODE=false, DRY_RUN=true)
- Live Mode: 실제 Upbit/Binance 주문 발행 (LIVE_MODE=true, DRY_RUN=false, SAFETY_MODE=true, API keys valid)

D20 LIVE ARM System:
- ARM 파일 + ARM 토큰 기반의 2단계 무장 시스템
- Live 모드 진입 시 ARM 조건을 반드시 만족해야 함
- ARM이 안 되어 있으면 무조건 Shadow Live Mode로 강등
"""

import logging
import asyncio
import os
from typing import Dict, List, Optional, Tuple
from datetime import datetime
import numpy as np

from data.live_prices import LivePriceCollector
from arbitrage.types import (
    Price, Signal, Order, Position, ExecutionResult, PortfolioState,
    OrderSide, ExchangeType
)
from arbitrage.state_manager import StateManager
from arbitrage.exchange import UpbitExchange, BinanceExchange
from liveguard.safety import SafetyModule
from liveguard.risk_limits import RiskLimits

# D15 모듈 임포트
from ml.volatility_model import VolatilityPredictor
from arbitrage.portfolio_optimizer import PortfolioOptimizer
from arbitrage.risk_quant import QuantitativeRiskManager

logger = logging.getLogger(__name__)


class LiveTrader:
    """
    실거래 차익 거래자
    
    D15 고성능 모듈을 활용한 실거래 실행.
    D19: Live Mode Safety Validation 지원
    - Paper Mode: 시뮬레이션 (D17/D18)
    - Shadow Live Mode: 실시간 가격 + 신호 생성 + 주문 로그만 기록
    - Live Mode: 실제 거래 (엄격한 조건 충족 시에만)
    
    D20: LIVE ARM System 지원
    - ARM 파일 + ARM 토큰 기반의 2단계 무장 시스템
    - Live 모드는 ARM 조건을 모두 만족할 때만 활성화
    - ARM 실패 시 무조건 Shadow Live Mode로 강등
    """
    
    def __init__(
        self,
        upbit_api_key: str,
        upbit_secret_key: str,
        binance_api_key: str,
        binance_secret_key: str,
        redis_host: str = "localhost",
        redis_port: int = 6379,
        risk_limits: Optional[RiskLimits] = None,
        live_mode: bool = False,
        safety_mode: bool = True,
        dry_run: bool = True
    ):
        """
        Args:
            upbit_api_key: Upbit API 키
            upbit_secret_key: Upbit 시크릿 키
            binance_api_key: Binance API 키
            binance_secret_key: Binance 시크릿 키
            redis_host: Redis 호스트
            redis_port: Redis 포트
            risk_limits: 리스크 제한 설정
            live_mode: 실거래 모드 활성화 (기본: False)
            safety_mode: 안전 모드 활성화 (기본: True)
            dry_run: 드라이런 모드 (기본: True)
        """
        # 환경 변수에서 모드 설정 읽기
        # 파라미터 기본값이 있으므로, 환경 변수가 설정되어 있으면 환경 변수를 우선함
        env_live_mode = os.getenv("LIVE_MODE")
        self.live_mode = env_live_mode.lower() == "true" if env_live_mode else live_mode
        
        env_safety_mode = os.getenv("SAFETY_MODE")
        self.safety_mode = env_safety_mode.lower() == "true" if env_safety_mode else safety_mode
        
        env_dry_run = os.getenv("DRY_RUN")
        self.dry_run = env_dry_run.lower() == "true" if env_dry_run else dry_run
        
        # D20: LIVE ARM 평가
        self.live_armed = self._evaluate_live_arming()
        
        # Live Mode 진입 조건 검증 (D19)
        base_live_enabled = self._validate_live_mode(
            upbit_api_key, upbit_secret_key,
            binance_api_key, binance_secret_key,
            risk_limits
        )
        
        # D20: Live Mode는 ARM 조건도 만족해야 함
        self.live_enabled = base_live_enabled and self.live_armed
        
        # 거래소 연결
        self.upbit = UpbitExchange(upbit_api_key, upbit_secret_key)
        self.binance = BinanceExchange(binance_api_key, binance_secret_key)
        
        # 가격 수집
        self.price_collector = LivePriceCollector(
            upbit_api_key, upbit_secret_key,
            binance_api_key, binance_secret_key
        )
        
        # 상태 관리 (D21: namespace를 live:docker로 설정)
        # 환경 변수에서 모드 정보 읽기
        env_app_env = os.getenv("APP_ENV", "docker")
        self.state_manager = StateManager(
            redis_host=redis_host,
            redis_port=redis_port,
            redis_db=0,
            namespace=f"live:{env_app_env}",
            enabled=True,
            key_prefix="arbitrage"
        )
        
        # 안전 장치
        self.safety = SafetyModule(risk_limits or RiskLimits())
        
        # D15 모듈
        self.volatility_predictor = VolatilityPredictor()
        self.portfolio_optimizer = PortfolioOptimizer()
        self.risk_manager = QuantitativeRiskManager()
        
        # 상태
        self._running = False
        self._positions: Dict[str, Position] = {}
        self._orders: Dict[str, Order] = {}
        self._total_balance = 0.0
        self._available_balance = 0.0
        
        # 모드 로깅
        logger.info(f"[LIVE_STATUS] requested_live_mode={self.live_mode}, "
                   f"safety_mode={self.safety_mode}, dry_run={self.dry_run}, "
                   f"live_armed={self.live_armed}, live_enabled={self.live_enabled}")
    
    def _evaluate_live_arming(self) -> bool:
        """
        D20: LIVE ARM 평가
        
        Live 모드에 진입하기 위한 2단계 무장(arming) 시스템:
        1. ARM 파일 존재 여부 (LIVE_ARM_FILE 환경 변수, 기본값: "configs/LIVE_ARMED")
        2. ARM 토큰 검증 (LIVE_ARM_TOKEN 환경 변수, 기본값: "I_UNDERSTAND_LIVE_RISK")
        
        두 조건을 모두 만족해야만 ARM 상태가 True
        """
        # ARM 파일 경로 (기본값: configs/LIVE_ARMED)
        arm_file = os.getenv("LIVE_ARM_FILE", "configs/LIVE_ARMED")
        
        # ARM 토큰 (기본값: I_UNDERSTAND_LIVE_RISK)
        arm_token = os.getenv("LIVE_ARM_TOKEN", "")
        expected_token = "I_UNDERSTAND_LIVE_RISK"
        
        # 조건 1: ARM 파일 존재 여부
        arm_file_exists = os.path.isfile(arm_file)
        
        # 조건 2: ARM 토큰 일치 여부
        arm_token_valid = arm_token == expected_token
        
        # 두 조건을 모두 만족해야 ARM 상태가 True
        is_armed = arm_file_exists and arm_token_valid
        
        if is_armed:
            logger.warning("[LIVE_ARM] LIVE ARMED. Live trading is fully enabled.")
        else:
            logger.warning("[LIVE_ARM] Live arm not satisfied. Falling back to SHADOW_LIVE mode.")
            if not arm_file_exists:
                logger.debug(f"[LIVE_ARM] ARM file not found: {arm_file}")
            if not arm_token_valid:
                logger.debug(f"[LIVE_ARM] ARM token invalid or not set")
        
        return is_armed
    
    def _validate_live_mode(
        self,
        upbit_api_key: str,
        upbit_secret_key: str,
        binance_api_key: str,
        binance_secret_key: str,
        risk_limits: Optional[RiskLimits]
    ) -> bool:
        """
        D19: Live Mode 진입 조건 검증
        
        Live Mode 진입 조건 (모두 만족해야 함):
        1. LIVE_MODE == "true"
        2. SAFETY_MODE == "true"
        3. DRY_RUN == "false"
        4. Upbit/Binance API 키가 모두 존재
        5. RiskLimits가 유효한 값으로 설정
        
        하나라도 만족하지 않으면 Shadow Live Mode로 동작
        (D20에서는 추가로 ARM 조건도 확인됨)
        """
        # 기본값: Shadow Live Mode
        if not self.live_mode:
            logger.warning("Live Mode disabled: LIVE_MODE=false → Shadow Live Mode")
            return False
        
        if not self.safety_mode:
            logger.warning("Live Mode disabled: SAFETY_MODE=false → Shadow Live Mode")
            return False
        
        if self.dry_run:
            logger.warning("Live Mode disabled: DRY_RUN=true → Shadow Live Mode")
            return False
        
        # API 키 검증
        if not all([upbit_api_key, upbit_secret_key, binance_api_key, binance_secret_key]):
            logger.warning("Live Mode disabled: Missing API keys → Shadow Live Mode")
            return False
        
        # RiskLimits 검증
        if not risk_limits:
            logger.warning("Live Mode disabled: RiskLimits not configured → Shadow Live Mode")
            return False
        
        if risk_limits.max_position_size <= 0 or risk_limits.max_daily_loss <= 0:
            logger.warning("Live Mode disabled: Invalid RiskLimits → Shadow Live Mode")
            return False
        
        logger.info("✅ Live Mode ENABLED - All conditions satisfied")
        return True
    
    def _assert_live_mode_safety(self) -> None:
        """
        Live Mode 안전 검사
        
        실제 거래 전에 반드시 통과해야 할 조건들을 검증
        """
        if not self.live_enabled:
            raise RuntimeError("Live Mode not enabled - cannot execute real orders")
        
        if self.safety.state.circuit_breaker_active:
            raise RuntimeError("Circuit breaker is active - trading halted")
        
        if self.safety.state.daily_loss >= self.safety.limits.max_daily_loss:
            raise RuntimeError("Daily loss limit exceeded")
        
        logger.debug("Live Mode safety checks passed")
    
    async def connect(self) -> None:
        """모든 연결 초기화"""
        await self.upbit.connect()
        await self.binance.connect()
        await self.price_collector.connect()
        self.state_manager.connect()
        logger.info("Live trader connected")
    
    async def disconnect(self) -> None:
        """모든 연결 종료"""
        await self.upbit.disconnect()
        await self.binance.disconnect()
        await self.price_collector.disconnect()
        self.state_manager.disconnect()
        logger.info("Live trader disconnected")
    
    async def start(
        self,
        upbit_symbols: List[str],
        binance_symbols: List[str],
        min_spread_pct: float = 0.5
    ) -> None:
        """
        실거래 루프 시작
        
        Args:
            upbit_symbols: Upbit 심볼 목록
            binance_symbols: Binance 심볼 목록
            min_spread_pct: 최소 수익 스프레드 (%)
        """
        self._running = True
        self.min_spread_pct = min_spread_pct
        
        # 가격 수집 시작
        self.price_collector.subscribe(self._on_price_update)
        
        # 메인 루프
        try:
            await asyncio.gather(
                self.price_collector.start(upbit_symbols, binance_symbols),
                self._main_loop()
            )
        except Exception as e:
            logger.error(f"Error in trading loop: {e}")
            self._running = False
    
    async def stop(self) -> None:
        """실거래 루프 중지"""
        self._running = False
        await self.price_collector.stop()
    
    async def _on_price_update(self, price: Price) -> None:
        """
        가격 업데이트 핸들러
        
        Args:
            price: 업데이트된 가격
        """
        # Redis에 가격 저장
        self.state_manager.set_price(
            price.exchange.value,
            price.symbol,
            price.bid,
            price.ask
        )
    
    async def _main_loop(self) -> None:
        """메인 거래 루프"""
        while self._running:
            try:
                # 1. 포트폴리오 상태 업데이트
                await self._update_portfolio_state()
                
                # 2. 차익 신호 생성
                signals = await self._generate_signals()
                
                # 3. 신호 필터링 및 실행
                for signal in signals:
                    await self._execute_signal(signal)
                
                # 4. 포지션 관리
                await self._manage_positions()
                
                # 5. 메트릭 업데이트
                await self._update_metrics()
                
                # 루프 대기
                await asyncio.sleep(1)
            
            except Exception as e:
                logger.error(f"Error in main loop: {e}")
                await asyncio.sleep(5)
    
    async def _update_portfolio_state(self) -> None:
        """포트폴리오 상태 업데이트"""
        try:
            # 잔액 조회
            upbit_balance = await self.upbit.get_balance()
            binance_balance = await self.binance.get_balance()
            
            # 총 잔액 계산 (KRW 기준)
            krw_balance = upbit_balance.get("KRW", 0)
            usdt_balance = binance_balance.get("USDT", 0)
            
            # USDT를 KRW로 변환 (현재 가격 사용)
            usdt_krw_price = self.price_collector.get_price(
                ExchangeType.UPBIT, "KRW-USDT"
            )
            if usdt_krw_price:
                usdt_krw = usdt_balance * usdt_krw_price.mid
            else:
                usdt_krw = 0
            
            self._total_balance = krw_balance + usdt_krw
            self._available_balance = self._total_balance
            
            # 포트폴리오 상태 저장
            state = PortfolioState(
                total_balance=self._total_balance,
                available_balance=self._available_balance,
                positions=self._positions
            )
            self.state_manager.set_portfolio_state(state)
        
        except Exception as e:
            logger.error(f"Error updating portfolio state: {e}")
    
    async def _generate_signals(self) -> List[Signal]:
        """차익 신호 생성"""
        signals = []
        
        try:
            # Upbit → Binance 차익 (KRW-BTC → BTCUSDT)
            upbit_btc = self.price_collector.get_price(ExchangeType.UPBIT, "KRW-BTC")
            binance_btc = self.price_collector.get_price(ExchangeType.BINANCE, "BTCUSDT")
            
            if upbit_btc and binance_btc:
                # Upbit에서 매수, Binance에서 매도
                spread = binance_btc.bid - upbit_btc.ask
                spread_pct = (spread / upbit_btc.ask) * 100
                
                if spread_pct > self.min_spread_pct:
                    signal = Signal(
                        symbol="BTC",
                        buy_exchange=ExchangeType.UPBIT,
                        sell_exchange=ExchangeType.BINANCE,
                        buy_price=upbit_btc.ask,
                        sell_price=binance_btc.bid,
                        spread=spread,
                        spread_pct=spread_pct
                    )
                    signals.append(signal)
                    self.state_manager.set_signal(signal)
            
            # Binance → Upbit 차익 (BTCUSDT → KRW-BTC)
            if upbit_btc and binance_btc:
                spread = upbit_btc.bid - binance_btc.ask
                spread_pct = (spread / binance_btc.ask) * 100
                
                if spread_pct > self.min_spread_pct:
                    signal = Signal(
                        symbol="BTC",
                        buy_exchange=ExchangeType.BINANCE,
                        sell_exchange=ExchangeType.UPBIT,
                        buy_price=binance_btc.ask,
                        sell_price=upbit_btc.bid,
                        spread=spread,
                        spread_pct=spread_pct
                    )
                    signals.append(signal)
                    self.state_manager.set_signal(signal)
        
        except Exception as e:
            logger.error(f"Error generating signals: {e}")
        
        return signals
    
    async def _execute_signal(self, signal: Signal) -> None:
        """
        신호 실행
        
        Args:
            signal: 실행할 신호
        """
        try:
            # 1. 안전 검사
            can_execute, reason = self.safety.can_execute_order(
                position_value=signal.buy_price * 1,  # 1 BTC 기준
                current_positions=len(self._positions),
                current_loss=0,  # TODO: 실제 손실 계산
                total_balance=self._total_balance
            )
            
            if not can_execute:
                logger.warning(f"Signal rejected: {reason}")
                return
            
            # 2. 스프레드 검사
            can_spread, reason = self.safety.check_spread(signal.spread_pct)
            if not can_spread:
                logger.warning(f"Spread check failed: {reason}")
                return
            
            # 3. 포지션 크기 계산 (D15 변동성 모델 활용)
            # TODO: 변동성 기반 포지션 크기 계산
            position_size = 1.0  # 1 BTC (임시)
            
            # 4. 매수 주문
            buy_order = await self._place_order(
                exchange=signal.buy_exchange,
                symbol=signal.symbol,
                side=OrderSide.BUY,
                quantity=position_size,
                price=signal.buy_price
            )
            
            if not buy_order:
                logger.error(f"Failed to place buy order")
                return
            
            # 5. 매도 주문
            sell_order = await self._place_order(
                exchange=signal.sell_exchange,
                symbol=signal.symbol,
                side=OrderSide.SELL,
                quantity=position_size,
                price=signal.sell_price
            )
            
            if not sell_order:
                logger.error(f"Failed to place sell order")
                # 매수 주문 취소
                await self._cancel_order(signal.buy_exchange, buy_order.order_id)
                return
            
            # 6. 실행 결과 기록
            execution = ExecutionResult(
                symbol=signal.symbol,
                buy_order_id=buy_order.order_id,
                sell_order_id=sell_order.order_id,
                buy_price=signal.buy_price,
                sell_price=signal.sell_price,
                quantity=position_size,
                gross_pnl=signal.spread * position_size,
                net_pnl=signal.spread * position_size * 0.998,  # 수수료 고려
                fees=signal.spread * position_size * 0.002
            )
            
            self.state_manager.set_execution(execution)
            self.safety.record_trade(execution.net_pnl)
            
            logger.info(
                f"Signal executed: {signal.symbol} "
                f"spread={signal.spread_pct:.2f}% "
                f"pnl={execution.net_pnl:.0f}"
            )
        
        except Exception as e:
            logger.error(f"Error executing signal: {e}")
    
    async def _place_order(
        self,
        exchange: ExchangeType,
        symbol: str,
        side: OrderSide,
        quantity: float,
        price: float
    ) -> Optional[Order]:
        """
        주문 생성 (D19: Live Mode Safety Validation)
        
        Args:
            exchange: 거래소
            symbol: 심볼
            side: 주문 방향
            quantity: 수량
            price: 가격
        
        Returns:
            Order 객체 또는 None
        """
        try:
            # D19: Shadow Live Mode 체크
            if not self.live_enabled:
                # Shadow Live Mode: 로그만 남기고 실제 거래는 하지 않음
                logger.info(f"[SHADOW_LIVE] Would place order: {exchange.value} {side.value} "
                           f"{quantity} {symbol} @ {price}")
                
                # Mock Order 반환 (상태 추적용)
                mock_order = Order(
                    order_id=f"mock_{datetime.now().timestamp()}",
                    exchange=exchange,
                    symbol=symbol,
                    side=side,
                    quantity=quantity,
                    price=price,
                    status="filled",
                    filled_quantity=quantity
                )
                self._orders[mock_order.order_id] = mock_order
                self.state_manager.set_order(mock_order)
                return mock_order
            
            # D19: Live Mode 안전 검사
            self._assert_live_mode_safety()
            
            # 실제 거래 실행
            if exchange == ExchangeType.UPBIT:
                order = await self.upbit.place_order(
                    f"KRW-{symbol}",
                    side,
                    quantity,
                    price
                )
            else:
                order = await self.binance.place_order(
                    f"{symbol}USDT",
                    side,
                    quantity,
                    price
                )
            
            if order:
                self._orders[order.order_id] = order
                self.state_manager.set_order(order)
                logger.info(f"[LIVE] Order placed: {order.order_id}")
            
            return order
        
        except RuntimeError as e:
            logger.error(f"Live Mode safety check failed: {e}")
            return None
        except Exception as e:
            logger.error(f"Error placing order: {e}")
            return None
    
    async def _cancel_order(self, exchange: ExchangeType, order_id: str) -> bool:
        """
        주문 취소
        
        Args:
            exchange: 거래소
            order_id: 주문 ID
        
        Returns:
            성공 여부
        """
        try:
            if exchange == ExchangeType.UPBIT:
                return await self.upbit.cancel_order(order_id)
            else:
                # Binance는 심볼이 필요함
                order = self._orders.get(order_id)
                if order:
                    return await self.binance.cancel_order(
                        f"{order.symbol}USDT",
                        order_id
                    )
            return False
        
        except Exception as e:
            logger.error(f"Error cancelling order: {e}")
            return False
    
    async def _manage_positions(self) -> None:
        """포지션 관리"""
        try:
            # TODO: 포지션 상태 업데이트
            # TODO: 손절/익절 로직
            pass
        
        except Exception as e:
            logger.error(f"Error managing positions: {e}")
    
    async def _update_metrics(self) -> None:
        """메트릭 업데이트 (D19: Live Mode 메트릭 포함)"""
        try:
            metrics = {
                "total_balance": self._total_balance,
                "available_balance": self._available_balance,
                "positions_count": len(self._positions),
                "orders_count": len(self._orders),
                "daily_loss": self.safety.state.daily_loss,
                "total_loss": self.safety.state.total_loss,
                "trades_today": self.safety.state.trades_today,
                # D19: Live Mode 메트릭
                "live_mode": self.live_mode,
                "live_enabled": self.live_enabled,
                "safety_mode": self.safety_mode,
                "dry_run": self.dry_run,
                "circuit_breaker_active": self.safety.state.circuit_breaker_active,
            }
            
            self.state_manager.set_metrics("live_trader", metrics)
            self.state_manager.set_heartbeat("live_trader")
        
        except Exception as e:
            logger.error(f"Error updating metrics: {e}")
