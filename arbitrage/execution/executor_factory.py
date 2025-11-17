# -*- coding: utf-8 -*-
"""
D61: Multi-Symbol Paper Execution — Executor Factory

심볼별 executor 생성 및 관리.
"""

import logging
from typing import Dict

from arbitrage.types import PortfolioState
from arbitrage.live_runner import RiskGuard
from .executor import BaseExecutor, PaperExecutor

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
    ) -> PaperExecutor:
        """
        D61: Paper Executor 생성
        
        Args:
            symbol: 거래 심볼
            portfolio_state: 포트폴리오 상태
            risk_guard: 리스크 가드
        
        Returns:
            PaperExecutor 인스턴스
        """
        if symbol in self.executors:
            logger.warning(f"[D61_EXECUTOR_FACTORY] Executor already exists for {symbol}")
            return self.executors[symbol]
        
        executor = PaperExecutor(
            symbol=symbol,
            portfolio_state=portfolio_state,
            risk_guard=risk_guard,
        )
        
        self.executors[symbol] = executor
        logger.info(f"[D61_EXECUTOR_FACTORY] Created PaperExecutor for {symbol}")
        
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
