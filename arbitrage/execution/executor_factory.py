# -*- coding: utf-8 -*-
"""
D61: Multi-Symbol Paper Execution — Executor Factory
D64: Live Execution Integration — LiveExecutor Support

심볼별 executor 생성 및 관리.
"""

import logging
from typing import Dict, Optional

from arbitrage.types import PortfolioState
from arbitrage.live_runner import RiskGuard
from arbitrage.config.settings import FillModelConfig
from .executor import BaseExecutor, PaperExecutor, LiveExecutor
from .fill_model import BaseFillModel, SimpleFillModel, AdvancedFillModel

logger = logging.getLogger(__name__)


class ExecutorFactory:
    """
    D61: Executor Factory
    
    책임:
    - 심볼별 executor 생성
    - executor 관리
    """
    
    def __init__(self):
        """초기화"""
        self.executors: Dict[str, BaseExecutor] = {}
        logger.info("[D61_EXECUTOR_FACTORY] Initialized")
    
    def create_paper_executor(
        self,
        symbol: str,
        portfolio_state: PortfolioState,
        risk_guard: RiskGuard,
        fill_model_config: Optional[FillModelConfig] = None,
    ) -> PaperExecutor:
        """
        D61: Paper Executor 생성
        D80-4: Fill Model 지원
        D81-0: Settings 기반 Fill Model 주입
        
        Args:
            symbol: 거래 심볼
            portfolio_state: 포트폴리오 상태
            risk_guard: 리스크 가드
            fill_model_config: Fill Model 설정 (None이면 기본값 사용)
        
        Returns:
            PaperExecutor 인스턴스
        """
        if symbol in self.executors:
            logger.warning(f"[D61_EXECUTOR_FACTORY] Executor already exists for {symbol}")
            return self.executors[symbol]
        
        # D81-0: FillModelConfig 기반으로 Fill Model 인스턴스 생성
        if fill_model_config is None:
            fill_model_config = FillModelConfig()  # 기본값 사용
        
        fill_model_instance = None
        if fill_model_config.enable_fill_model:
            # Fill Model 타입에 따라 인스턴스 생성
            if fill_model_config.fill_model_type == "simple":
                fill_model_instance = SimpleFillModel(
                    enable_partial_fill=fill_model_config.enable_partial_fill,
                    enable_slippage=fill_model_config.enable_slippage,
                    default_slippage_alpha=fill_model_config.slippage_alpha,
                )
                logger.info(
                    f"[D81-0_EXECUTOR_FACTORY] Created SimpleFillModel for {symbol} "
                    f"(partial={fill_model_config.enable_partial_fill}, "
                    f"slippage={fill_model_config.enable_slippage}, "
                    f"alpha={fill_model_config.slippage_alpha})"
                )
            elif fill_model_config.fill_model_type == "advanced":
                # D81-1: AdvancedFillModel
                fill_model_instance = AdvancedFillModel(
                    enable_partial_fill=fill_model_config.enable_partial_fill,
                    enable_slippage=fill_model_config.enable_slippage,
                    default_slippage_alpha=fill_model_config.slippage_alpha,
                    num_levels=fill_model_config.advanced_num_levels,
                    level_spacing_bps=fill_model_config.advanced_level_spacing_bps,
                    decay_rate=fill_model_config.advanced_decay_rate,
                    slippage_exponent=fill_model_config.advanced_slippage_exponent,
                    base_volume_multiplier=fill_model_config.advanced_base_volume_multiplier,
                )
                logger.info(
                    f"[D81-1_EXECUTOR_FACTORY] Created AdvancedFillModel for {symbol} "
                    f"(levels={fill_model_config.advanced_num_levels}, "
                    f"spacing={fill_model_config.advanced_level_spacing_bps}bps, "
                    f"decay={fill_model_config.advanced_decay_rate}, "
                    f"exponent={fill_model_config.advanced_slippage_exponent})"
                )
            else:
                logger.error(
                    f"[D81-0_EXECUTOR_FACTORY] Unknown fill_model_type: {fill_model_config.fill_model_type}, "
                    f"using SimpleFillModel for {symbol}"
                )
                fill_model_instance = SimpleFillModel()
        
        executor = PaperExecutor(
            symbol=symbol,
            portfolio_state=portfolio_state,
            risk_guard=risk_guard,
            enable_fill_model=fill_model_config.enable_fill_model,
            fill_model=fill_model_instance,
            default_available_volume_factor=fill_model_config.available_volume_factor,
        )
        
        self.executors[symbol] = executor
        logger.info(
            f"[D61_EXECUTOR_FACTORY] Created PaperExecutor for {symbol} "
            f"(fill_model={fill_model_config.enable_fill_model})"
        )
        
        return executor
    
    def create_live_executor(
        self,
        symbol: str,
        portfolio_state: PortfolioState,
        risk_guard: RiskGuard,
        upbit_api=None,
        binance_api=None,
        dry_run: bool = True,
    ) -> LiveExecutor:
        """
        D64: Live Executor 생성
        
        Args:
            symbol: 거래 심볼
            portfolio_state: 포트폴리오 상태
            risk_guard: 리스크 가드
            upbit_api: Upbit API 클라이언트
            binance_api: Binance API 클라이언트
            dry_run: 드라이런 모드 (True면 실제 주문 안 함)
        
        Returns:
            LiveExecutor 인스턴스
        """
        if symbol in self.executors:
            logger.warning(f"[D64_EXECUTOR_FACTORY] Executor already exists for {symbol}")
            return self.executors[symbol]
        
        executor = LiveExecutor(
            symbol=symbol,
            portfolio_state=portfolio_state,
            risk_guard=risk_guard,
            upbit_api=upbit_api,
            binance_api=binance_api,
            dry_run=dry_run,
        )
        
        self.executors[symbol] = executor
        logger.info(f"[D64_EXECUTOR_FACTORY] Created LiveExecutor for {symbol} (dry_run={dry_run})")
        
        return executor
    
    def get_executor(self, symbol: str) -> BaseExecutor:
        """
        D61: Executor 조회
        
        Args:
            symbol: 거래 심볼
        
        Returns:
            Executor 인스턴스 또는 None
        """
        return self.executors.get(symbol)
    
    def get_all_executors(self) -> Dict[str, BaseExecutor]:
        """
        D61: 모든 Executor 조회
        
        Returns:
            Executor 딕셔너리
        """
        return self.executors.copy()
    
    def remove_executor(self, symbol: str) -> bool:
        """
        D61: Executor 제거
        
        Args:
            symbol: 거래 심볼
        
        Returns:
            성공 여부
        """
        if symbol in self.executors:
            del self.executors[symbol]
            logger.info(f"[D61_EXECUTOR_FACTORY] Removed executor for {symbol}")
            return True
        
        logger.warning(f"[D61_EXECUTOR_FACTORY] Executor not found for {symbol}")
        return False
