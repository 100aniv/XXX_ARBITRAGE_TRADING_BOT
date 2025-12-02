#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
D18 Paper/Shadow Mode Trader Entrypoint
========================================

Docker 기반 Paper/Shadow 모드 트레이더.
SimulatedExchange + D17 시나리오를 사용하여 엔드-투-엔드 검증.

환경변수:
- APP_ENV: docker
- PAPER_MODE: true (paper mode 활성화)
- SCENARIO_FILE: configs/d17_scenarios/basic_spread_win.yaml
- REDIS_HOST: redis (Docker 내부)
- REDIS_PORT: 6379
- LOG_LEVEL: INFO
"""

import os
import sys
import logging
import asyncio
import yaml
from pathlib import Path
from datetime import datetime, timezone

# 프로젝트 루트 추가
sys.path.insert(0, str(Path(__file__).parent.parent))

from arbitrage.exchanges.simulated_exchange import SimulatedExchange
from arbitrage.state_manager import StateManager
from liveguard.safety import SafetyModule
from liveguard.risk_limits import RiskLimits
from arbitrage.types import ExchangeType, OrderSide

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s'
)
logger = logging.getLogger(__name__)


class PaperTrader:
    """Docker 기반 Paper/Shadow 모드 트레이더"""
    
    def __init__(self, scenario_path: str, redis_host: str = "localhost", redis_port: int = 6379):
        """
        Args:
            scenario_path: 시나리오 YAML 파일 경로
            redis_host: Redis 호스트
            redis_port: Redis 포트
        """
        logger.info(f"Initializing PaperTrader with scenario: {scenario_path}")
        
        # 시나리오 로드
        with open(scenario_path, 'r', encoding='utf-8') as f:
            self.scenario = yaml.safe_load(f)
        
        self.name = self.scenario.get('name', 'unknown')
        self.steps = self.scenario.get('steps', [])
        self.risk_profile = self.scenario.get('risk_profile', {})
        self.expected = self.scenario.get('expected_outcomes', {})
        
        logger.info(f"Scenario: {self.name}")
        logger.info(f"Steps: {len(self.steps)}")
        logger.info(f"Risk Profile: {self.risk_profile}")
        
        # SimulatedExchange 초기화
        self.exchange = SimulatedExchange(
            exchange_type=ExchangeType.UPBIT,
            initial_balance={"KRW": 10_000_000, "BTC": 0},
            slippage_bps=self.risk_profile.get('slippage_bps', 5.0)
        )
        
        # SafetyModule 초기화
        self.safety = SafetyModule(
            RiskLimits(
                max_position_size=self.risk_profile.get('max_position_krw', 1_000_000),
                max_daily_loss=self.risk_profile.get('max_daily_loss_krw', 500_000),
                max_trades_per_hour=self.risk_profile.get('max_trades_per_hour', 100),
                min_spread_pct=self.risk_profile.get('min_spread_pct', 0.1)
            )
        )
        
        # StateManager 초기화 (Redis 연동 + in-memory fallback)
        # D21: namespace를 paper:local로 설정
        self.state_manager = StateManager(
            redis_host=redis_host,
            redis_port=redis_port,
            redis_db=0,
            namespace="paper:local",
            enabled=True,
            key_prefix="arbitrage"
        )
        logger.info(f"StateManager initialized with namespace=paper:local")
        
        # 통계
        self.trades = []
        self.signals = []
        self.pnl = 0.0
        self.start_time = datetime.now(timezone.utc)
    
    async def run(self) -> dict:
        """
        시나리오 실행
        
        Returns:
            실행 결과 딕셔너리
        """
        logger.info("Starting paper trader run...")
        
        try:
            await self.exchange.connect()
            logger.info("Exchange connected")
            
            # 시나리오 스텝 실행
            for step_idx, step in enumerate(self.steps):
                t = step.get('t')
                upbit_bid = step.get('upbit_bid')
                upbit_ask = step.get('upbit_ask')
                
                logger.debug(f"Step {step_idx}: t={t}, bid={upbit_bid}, ask={upbit_ask}")
                
                # 가격 설정
                if upbit_bid and upbit_ask:
                    self.exchange.set_price("KRW-BTC", upbit_bid, upbit_ask)
                
                # 신호 생성 (스프레드 기반)
                spread_pct = ((upbit_ask - upbit_bid) / upbit_bid) * 100 if upbit_bid else 0
                
                # 스프레드가 최소값보다 크면 신호 생성
                if spread_pct > self.risk_profile.get('min_spread_pct', 0.1):
                    # 안전 검사
                    can_execute, reason = self.safety.can_execute_order(
                        position_value=1_000_000,
                        current_positions=len(self.trades),
                        current_loss=self.pnl,
                        total_balance=10_000_000
                    )
                    
                    if can_execute:
                        # 주문 실행
                        order = await self.exchange.place_order(
                            symbol="KRW-BTC",
                            side=OrderSide.BUY,
                            quantity=1.0,
                            price=upbit_ask
                        )
                        
                        if order:
                            self.trades.append(order)
                            self.signals.append({
                                't': t,
                                'spread_pct': spread_pct,
                                'order_id': order.order_id
                            })
                            self.safety.record_trade(0)  # 임시 손실
                            logger.info(f"Order placed: {order.order_id} (spread={spread_pct:.2f}%)")
                    else:
                        logger.warning(f"Order rejected: {reason}")
            
            await self.exchange.disconnect()
            logger.info("Exchange disconnected")
            
            # 결과 계산
            stats = self.exchange.get_stats()
            
            result = {
                'scenario': self.name,
                'trades': len(self.trades),
                'signals': len(self.signals),
                'total_fees': stats['total_fees'],
                'pnl': self.pnl,
                'circuit_breaker_active': self.safety.state.circuit_breaker_active,
                'safety_violations': 0,
                'duration_seconds': (datetime.now(timezone.utc) - self.start_time).total_seconds()
            }
            
            logger.info(f"Paper trader run completed: {result}")
            
            # StateManager에 결과 저장
            if self.state_manager:
                try:
                    self.state_manager.set_metrics({
                        'paper_trader_result': result,
                        'timestamp': datetime.now(timezone.utc).isoformat()
                    })
                    logger.info("Results saved to StateManager")
                except Exception as e:
                    logger.warning(f"Failed to save results to StateManager: {e}")
            
            return result
        
        except Exception as e:
            logger.error(f"Error during paper trader run: {e}", exc_info=True)
            raise


async def main():
    """메인 엔트리포인트"""
    
    # 환경변수 읽기
    app_env = os.getenv('APP_ENV', 'local')
    paper_mode = os.getenv('PAPER_MODE', 'false').lower() == 'true'
    scenario_file = os.getenv('SCENARIO_FILE', 'configs/d17_scenarios/basic_spread_win.yaml')
    redis_host = os.getenv('REDIS_HOST', 'localhost')
    redis_port = int(os.getenv('REDIS_PORT', '6379'))
    log_level = os.getenv('LOG_LEVEL', 'INFO')
    
    # 로그 레벨 설정
    logging.getLogger().setLevel(getattr(logging, log_level.upper(), logging.INFO))
    
    logger.info(f"APP_ENV: {app_env}")
    logger.info(f"PAPER_MODE: {paper_mode}")
    logger.info(f"SCENARIO_FILE: {scenario_file}")
    logger.info(f"REDIS_HOST: {redis_host}")
    logger.info(f"REDIS_PORT: {redis_port}")
    
    if not paper_mode:
        logger.error("PAPER_MODE is not enabled. Exiting.")
        sys.exit(1)
    
    # 시나리오 파일 경로 확인
    scenario_path = Path(scenario_file)
    if not scenario_path.exists():
        # 상대 경로로 시도
        scenario_path = Path(__file__).parent.parent / scenario_file
    
    if not scenario_path.exists():
        logger.error(f"Scenario file not found: {scenario_file}")
        sys.exit(1)
    
    logger.info(f"Using scenario file: {scenario_path}")
    
    # PaperTrader 실행
    try:
        trader = PaperTrader(
            scenario_path=str(scenario_path),
            redis_host=redis_host,
            redis_port=redis_port
        )
        result = await trader.run()
        
        logger.info(f"Final result: {result}")
        
        # 성공 종료
        sys.exit(0)
    
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == '__main__':
    asyncio.run(main())
